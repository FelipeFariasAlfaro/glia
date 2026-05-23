"""
Background Email Processing Worker.

Consumes email jobs from Redis queue and sends via SMTP.
Runs as a separate process (Celery worker or standalone consumer).

ARCHITECTURE:
- Reads from Redis list 'email_queue' (populated by notification_service)
- Processes emails one at a time with retry on failure
- Dead letter queue for permanently failed emails
- Rate limited to prevent SMTP provider throttling

DEPENDENCIES:
- Redis (same pool as everything else - see connection.py)
- SMTP server (configured in settings.py)
- notification_service (produces the queue items)

FLOW:
1. notification_service handles an event (e.g., order.created)
2. notification_service pushes email job to Redis 'email_queue'
3. This worker pops jobs and sends emails via SMTP
4. Failed emails are retried up to 3 times with exponential backoff
5. After 3 failures, moved to 'email_dead_letter' queue for manual review
"""

import json
import asyncio
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Optional

from src.database.connection import get_redis, get_db_session
from src.config.settings import settings


MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 5  # seconds: 5, 25, 125


class EmailWorker:
    """Processes email queue with retry logic and dead letter handling."""

    def __init__(self):
        self.redis = get_redis()
        self.running = False

    async def start(self):
        """Start the email worker loop.
        
        Blocks indefinitely, processing emails as they arrive.
        Uses BRPOP for efficient blocking wait (no polling).
        """
        self.running = True
        print(f"[EmailWorker] Started at {datetime.utcnow().isoformat()}")
        
        while self.running:
            try:
                # Blocking pop - waits up to 5 seconds for new job
                result = await self.redis.brpop("email_queue", timeout=5)
                if result:
                    _, job_data = result
                    job = json.loads(job_data)
                    await self._process_job(job)
            except Exception as e:
                print(f"[EmailWorker] Error in main loop: {e}")
                await asyncio.sleep(1)

    async def _process_job(self, job: dict):
        """Process a single email job with retry logic.
        
        Job format: {user_id, content: {subject, body}, queued_at, attempt?}
        """
        attempt = job.get("attempt", 0)
        
        try:
            user_email = await self._get_user_email(job["user_id"])
            if not user_email:
                print(f"[EmailWorker] User {job['user_id']} not found, discarding")
                return
            
            await self._send_email(
                to=user_email,
                subject=job["content"]["subject"],
                body=job["content"]["body"]
            )
            print(f"[EmailWorker] Sent email to {user_email}: {job['content']['subject']}")
            
        except Exception as e:
            attempt += 1
            if attempt >= MAX_RETRIES:
                # Move to dead letter queue
                await self.redis.lpush("email_dead_letter", json.dumps({
                    **job, "error": str(e), "failed_at": datetime.utcnow().isoformat()
                }))
                print(f"[EmailWorker] Moved to dead letter after {MAX_RETRIES} failures: {e}")
            else:
                # Retry with backoff
                job["attempt"] = attempt
                backoff = RETRY_BACKOFF_BASE ** attempt
                await asyncio.sleep(backoff)
                await self.redis.lpush("email_queue", json.dumps(job))
                print(f"[EmailWorker] Retry {attempt}/{MAX_RETRIES} after {backoff}s: {e}")

    async def _send_email(self, to: str, subject: str, body: str):
        """Send email via SMTP.
        
        Uses TLS connection to SMTP server configured in settings.
        Raises exception on failure for retry handling.
        """
        msg = MIMEMultipart()
        msg["From"] = settings.EMAIL_FROM
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "html"))
        
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            if settings.SMTP_USER:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)

    async def _get_user_email(self, user_id: str) -> Optional[str]:
        """Look up user email from database."""
        async with get_db_session() as db:
            result = await db.fetchval(
                "SELECT email FROM users WHERE id = $1", user_id
            )
            return result

    def stop(self):
        """Gracefully stop the worker."""
        self.running = False
        print("[EmailWorker] Stopping...")


async def main():
    """Entry point for running email worker as standalone process."""
    from src.database.connection import init_redis_pool, init_pg_pool
    await init_redis_pool()
    await init_pg_pool()
    
    worker = EmailWorker()
    try:
        await worker.start()
    except KeyboardInterrupt:
        worker.stop()


if __name__ == "__main__":
    asyncio.run(main())
