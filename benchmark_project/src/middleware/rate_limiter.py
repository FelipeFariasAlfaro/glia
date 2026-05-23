"""
Rate Limiting Middleware.

Implements sliding window rate limiting using Redis.
Applied as a decorator on route handlers.

CRITICAL DEPENDENCY:
Uses the SAME Redis connection pool as auth_service (sessions),
inventory_service (reservations), and notification_service (queues).
If Redis goes down, rate limiting fails OPEN (allows all requests)
to prevent total service outage. This is a deliberate trade-off:
we prefer potential abuse over complete unavailability.

However, this means a Redis outage simultaneously breaks:
1. Rate limiting (this module) - fails open
2. Session validation (auth_service) - fails closed (401 for all)
3. Inventory reservations (inventory_service) - fails closed (can't create orders)
4. Event publishing (order_service) - notifications stop

See docs/architecture.md for the Redis dependency analysis.
"""

import time
import functools
from typing import Optional

from fastapi import Request, HTTPException, status

from src.database.connection import get_redis
from src.config.settings import settings
from src.config.constants import RATE_LIMIT_DEFAULT


def rate_limit(max_requests: int = RATE_LIMIT_DEFAULT, window_seconds: int = 60):
    """Decorator for rate limiting API endpoints.
    
    Uses Redis sliding window counter per client IP.
    Falls back to allowing requests if Redis is unavailable (fail-open).
    
    Args:
        max_requests: Maximum requests allowed in the window.
        window_seconds: Time window in seconds.
    
    Example:
        @rate_limit(max_requests=5, window_seconds=60)
        async def login(request: LoginRequest):
            ...
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            if not settings.RATE_LIMIT_ENABLED:
                return await func(*args, **kwargs)
            
            # Extract request from args/kwargs
            request = _extract_request(args, kwargs)
            if not request:
                return await func(*args, **kwargs)
            
            client_ip = _get_client_ip(request)
            endpoint = request.url.path
            
            try:
                is_limited = await _check_rate_limit(
                    client_ip, endpoint, max_requests, window_seconds
                )
                if is_limited:
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail="Rate limit exceeded. Try again later.",
                        headers={"Retry-After": str(window_seconds)}
                    )
            except HTTPException:
                raise
            except Exception:
                # Redis unavailable - fail open (allow request)
                # This is intentional: prefer availability over rate limiting
                pass
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


async def _check_rate_limit(
    client_ip: str, endpoint: str, max_requests: int, window_seconds: int
) -> bool:
    """Check if client has exceeded rate limit using sliding window.
    
    Implementation: Redis sorted set with timestamps as scores.
    - Add current timestamp
    - Remove entries older than window
    - Count remaining entries
    
    This gives accurate sliding window behavior (not fixed windows).
    """
    redis = get_redis()
    key = f"ratelimit:{endpoint}:{client_ip}"
    now = time.time()
    window_start = now - window_seconds
    
    pipe = redis.pipeline()
    # Remove old entries outside the window
    pipe.zremrangebyscore(key, 0, window_start)
    # Add current request
    pipe.zadd(key, {str(now): now})
    # Count requests in window
    pipe.zcard(key)
    # Set expiry on the key (cleanup)
    pipe.expire(key, window_seconds + 1)
    
    results = await pipe.execute()
    request_count = results[2]
    
    return request_count > max_requests


def _get_client_ip(request: Request) -> str:
    """Extract client IP, respecting X-Forwarded-For behind proxy.
    
    In production, we're behind a load balancer so the real IP
    is in X-Forwarded-For. We trust the first IP in the chain.
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _extract_request(args, kwargs) -> Optional[Request]:
    """Extract FastAPI Request object from function arguments."""
    for arg in args:
        if isinstance(arg, Request):
            return arg
    return kwargs.get("request")
