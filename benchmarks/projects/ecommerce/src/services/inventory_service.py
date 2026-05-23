"""
Inventory / Stock Management Service.

Manages product stock levels, reservations, and low-stock alerts.
Reservations are time-limited holds that prevent overselling.

ARCHITECTURE:
- Called synchronously by order_service for reserve/release operations.
- Emits 'inventory.low_stock' events consumed by notification_service.
- Does NOT know about order state - only manages reservations by ID.
- The order_service is responsible for calling release when orders are cancelled.

IMPORTANT COUPLING:
- Reservation TTL (15 min) must be longer than payment authorization time.
- If payment takes longer than TTL, reservation expires and stock may be sold
  to another customer. This is an accepted trade-off (documented in ADR-002).
"""

from uuid import UUID, uuid4
from typing import Optional
from datetime import datetime, timedelta

from src.database.connection import get_db_session, get_redis
from src.config.constants import (
    STOCK_RESERVATION_TTL_SECONDS, LOW_STOCK_THRESHOLD,
    ORDER_RESERVATION_TTL
)


class InventoryService:
    """Manages stock levels and time-limited reservations."""

    def __init__(self):
        self.redis = get_redis()  # For reservation tracking and event emission

    async def reserve_stock(
        self, product_id: UUID, variant_id: Optional[UUID],
        quantity: int, ttl: int = STOCK_RESERVATION_TTL_SECONDS
    ) -> str:
        """Reserve stock for an order (time-limited hold).
        
        Reservations prevent overselling by holding stock for a limited time.
        If the order isn't confirmed within TTL, reservation auto-expires
        and stock becomes available again.
        
        Uses Redis for fast reservation tracking with automatic expiry.
        PostgreSQL stock levels are updated only on confirmation (not reservation).
        
        Raises ValueError if insufficient stock available.
        """
        reservation_id = str(uuid4())
        
        # Check available stock (total - active reservations)
        available = await self._get_available_stock(product_id, variant_id)
        if available < quantity:
            raise ValueError(
                f"Insufficient stock: requested {quantity}, available {available}"
            )
        
        # Create reservation in Redis with TTL
        reservation_key = f"reservation:{reservation_id}"
        await self.redis.setex(reservation_key, ttl, f"{product_id}:{variant_id}:{quantity}")
        
        # Track reservation against product for availability calculation
        await self.redis.sadd(f"product_reservations:{product_id}", reservation_id)
        
        # Check if stock is getting low
        remaining = available - quantity
        if remaining <= LOW_STOCK_THRESHOLD:
            await self._emit_low_stock_alert(product_id, remaining)
        
        return reservation_id

    async def release_reservation(self, reservation_id: str):
        """Release a single reservation (stock becomes available again).
        
        Called by order_service when:
        - Order creation fails (rollback)
        - Order is cancelled
        - Reservation expires (handled by Redis TTL, but explicit release is cleaner)
        """
        reservation_key = f"reservation:{reservation_id}"
        data = await self.redis.get(reservation_key)
        if data:
            product_id = data.split(":")[0]
            await self.redis.delete(reservation_key)
            await self.redis.srem(f"product_reservations:{product_id}", reservation_id)

    async def release_order_reservations(self, order_id: UUID):
        """Release all reservations associated with an order.
        
        Called by order_service.cancel_order().
        Looks up reservation IDs from the order record and releases each one.
        """
        async with get_db_session() as db:
            reservations = await db.execute(
                "SELECT reservation_id FROM order_reservations WHERE order_id = %s",
                (str(order_id),)
            )
            for res in reservations:
                await self.release_reservation(res["reservation_id"])

    async def confirm_reservation(self, reservation_id: str):
        """Convert reservation to permanent stock deduction.
        
        Called when order is confirmed (payment captured).
        Removes Redis reservation and decrements PostgreSQL stock.
        """
        reservation_key = f"reservation:{reservation_id}"
        data = await self.redis.get(reservation_key)
        if not data:
            raise ValueError("Reservation expired or not found")
        
        product_id, variant_id, quantity = data.split(":")
        
        async with get_db_session() as db:
            await db.execute(
                "UPDATE product_variants SET stock = stock - %s "
                "WHERE product_id = %s AND id = %s AND stock >= %s",
                (int(quantity), product_id, variant_id, int(quantity))
            )
            await db.commit()
        
        # Clean up reservation
        await self.redis.delete(reservation_key)
        await self.redis.srem(f"product_reservations:{product_id}", reservation_id)

    async def _get_available_stock(self, product_id: UUID, variant_id: Optional[UUID]) -> int:
        """Calculate available stock = total stock - active reservations."""
        async with get_db_session() as db:
            result = await db.execute(
                "SELECT stock FROM product_variants WHERE product_id = %s AND id = %s",
                (str(product_id), str(variant_id))
            )
            total_stock = result[0]["stock"] if result else 0
        
        # Count active reservations for this product
        reservation_ids = await self.redis.smembers(f"product_reservations:{product_id}")
        reserved = 0
        for res_id in reservation_ids:
            data = await self.redis.get(f"reservation:{res_id}")
            if data:
                reserved += int(data.split(":")[2])
        
        return total_stock - reserved

    async def _emit_low_stock_alert(self, product_id: UUID, remaining: int):
        """Emit low stock event for notification_service to handle."""
        import json
        await self.redis.publish("inventory_events", json.dumps({
            "type": "inventory.low_stock",
            "payload": {"product_id": str(product_id), "remaining": remaining},
            "timestamp": datetime.utcnow().isoformat()
        }))

    async def get_stock_levels(self, product_ids: list) -> dict:
        """Get current stock levels for multiple products (used by product listing)."""
        levels = {}
        for pid in product_ids:
            available = await self._get_available_stock(pid, None)
            levels[str(pid)] = available
        return levels
