"""
Authentication module - JWT token management.
"""

import os
import time
import hashlib
import hmac
import json
import base64
from functools import wraps
from flask import request, jsonify

SECRET_KEY = os.environ.get("JWT_SECRET", "dev-secret-change-in-production")
TOKEN_EXPIRY = int(os.environ.get("TOKEN_EXPIRY_SECONDS", "3600"))


def generate_token(user_id: int, expires_in: int = None) -> str:
    """Generate a JWT-like token for the user."""
    expires_in = expires_in or TOKEN_EXPIRY
    payload = {
        "user_id": user_id,
        "exp": time.time() + expires_in,  # BUG: was using milliseconds before fix
        "iat": time.time(),
    }
    payload_bytes = base64.b64encode(json.dumps(payload).encode())
    signature = hmac.new(
        SECRET_KEY.encode(), payload_bytes, hashlib.sha256
    ).hexdigest()
    return f"{payload_bytes.decode()}.{signature}"


def verify_token(token: str) -> dict | None:
    """Verify and decode a token. Returns payload or None if invalid."""
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None

        payload_bytes = parts[0].encode()
        signature = parts[1]

        expected_sig = hmac.new(
            SECRET_KEY.encode(), payload_bytes, hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(signature, expected_sig):
            return None

        payload = json.loads(base64.b64decode(payload_bytes))

        # Check expiration
        if payload.get("exp", 0) < time.time():
            return None

        return payload
    except Exception:
        return None


def require_auth(f):
    """Decorator that requires a valid auth token."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing authorization token"}), 401

        token = auth_header.split(" ")[1]
        payload = verify_token(token)

        if not payload:
            return jsonify({"error": "Invalid or expired token"}), 401

        from database import get_db
        db = get_db()
        current_user = db.find_user_by_id(payload["user_id"])

        if not current_user:
            return jsonify({"error": "User not found"}), 401

        return f(current_user, *args, **kwargs)
    return decorated
