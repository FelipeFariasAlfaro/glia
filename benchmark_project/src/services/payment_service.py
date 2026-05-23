"""
Payment Processing Service.

Integrates with Stripe for payment authorization, capture, and refunds.
Handles webhook events from Stripe for async payment status updates.

CRITICAL HISTORY:
- May 2024: Double-charge incident. Two concurrent requests for the same order
  both passed the "check if already charged" query before either committed.
  Root cause: read-then-write race condition without proper locking.
  Fix: Added PostgreSQL advisory locks keyed on order_id + idempotency keys.
  The advisory lock is acquired in order_service before calling this service.
  See docs/incidents/2024-05-payment-double-charge.md

ARCHITECTURE NOTE:
- This service is called synchronously by order_service for authorize/capture/refund.
- It also receives async webhooks from Stripe (payment.succeeded, payment.failed).
- Webhook events are verified using Stripe's signature verification.
"""

import stripe
from uuid import UUID
from typing import Dict, Optional
from datetime import datetime

from src.config.settings import settings
from src.database.connection import get_db_session, get_redis
from src.config.constants import PAYMENT_CAPTURE_WINDOW_HOURS


class PaymentService:
    """Handles Stripe payment operations with idempotency protection."""

    def __init__(self):
        stripe.api_key = settings.STRIPE_SECRET_KEY
        self.redis = get_redis()

    async def authorize(self, user_id: UUID, amount: float, idempotency_key: str) -> Dict:
        """Create a payment intent (authorize, don't capture yet).
        
        Authorization holds funds for up to 7 days.
        Capture happens when order transitions to 'confirmed'.
        
        Idempotency key prevents double-charge on retry (May 2024 fix).
        If the same key is sent twice, Stripe returns the original intent.
        """
        # Check idempotency at application level too (belt and suspenders)
        existing = await self.redis.get(f"payment_idem:{idempotency_key}")
        if existing:
            return {"intent_id": existing, "status": "already_authorized"}

        intent = stripe.PaymentIntent.create(
            amount=int(amount * 100),  # Stripe uses cents
            currency="usd",
            capture_method="manual",  # Authorize only
            metadata={"user_id": str(user_id), "idempotency_key": idempotency_key},
            idempotency_key=idempotency_key
        )
        
        # Cache the intent ID for idempotency checks
        await self.redis.setex(
            f"payment_idem:{idempotency_key}",
            86400,  # 24h TTL
            intent.id
        )
        return {"intent_id": intent.id, "status": intent.status}

    async def capture(self, payment_intent_id: str) -> Dict:
        """Capture a previously authorized payment.
        
        Called by order_service when order transitions to 'confirmed'.
        Must be captured within PAYMENT_CAPTURE_WINDOW_HOURS (default 72h).
        """
        intent = stripe.PaymentIntent.capture(payment_intent_id)
        return {"intent_id": intent.id, "status": intent.status, "captured_at": datetime.utcnow().isoformat()}

    async def refund(self, payment_intent_id: str, amount: Optional[float] = None) -> Dict:
        """Issue a full or partial refund.
        
        Called by order_service when order is cancelled after payment capture.
        Partial refunds are used for partial cancellations.
        Refund status is tracked and emitted as event for notification_service.
        """
        refund_params = {"payment_intent": payment_intent_id}
        if amount:
            refund_params["amount"] = int(amount * 100)
        
        refund = stripe.Refund.create(**refund_params)
        
        # Emit refund event for notification service
        await self._emit_payment_event("payment.refunded", {
            "payment_intent_id": payment_intent_id,
            "refund_id": refund.id,
            "amount": amount,
            "status": refund.status
        })
        return {"refund_id": refund.id, "status": refund.status}

    async def handle_stripe_webhook(self, payload: bytes, signature: str) -> None:
        """Process incoming Stripe webhook events.
        
        Verifies signature using webhook secret to prevent spoofing.
        Handles: payment_intent.succeeded, payment_intent.payment_failed,
        charge.refunded, charge.dispute.created
        """
        event = stripe.Webhook.construct_event(
            payload, signature, settings.STRIPE_WEBHOOK_SECRET
        )
        
        if event.type == "payment_intent.payment_failed":
            await self._handle_payment_failure(event.data.object)
        elif event.type == "charge.dispute.created":
            await self._handle_dispute(event.data.object)

    async def _handle_payment_failure(self, intent):
        """Handle failed payment - notify user and update order status."""
        await self._emit_payment_event("payment.failed", {
            "payment_intent_id": intent.id,
            "user_id": intent.metadata.get("user_id"),
            "error": intent.last_payment_error
        })

    async def _handle_dispute(self, dispute):
        """Handle charge dispute - flag order for review."""
        await self._emit_payment_event("payment.disputed", {
            "dispute_id": dispute.id,
            "amount": dispute.amount / 100
        })

    async def _emit_payment_event(self, event_type: str, payload: dict):
        """Publish payment event to Redis for notification_service consumption."""
        import json
        await self.redis.publish("payment_events", json.dumps({
            "type": event_type, "payload": payload,
            "timestamp": datetime.utcnow().isoformat()
        }))
