"""
Cryptographic Utilities.

Provides password hashing, token signing/verification, and encryption.
Uses industry-standard algorithms: bcrypt for passwords, RS256 for JWTs.

CRITICAL SECURITY HISTORY:
- March 2024 Token Leak Incident:
  This module previously used AES-CBC with a DETERMINISTIC IV for encrypting
  tokens at rest in Redis. The IV was derived from the token's session_id,
  meaning the same session always produced the same ciphertext. An attacker
  who gained read access to Redis could correlate encrypted tokens across
  time and eventually recover plaintext through a chosen-plaintext attack.
  
  FIX: Switched to random IV generation (os.urandom(16)) for each encryption.
  All existing encrypted tokens were invalidated and users forced to re-login.
  See docs/incidents/2024-03-token-leak.md for full post-mortem.

- The deterministic IV bug was introduced in commit abc123 when we added
  "token encryption at rest" as a security improvement. Ironic.
"""

import os
import jwt
import bcrypt
import hashlib
import hmac
from typing import Dict, Any
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend


def hash_password(password: str) -> str:
    """Hash password using bcrypt with cost factor 12.
    
    Cost factor 12 provides ~250ms hashing time on modern hardware.
    This is intentionally slow to resist brute-force attacks.
    """
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Verify password against bcrypt hash.
    
    Uses constant-time comparison to prevent timing attacks.
    """
    return bcrypt.checkpw(
        password.encode("utf-8"),
        password_hash.encode("utf-8")
    )


def sign_token(payload: Dict[str, Any], private_key: str) -> str:
    """Sign a JWT token using RS256 (asymmetric).
    
    RS256 was chosen over HS256 because:
    - Services only need the public key to verify (not the signing key)
    - Key rotation is simpler (only private key holder needs to update)
    - Compromised verifier can't forge tokens
    See ADR-001 for full rationale.
    """
    return jwt.encode(payload, private_key, algorithm="RS256")


def verify_token_signature(token: str, public_key: str) -> Dict[str, Any]:
    """Verify JWT signature and decode payload.
    
    Raises jwt.InvalidTokenError if signature is invalid or token expired.
    Only the public key is needed for verification (RS256 advantage).
    """
    return jwt.decode(token, public_key, algorithms=["RS256"])


def encrypt_at_rest(data: bytes, key: bytes) -> bytes:
    """Encrypt data for storage using AES-256-CBC with RANDOM IV.
    
    IMPORTANT: IV is randomly generated for EACH encryption operation.
    The IV is prepended to the ciphertext (first 16 bytes).
    
    HISTORY: Previously used deterministic IV derived from content hash.
    This was the root cause of the March 2024 token leak. NEVER use
    deterministic IVs - they leak information about plaintext equality.
    """
    # FIXED: Random IV (was previously: iv = hashlib.md5(session_id).digest())
    iv = os.urandom(16)  # Cryptographically random - NEVER deterministic
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    # Pad data to AES block size
    pad_length = 16 - (len(data) % 16)
    padded = data + bytes([pad_length] * pad_length)
    ciphertext = encryptor.update(padded) + encryptor.finalize()
    return iv + ciphertext  # Prepend IV for decryption


def decrypt_at_rest(encrypted: bytes, key: bytes) -> bytes:
    """Decrypt AES-256-CBC encrypted data.
    
    Expects IV as first 16 bytes of input (prepended during encryption).
    """
    iv = encrypted[:16]
    ciphertext = encrypted[16:]
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()
    pad_length = padded[-1]
    return padded[:-pad_length]


def generate_hmac(data: str, secret: str) -> str:
    """Generate HMAC-SHA256 for webhook signature verification."""
    return hmac.new(
        secret.encode("utf-8"),
        data.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()


def constant_time_compare(a: str, b: str) -> bool:
    """Constant-time string comparison to prevent timing attacks.
    
    Used for comparing tokens, signatures, and other secrets.
    Standard == comparison leaks information about which character differs.
    """
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))
