"""
Database Connection Pool Management.

Manages two connection pools:
1. PostgreSQL (primary data store) - via asyncpg
2. Redis (cache, sessions, rate limiting, events) - via aioredis

CRITICAL SHARED DEPENDENCY:
The Redis connection pool is shared across multiple subsystems:
- Session storage (auth_service)
- Rate limiting (rate_limiter middleware)
- Event pub/sub (order_service, payment_service, notification_service)
- Inventory reservations (inventory_service)
- Email/webhook queues (workers)

If Redis goes down, ALL of these break simultaneously. This is a known
single point of failure documented in the architecture decisions.
A Redis Sentinel setup is used in production for high availability.

PostgreSQL uses connection pooling with min=5, max=20 connections.
Connections are health-checked every 30 seconds.
"""

import asyncpg
import aioredis
from contextlib import asynccontextmanager
from typing import Optional

from src.config.settings import settings


# Module-level connection pools (initialized on first use)
_pg_pool: Optional[asyncpg.Pool] = None
_redis_pool: Optional[aioredis.Redis] = None


async def init_pg_pool():
    """Initialize PostgreSQL connection pool.
    
    Pool settings:
    - min_size: 5 (keep warm connections ready)
    - max_size: 20 (prevent connection exhaustion)
    - max_inactive_connection_lifetime: 300s
    - command_timeout: 30s (prevent long-running queries from blocking)
    """
    global _pg_pool
    _pg_pool = await asyncpg.create_pool(
        dsn=settings.DATABASE_URL,
        min_size=settings.DB_POOL_MIN,
        max_size=settings.DB_POOL_MAX,
        max_inactive_connection_lifetime=300,
        command_timeout=30
    )
    return _pg_pool


async def init_redis_pool():
    """Initialize Redis connection pool.
    
    IMPORTANT: This single pool is used by:
    - auth_service (sessions, token blacklist)
    - rate_limiter (request counting)
    - inventory_service (reservations)
    - notification_service (rate limits, queues)
    - order_service (event publishing)
    - payment_service (idempotency keys)
    
    Redis Sentinel is used in production for failover.
    In development, connects to a single Redis instance.
    """
    global _redis_pool
    if settings.ENVIRONMENT == "production":
        sentinel = aioredis.Sentinel(
            settings.REDIS_SENTINELS,
            password=settings.REDIS_PASSWORD
        )
        _redis_pool = sentinel.master_for("mymaster")
    else:
        _redis_pool = aioredis.from_url(
            settings.REDIS_URL,
            max_connections=settings.REDIS_POOL_SIZE,
            decode_responses=True
        )
    return _redis_pool


def get_redis() -> aioredis.Redis:
    """Get the shared Redis connection pool.
    
    WARNING: This is the SAME pool used by rate_limiter, auth sessions,
    inventory reservations, and event pub/sub. If you need isolation,
    consider a separate Redis instance.
    """
    if _redis_pool is None:
        raise RuntimeError("Redis pool not initialized. Call init_redis_pool() first.")
    return _redis_pool


@asynccontextmanager
async def get_db_session():
    """Get a PostgreSQL connection from the pool.
    
    Usage:
        async with get_db_session() as db:
            result = await db.fetch("SELECT * FROM users WHERE id = $1", user_id)
    
    Connection is automatically returned to pool on exit.
    Transactions must be explicitly managed with db.transaction().
    """
    if _pg_pool is None:
        raise RuntimeError("PostgreSQL pool not initialized. Call init_pg_pool() first.")
    async with _pg_pool.acquire() as conn:
        yield conn


async def close_pools():
    """Gracefully close all connection pools on shutdown."""
    global _pg_pool, _redis_pool
    if _pg_pool:
        await _pg_pool.close()
        _pg_pool = None
    if _redis_pool:
        await _redis_pool.close()
        _redis_pool = None


async def health_check() -> dict:
    """Check connectivity to both PostgreSQL and Redis.
    
    Returns status dict used by /health endpoint.
    If either is unhealthy, the service should be marked as degraded.
    """
    status = {"postgresql": "unknown", "redis": "unknown"}
    try:
        async with get_db_session() as db:
            await db.fetchval("SELECT 1")
        status["postgresql"] = "healthy"
    except Exception as e:
        status["postgresql"] = f"unhealthy: {str(e)}"
    
    try:
        redis = get_redis()
        await redis.ping()
        status["redis"] = "healthy"
    except Exception as e:
        status["redis"] = f"unhealthy: {str(e)}"
    
    return status
