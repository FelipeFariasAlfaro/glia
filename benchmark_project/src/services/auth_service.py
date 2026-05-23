"""
Authentication Service.

Handles JWT token management with RS256 signing, session management,
and token rotation. Uses Redis for session storage and token blacklisting.

IMPORTANT: This service shares the Redis connection pool with rate_limiter.
If Redis goes down, both authentication sessions AND rate limiting break.
This is a known coupling documented in ADR-002.

HISTORY:
- March 2024: Token leak incident caused by crypto.py using deterministic IV
  for token encryption at rest. Tokens stored in Redis were recoverable.
  Fix: switched to random IV generation in crypto.py, rotated all keys.
"""

import jwt
import time
from uuid import UUID, uuid4
from typing import Optional, Dict

from src.utils.crypto import sign_token, verify_token_signature, hash_password, verify_password
from src.database.connection import get_redis, get_db_session
from src.models.user import User
from src.config.settings import settings
from src.config.constants import TOKEN_EXPIRY_ACCESS, TOKEN_EXPIRY_REFRESH


class AuthService:
    """Manages authentication, sessions, and token lifecycle."""

    def __init__(self):
        self.redis = get_redis()  # Same pool as rate_limiter - shared dependency
        self._private_key = settings.JWT_PRIVATE_KEY
        self._public_key = settings.JWT_PUBLIC_KEY

    async def authenticate(self, email: str, password: str) -> Optional[User]:
        """Verify credentials and return user if valid.
        
        Uses bcrypt with cost factor 12 for password verification.
        Timing-safe comparison to prevent timing attacks.
        """
        async with get_db_session() as db:
            user = await db.query(User).filter(User.email == email).first()
            if not user or not verify_password(password, user.password_hash):
                return None
            return user

    async def create_token_pair(self, user: User) -> Dict[str, str]:
        """Generate access + refresh token pair.
        
        Access token: 15 min expiry, contains user_id and role.
        Refresh token: 7 day expiry, stored in Redis for rotation tracking.
        Both signed with RS256 private key (see ADR-001 for rationale).
        """
        session_id = str(uuid4())
        access_payload = {
            "sub": str(user.id), "role": user.role,
            "session_id": session_id, "exp": time.time() + TOKEN_EXPIRY_ACCESS
        }
        refresh_payload = {
            "sub": str(user.id), "session_id": session_id,
            "exp": time.time() + TOKEN_EXPIRY_REFRESH, "type": "refresh"
        }
        access_token = sign_token(access_payload, self._private_key)
        refresh_token = sign_token(refresh_payload, self._private_key)
        # Store session in Redis for rotation detection
        await self.redis.setex(
            f"session:{session_id}", TOKEN_EXPIRY_REFRESH,
            f"{user.id}:{refresh_token[:16]}"
        )
        return {"access_token": access_token, "refresh_token": refresh_token, "expires_in": TOKEN_EXPIRY_ACCESS}

    async def rotate_tokens(self, refresh_token: str) -> Dict[str, str]:
        """Rotate refresh token (one-time use).
        
        If a used refresh token is presented again, it indicates potential theft.
        In that case, ALL sessions for the user are terminated immediately.
        This was added after the March 2024 token leak incident.
        """
        payload = verify_token_signature(refresh_token, self._public_key)
        session_id = payload["session_id"]
        stored = await self.redis.get(f"session:{session_id}")
        if not stored:
            # Token reuse detected - terminate all user sessions
            await self._terminate_all_sessions(payload["sub"])
            raise Exception("Token reuse detected - all sessions terminated")
        # Invalidate old session, create new token pair
        await self.redis.delete(f"session:{session_id}")
        async with get_db_session() as db:
            user = await db.get(User, UUID(payload["sub"]))
            return await self.create_token_pair(user)

    async def revoke_session(self, token: str):
        """Revoke a session by blacklisting the token until expiry."""
        payload = verify_token_signature(token, self._public_key)
        ttl = int(payload["exp"] - time.time())
        if ttl > 0:
            await self.redis.setex(f"blacklist:{token[:32]}", ttl, "1")
            await self.redis.delete(f"session:{payload['session_id']}")

    async def _terminate_all_sessions(self, user_id: str):
        """Emergency: kill all sessions for a user (token theft response)."""
        pattern = f"session:*"
        async for key in self.redis.scan_iter(pattern):
            val = await self.redis.get(key)
            if val and val.startswith(f"{user_id}:"):
                await self.redis.delete(key)
