"""
Order Model with State Machine.

Implements strict state transitions for order lifecycle:
  pending → confirmed → shipped → delivered
  pending → cancelled
  confirmed → cancelled (triggers refund)

State transitions emit events consumed by notification_service and webhook_worker.
The state machine prevents invalid transitions (e.g., shipped → pending).

COUPLING NOTE:
- order_service.cancel_order() calls inventory_service.release_order_reservations()
- order_service.transition_status() calls payment_service.capture() on confirmation
- notification_service listens to state change events (no direct coupling)
"""

from uuid import UUID, uuid4
from datetime import datetime
from enum import Enum
from typing import Optional, List
from dataclasses import dataclass, field


class OrderStatus(Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


# Valid state transitions - key is current state, value is list of allowed next states
VALID_TRANSITIONS = {
    OrderStatus.PENDING: [OrderStatus.CONFIRMED, OrderStatus.CANCELLED],
    OrderStatus.CONFIRMED: [OrderStatus.SHIPPED, OrderStatus.CANCELLED],
    OrderStatus.SHIPPED: [OrderStatus.DELIVERED],
    OrderStatus.DELIVERED: [],  # Terminal state
    OrderStatus.CANCELLED: [],  # Terminal state
}


@dataclass
class OrderItem:
    """Individual line item in an order."""
    id: UUID = field(default_factory=uuid4)
    product_id: UUID = field(default_factory=uuid4)
    variant_id: Optional[UUID] = None
    quantity: int = 1
    unit_price: float = 0.0
    reservation_id: Optional[str] = None  # Links to inventory_service reservation


@dataclass
class Order:
    """Order entity with state machine enforcement.
    
    The idempotency_key field was added after the May 2024 double-charge incident.
    It ensures that retried order creation doesn't result in duplicate charges.
    The payment_intent_id links to Stripe's payment intent for this order.
    """
    id: UUID = field(default_factory=uuid4)
    user_id: UUID = field(default_factory=uuid4)
    status: OrderStatus = OrderStatus.PENDING
    items: List[OrderItem] = field(default_factory=list)
    total: float = 0.0
    payment_intent_id: Optional[str] = None
    idempotency_key: Optional[str] = None  # Added May 2024 to prevent double-charge
    created_at: datetime = field(default_factory=datetime.utcnow)
    confirmed_at: Optional[datetime] = None
    shipped_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    cancellation_reason: Optional[str] = None

    def can_transition_to(self, new_status: OrderStatus) -> bool:
        """Check if transition from current status to new_status is valid."""
        allowed = VALID_TRANSITIONS.get(self.status, [])
        return new_status in allowed

    def transition_to(self, new_status: OrderStatus) -> None:
        """Execute state transition with timestamp tracking.
        
        Raises ValueError if transition is invalid.
        Sets appropriate timestamp for the new state.
        """
        if not self.can_transition_to(new_status):
            raise ValueError(
                f"Invalid transition: {self.status.value} → {new_status.value}. "
                f"Allowed: {[s.value for s in VALID_TRANSITIONS[self.status]]}"
            )
        self.status = new_status
        now = datetime.utcnow()
        if new_status == OrderStatus.CONFIRMED:
            self.confirmed_at = now
        elif new_status == OrderStatus.SHIPPED:
            self.shipped_at = now
        elif new_status == OrderStatus.DELIVERED:
            self.delivered_at = now
        elif new_status == OrderStatus.CANCELLED:
            self.cancelled_at = now

    def to_dict(self) -> dict:
        """Serialize order for API response."""
        return {
            "id": str(self.id), "user_id": str(self.user_id),
            "status": self.status.value, "total": self.total,
            "items": [{"product_id": str(i.product_id), "quantity": i.quantity} for i in self.items],
            "created_at": self.created_at.isoformat(),
            "cancelled_at": self.cancelled_at.isoformat() if self.cancelled_at else None
        }
