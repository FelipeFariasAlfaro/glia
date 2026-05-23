"""
Order Management API Routes.

Handles order creation, listing, status updates, and cancellation.
Order state transitions follow a strict state machine (see order model).
Inventory is reserved on creation and released on cancellation.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from uuid import UUID

from src.services.order_service import OrderService
from src.services.auth_service import get_current_user
from src.models.order import OrderStatus
from src.utils.validators import validate_order_items

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("/", status_code=201)
async def create_order(
    items: List[dict],
    current_user=Depends(get_current_user),
    order_service: OrderService = Depends()
):
    """Create a new order and reserve inventory.
    
    This triggers several side effects via events:
    1. Inventory reservation (sync - must succeed or order fails)
    2. Payment authorization (sync - must succeed or inventory is released)
    3. Confirmation email (async - via event bus, doesn't block)
    4. Webhook notification (async - via event bus)
    
    WARNING: There was a race condition here (May 2024) where payment could
    be charged twice if the client retried. Fixed with idempotency keys.
    """
    validate_order_items(items)
    order = await order_service.create_order(
        user_id=current_user.id, items=items
    )
    return {"order_id": order.id, "status": order.status.value}


@router.get("/", response_model=List[dict])
async def list_orders(
    current_user=Depends(get_current_user),
    status_filter: Optional[OrderStatus] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100)
):
    """List orders for the current user with optional status filter."""
    order_service = OrderService()
    return await order_service.list_user_orders(
        user_id=current_user.id, status=status_filter,
        page=page, page_size=page_size
    )


@router.patch("/{order_id}/status")
async def update_order_status(
    order_id: UUID,
    new_status: OrderStatus,
    current_user=Depends(get_current_user),
    order_service: OrderService = Depends()
):
    """Update order status following the state machine rules.
    
    Only admins can transition to 'shipped' or 'delivered'.
    Customers can only cancel orders in 'pending' or 'confirmed' state.
    Each transition emits an event consumed by notification_service.
    """
    order = await order_service.transition_status(
        order_id=order_id, new_status=new_status,
        actor=current_user
    )
    return {"order_id": order.id, "status": order.status.value}


@router.post("/{order_id}/cancel")
async def cancel_order(
    order_id: UUID,
    reason: str = "",
    current_user=Depends(get_current_user),
    order_service: OrderService = Depends()
):
    """Cancel an order and release reserved inventory.
    
    Cancellation triggers:
    1. Inventory release (reserved stock returned to available)
    2. Payment refund (if already charged)
    3. Cancellation notification to user
    
    Can only cancel orders in 'pending' or 'confirmed' state.
    """
    order = await order_service.cancel_order(
        order_id=order_id, user_id=current_user.id, reason=reason
    )
    return {"order_id": order.id, "status": "cancelled", "refund_initiated": True}
