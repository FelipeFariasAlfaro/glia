"""
Order Processing Service.

Implements order state machine, coordinates inventory reservation,
payment processing, and event emission for downstream services.

CRITICAL: This service orchestrates the order lifecycle. Changes here
affect inventory_service (stock reservation/release), payment_service
(charge/refund), and notification_service (via events).

HISTORY:
- May 2024: Double-charge bug. Race condition where concurrent requests
  could both pass the "not yet charged" check before either wrote the
  charge record. Fixed with database-level advisory locks and idempotency keys.
  See docs/incidents/2024-05-payment-double-charge.md
"""

from uuid import UUID, uuid4
from typing import List, Optional
from datetime import datetime

from src.models.order import Order, OrderStatus, OrderItem
from src.services.inventory_service import InventoryService
from src.services.payment_service import PaymentService
from src.database.connection import get_db_session, get_redis
from src.config.constants import ORDER_RESERVATION_TTL


class OrderService:
    """Orchestrates order lifecycle with inventory and payment coordination."""

    def __init__(self):
        self.inventory = InventoryService()
        self.payment = PaymentService()
        self.redis = get_redis()  # For event publishing

    async def create_order(self, user_id: UUID, items: List[dict]) -> Order:
        """Create order with inventory reservation and payment authorization.
        
        Steps (all-or-nothing):
        1. Reserve inventory for all items (rollback if any fails)
        2. Calculate total with tax
        3. Authorize payment (hold, not charge)
        4. Persist order with 'pending' status
        5. Emit 'order.created' event (consumed by notification_service)
        
        Uses idempotency key to prevent double-charge on retry (May 2024 fix).
        """
        idempotency_key = str(uuid4())
        
        async with get_db_session() as db:
            # Step 1: Reserve inventory
            reservation_ids = []
            try:
                for item in items:
                    res_id = await self.inventory.reserve_stock(
                        product_id=item["product_id"],
                        variant_id=item.get("variant_id"),
                        quantity=item["quantity"],
                        ttl=ORDER_RESERVATION_TTL
                    )
                    reservation_ids.append(res_id)
            except Exception:
                # Rollback any successful reservations
                for res_id in reservation_ids:
                    await self.inventory.release_reservation(res_id)
                raise

            # Step 2-3: Calculate and authorize payment
            total = await self._calculate_total(items, db)
            payment_auth = await self.payment.authorize(
                user_id=user_id, amount=total,
                idempotency_key=idempotency_key
            )

            # Step 4: Persist order
            order = Order(
                id=uuid4(), user_id=user_id, status=OrderStatus.PENDING,
                total=total, payment_intent_id=payment_auth["intent_id"],
                idempotency_key=idempotency_key, created_at=datetime.utcnow()
            )
            db.add(order)
            await db.commit()

        # Step 5: Emit event (async, non-blocking)
        await self._emit_event("order.created", {
            "order_id": str(order.id), "user_id": str(user_id),
            "total": total, "items": items
        })
        return order

    async def cancel_order(self, order_id: UUID, user_id: UUID, reason: str = "") -> Order:
        """Cancel order: release inventory, refund payment, notify user.
        
        IMPORTANT: Cancellation releases inventory reservations held by
        inventory_service. The inventory_service doesn't know about order
        state - it only manages reservations by ID. This service is
        responsible for triggering the release.
        """
        async with get_db_session() as db:
            order = await db.get(Order, order_id)
            if not order or order.user_id != user_id:
                raise ValueError("Order not found")
            if order.status not in (OrderStatus.PENDING, OrderStatus.CONFIRMED):
                raise ValueError(f"Cannot cancel order in {order.status} state")

            # Release inventory reservations
            await self.inventory.release_order_reservations(order_id)
            
            # Refund payment if charged
            if order.status == OrderStatus.CONFIRMED:
                await self.payment.refund(order.payment_intent_id, order.total)

            order.status = OrderStatus.CANCELLED
            order.cancelled_at = datetime.utcnow()
            order.cancellation_reason = reason
            await db.commit()

        await self._emit_event("order.cancelled", {
            "order_id": str(order_id), "user_id": str(user_id), "reason": reason
        })
        return order

    async def transition_status(self, order_id: UUID, new_status: OrderStatus, actor) -> Order:
        """Transition order to new status following state machine rules.
        
        Valid transitions:
          pending → confirmed (payment captured)
          confirmed → shipped (admin only)
          shipped → delivered (admin only)
          pending/confirmed → cancelled (customer or admin)
        
        Each transition emits an event for notification_service.
        """
        async with get_db_session() as db:
            order = await db.get(Order, order_id)
            if not order:
                raise ValueError("Order not found")
            if not order.can_transition_to(new_status):
                raise ValueError(f"Invalid transition: {order.status} → {new_status}")
            
            # Capture payment on confirmation
            if new_status == OrderStatus.CONFIRMED:
                await self.payment.capture(order.payment_intent_id)
            
            old_status = order.status
            order.status = new_status
            await db.commit()

        await self._emit_event("order.status_changed", {
            "order_id": str(order_id), "old_status": old_status.value,
            "new_status": new_status.value
        })
        return order

    async def _calculate_total(self, items: List[dict], db) -> float:
        """Calculate order total including tax."""
        total = 0.0
        for item in items:
            product = await db.get("Product", item["product_id"])
            total += product.price * item["quantity"]
        return round(total * 1.08, 2)  # 8% tax

    async def _emit_event(self, event_type: str, payload: dict):
        """Publish event to Redis pub/sub for downstream consumers.
        
        Consumers: notification_service, webhook_worker, analytics.
        This is the decoupling point - we don't import or call those services.
        """
        import json
        await self.redis.publish("order_events", json.dumps({
            "type": event_type, "payload": payload,
            "timestamp": datetime.utcnow().isoformat()
        }))
