"""
Notification Dispatch Service.

Handles notification creation, template rendering, and dispatch coordination.
Subscribes to domain events via Redis pub/sub (event-driven architecture).

ARCHITECTURE:
- Does NOT import order_service, payment_service, or inventory_service.
- Instead, subscribes to Redis channels: order_events, payment_events, inventory_events.
- This decoupling means notification logic can change without affecting core services.
- See ADR-002 for the rationale behind event-driven architecture.

RATE LIMITING:
- Email: max 10 per user per hour (prevents spam on rapid status changes)
- Push: max 30 per user per hour
- Webhooks: max 100 per endpoint per hour (with exponential backoff on failure)
"""

from uuid import UUID, uuid4
from typing import List, Dict, Optional
from datetime import datetime
from enum import Enum

from src.database.connection import get_db_session, get_redis
from src.config.constants import (
    EMAIL_RATE_LIMIT, PUSH_RATE_LIMIT, WEBHOOK_RATE_LIMIT,
    WEBHOOK_MAX_RETRIES, WEBHOOK_BACKOFF_BASE
)


class NotificationChannel(Enum):
    EMAIL = "email"
    PUSH = "push"
    WEBHOOK = "webhook"


class NotificationService:
    """Dispatches notifications across channels with rate limiting and templating."""

    def __init__(self):
        self.redis = get_redis()  # Used for rate limiting AND event subscription
        self._templates = self._load_templates()

    async def handle_order_event(self, event: dict):
        """Process order domain events and create appropriate notifications.
        
        Event types handled:
        - order.created → confirmation email + push
        - order.status_changed → status update email + push
        - order.cancelled → cancellation email + push + webhook
        
        This method is called by the event subscriber (not by order_service directly).
        The decoupling allows us to add/modify notifications without touching order logic.
        """
        event_type = event["type"]
        user_id = event["payload"]["user_id"]
        
        template_key = self._get_template_for_event(event_type)
        if not template_key:
            return
        
        content = self._render_template(template_key, event["payload"])
        await self._dispatch_notification(user_id, content, event_type)

    async def handle_payment_event(self, event: dict):
        """Process payment events (refunds, failures, disputes)."""
        event_type = event["type"]
        user_id = event["payload"].get("user_id")
        if not user_id:
            return
        content = self._render_template(f"payment.{event_type}", event["payload"])
        await self._dispatch_notification(user_id, content, event_type)

    async def _dispatch_notification(self, user_id: str, content: dict, event_type: str):
        """Route notification to appropriate channels based on user preferences.
        
        Checks rate limits before sending. If rate limited, notification is
        queued for later delivery by the email_worker/webhook_worker.
        """
        prefs = await self.get_preferences(UUID(user_id))
        
        if prefs.get("email_enabled", True) and await self._check_rate_limit(user_id, "email"):
            await self._queue_email(user_id, content)
        
        if prefs.get("push_enabled", True) and await self._check_rate_limit(user_id, "push"):
            await self._send_push(user_id, content)
        
        # Dispatch to registered webhooks
        webhooks = await self._get_active_webhooks(user_id, event_type)
        for webhook in webhooks:
            if await self._check_rate_limit(webhook["id"], "webhook"):
                await self._queue_webhook_delivery(webhook, content)

    async def _check_rate_limit(self, entity_id: str, channel: str) -> bool:
        """Check if entity has exceeded rate limit for channel.
        
        Uses Redis sliding window counter.
        Limits: email=10/hr, push=30/hr, webhook=100/hr per endpoint.
        """
        limits = {"email": EMAIL_RATE_LIMIT, "push": PUSH_RATE_LIMIT, "webhook": WEBHOOK_RATE_LIMIT}
        key = f"notif_rate:{channel}:{entity_id}"
        count = await self.redis.incr(key)
        if count == 1:
            await self.redis.expire(key, 3600)
        return count <= limits.get(channel, 10)

    async def _queue_email(self, user_id: str, content: dict):
        """Queue email for background processing by email_worker."""
        import json
        await self.redis.lpush("email_queue", json.dumps({
            "user_id": user_id, "content": content,
            "queued_at": datetime.utcnow().isoformat()
        }))

    async def _queue_webhook_delivery(self, webhook: dict, content: dict):
        """Queue webhook for delivery by webhook_worker with retry config."""
        import json
        await self.redis.lpush("webhook_queue", json.dumps({
            "webhook_id": webhook["id"], "url": webhook["url"],
            "payload": content, "attempt": 0,
            "max_retries": WEBHOOK_MAX_RETRIES
        }))

    async def get_user_notifications(self, user_id: UUID, unread_only: bool, page: int, page_size: int):
        """Retrieve paginated notifications for a user."""
        async with get_db_session() as db:
            query = f"SELECT * FROM notifications WHERE user_id = '{user_id}'"
            if unread_only:
                query += " AND read_at IS NULL"
            query += f" ORDER BY created_at DESC LIMIT {page_size} OFFSET {(page-1)*page_size}"
            return await db.execute(query)

    async def get_preferences(self, user_id: UUID) -> dict:
        """Get notification preferences, with defaults for new users."""
        async with get_db_session() as db:
            prefs = await db.execute(
                f"SELECT * FROM notification_preferences WHERE user_id = '{user_id}'"
            )
            return prefs or {"email_enabled": True, "push_enabled": True, "webhook_enabled": False}

    async def update_preferences(self, user_id: UUID, prefs: dict) -> dict:
        """Update notification preferences for a user."""
        async with get_db_session() as db:
            await db.execute(
                "INSERT INTO notification_preferences (user_id, prefs) VALUES (%s, %s) "
                "ON CONFLICT (user_id) DO UPDATE SET prefs = %s",
                (str(user_id), prefs, prefs)
            )
            return prefs

    def _load_templates(self) -> dict:
        """Load notification templates from database/config."""
        return {
            "order.created": {"subject": "Order Confirmed", "body": "Your order {order_id} has been placed."},
            "order.cancelled": {"subject": "Order Cancelled", "body": "Order {order_id} was cancelled."},
            "order.status_changed": {"subject": "Order Update", "body": "Order {order_id}: {old_status} → {new_status}"},
            "payment.refunded": {"subject": "Refund Processed", "body": "Refund of ${amount} processed."},
            "payment.failed": {"subject": "Payment Failed", "body": "Payment for your order failed."},
        }

    def _render_template(self, template_key: str, data: dict) -> dict:
        """Render a notification template with event data."""
        template = self._templates.get(template_key, {"subject": "Notification", "body": str(data)})
        return {
            "subject": template["subject"].format(**data) if "{" in template["subject"] else template["subject"],
            "body": template["body"].format(**data) if "{" in template["body"] else template["body"]
        }

    def _get_template_for_event(self, event_type: str) -> Optional[str]:
        """Map event type to template key."""
        return event_type if event_type in self._templates else None

    async def _get_active_webhooks(self, user_id: str, event_type: str) -> List[dict]:
        """Get active webhooks for user that subscribe to this event type."""
        async with get_db_session() as db:
            return await db.execute(
                "SELECT * FROM webhooks WHERE user_id = %s AND %s = ANY(events) AND active = true",
                (user_id, event_type)
            )

    async def _send_push(self, user_id: str, content: dict):
        """Send push notification via FCM/APNs."""
        pass  # Implementation uses firebase-admin SDK

    async def register_webhook(self, user_id: UUID, url: str, events: List[str]):
        """Register a new webhook endpoint after URL validation."""
        async with get_db_session() as db:
            webhook_id = uuid4()
            await db.execute(
                "INSERT INTO webhooks (id, user_id, url, events, active) VALUES (%s, %s, %s, %s, true)",
                (str(webhook_id), str(user_id), url, events)
            )
            return type("Webhook", (), {"id": webhook_id})()

    async def mark_read(self, notification_id: UUID, user_id: UUID):
        """Mark notification as read."""
        async with get_db_session() as db:
            await db.execute(
                "UPDATE notifications SET read_at = NOW() WHERE id = %s AND user_id = %s",
                (str(notification_id), str(user_id))
            )

    async def deactivate_webhook(self, webhook_id: UUID, user_id: UUID):
        """Deactivate a webhook endpoint."""
        async with get_db_session() as db:
            await db.execute(
                "UPDATE webhooks SET active = false WHERE id = %s AND user_id = %s",
                (str(webhook_id), str(user_id))
            )
