"""
Webhook Delivery Worker.

Delivers webhook payloads to registered endpoints with exponential backoff.
Runs as a separate background process consuming from Redis queue.

ARCHITECTURE:
- Consumes from Redis list 'webhook_queue' (populated by notification_service)
- Delivers HTTP POST to registered webhook URLs
- Retries with exponential backoff: 2^attempt seconds (max 5 retries)
- Signs payloads with HMAC-SHA256 for recipient verification
- Tracks delivery status for monitoring and alerting

RETRY STRATEGY:
- Attempt 1: immediate
- Attempt 2: after 2 seconds
- Attempt 3: after 4 seconds
- Attempt 4: after 8 seconds
- Attempt 5: after 16 seconds
- After 5 failures: webhook is deactivated, user is notified

SECURITY:
- Payloads are signed with per-webhook secret using HMAC-SHA256
- Signature is sent in X-Webhook-Signature header
- Recipients should verify signature before processing
"""

import json
import asyncio
import httpx
from datetime import datetime
from typing import Optional

from src.database.connection import get_redis, get_db_session
from src.utils.crypto import generate_hmac
from src.config.constants import (
    WEBHOOK_MAX_RETRIES, WEBHOOK_BACKOFF_BASE, WEBHOOK_TIMEOUT_SECONDS
)


class WebhookWorker:
    """Delivers webhooks with retry logic and signature verification."""

    def __init__(self):
        self.redis = get_redis()
        self.running = False
        self.http_client = httpx.AsyncClient(timeout=WEBHOOK_TIMEOUT_SECONDS)

    async def start(self):
        """Start the webhook delivery loop.
        
        Processes webhook jobs from Redis queue with blocking pop.
        Each delivery attempt is logged for monitoring.
        """
        self.running = True
        print(f"[WebhookWorker] Started at {datetime.utcnow().isoformat()}")
        
        while self.running:
            try:
                result = await self.redis.brpop("webhook_queue", timeout=5)
                if result:
                    _, job_data = result
                    job = json.loads(job_data)
                    await self._deliver(job)
            except Exception as e:
                print(f"[WebhookWorker] Error in main loop: {e}")
                await asyncio.sleep(1)

    async def _deliver(self, job: dict):
        """Attempt webhook delivery with retry on failure.
        
        Job format: {webhook_id, url, payload, attempt, max_retries}
        """
        attempt = job.get("attempt", 0)
        url = job["url"]
        payload = json.dumps(job["payload"])
        
        # Sign the payload
        webhook_secret = await self._get_webhook_secret(job["webhook_id"])
        signature = generate_hmac(payload, webhook_secret) if webhook_secret else ""
        
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Signature": f"sha256={signature}",
            "X-Webhook-ID": job["webhook_id"],
            "X-Delivery-Attempt": str(attempt + 1),
        }
        
        try:
            response = await self.http_client.post(url, content=payload, headers=headers)
            
            if response.status_code >= 200 and response.status_code < 300:
                await self._log_delivery(job["webhook_id"], "success", attempt + 1)
                print(f"[WebhookWorker] Delivered to {url} (attempt {attempt + 1})")
            else:
                raise Exception(f"HTTP {response.status_code}: {response.text[:100]}")
                
        except Exception as e:
            attempt += 1
            if attempt >= WEBHOOK_MAX_RETRIES:
                await self._handle_permanent_failure(job, str(e))
            else:
                # Retry with exponential backoff
                backoff = WEBHOOK_BACKOFF_BASE ** attempt
                job["attempt"] = attempt
                await asyncio.sleep(backoff)
                await self.redis.lpush("webhook_queue", json.dumps(job))
                print(f"[WebhookWorker] Retry {attempt}/{WEBHOOK_MAX_RETRIES} for {url}: {e}")

    async def _handle_permanent_failure(self, job: dict, error: str):
        """Handle webhook that failed all retry attempts.
        
        Actions:
        1. Deactivate the webhook endpoint
        2. Notify the user about the failure
        3. Log for monitoring/alerting
        """
        webhook_id = job["webhook_id"]
        
        # Deactivate webhook
        async with get_db_session() as db:
            await db.execute(
                "UPDATE webhooks SET active = false WHERE id = $1", webhook_id
            )
        
        # Notify user about webhook failure (via email, not webhook obviously)
        await self.redis.lpush("email_queue", json.dumps({
            "user_id": await self._get_webhook_owner(webhook_id),
            "content": {
                "subject": "Webhook Delivery Failed",
                "body": f"Your webhook endpoint {job['url']} has been deactivated "
                        f"after {WEBHOOK_MAX_RETRIES} failed delivery attempts. "
                        f"Last error: {error}"
            }
        }))
        
        await self._log_delivery(webhook_id, "permanent_failure", WEBHOOK_MAX_RETRIES)
        print(f"[WebhookWorker] Permanently failed: {job['url']} - {error}")

    async def _get_webhook_secret(self, webhook_id: str) -> Optional[str]:
        """Get the signing secret for a webhook endpoint."""
        async with get_db_session() as db:
            return await db.fetchval(
                "SELECT signing_secret FROM webhooks WHERE id = $1", webhook_id
            )

    async def _get_webhook_owner(self, webhook_id: str) -> Optional[str]:
        """Get the user_id who owns this webhook."""
        async with get_db_session() as db:
            return await db.fetchval(
                "SELECT user_id FROM webhooks WHERE id = $1", webhook_id
            )

    async def _log_delivery(self, webhook_id: str, status: str, attempts: int):
        """Log delivery attempt for monitoring."""
        async with get_db_session() as db:
            await db.execute(
                "INSERT INTO webhook_deliveries (webhook_id, status, attempts, delivered_at) "
                "VALUES ($1, $2, $3, NOW())",
                webhook_id, status, attempts
            )

    def stop(self):
        """Gracefully stop the worker."""
        self.running = False


async def main():
    """Entry point for running webhook worker as standalone process."""
    from src.database.connection import init_redis_pool, init_pg_pool
    await init_redis_pool()
    await init_pg_pool()
    
    worker = WebhookWorker()
    try:
        await worker.start()
    except KeyboardInterrupt:
        worker.stop()


if __name__ == "__main__":
    asyncio.run(main())
