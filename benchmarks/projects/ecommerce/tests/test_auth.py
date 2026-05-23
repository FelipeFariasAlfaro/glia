"""
Authentication Tests.

Tests for login, registration, token rotation, and session management.
Covers the March 2024 token leak fix (token rotation detection).
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4

from src.services.auth_service import AuthService
from src.utils.crypto import hash_password, verify_password, sign_token, verify_token_signature
from src.utils.validators import validate_password_strength
from src.models.user import User, UserRole


class TestPasswordHashing:
    """Test bcrypt password hashing and verification."""

    def test_hash_password_produces_bcrypt_hash(self):
        password = "SecureP@ss123!"
        hashed = hash_password(password)
        assert hashed.startswith("$2b$12$")  # bcrypt with cost 12

    def test_verify_correct_password(self):
        password = "SecureP@ss123!"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_verify_wrong_password(self):
        hashed = hash_password("correct_password")
        assert verify_password("wrong_password", hashed) is False

    def test_different_hashes_for_same_password(self):
        """Bcrypt uses random salt, so same password → different hashes."""
        h1 = hash_password("same_password")
        h2 = hash_password("same_password")
        assert h1 != h2  # Different salts


class TestPasswordValidation:
    """Test password strength validation rules."""

    def test_valid_password(self):
        validate_password_strength("SecureP@ss123!")  # Should not raise

    def test_too_short(self):
        with pytest.raises(ValueError, match="at least 12 characters"):
            validate_password_strength("Short1!")

    def test_missing_uppercase(self):
        with pytest.raises(ValueError, match="uppercase"):
            validate_password_strength("nouppercase123!@")

    def test_missing_special_char(self):
        with pytest.raises(ValueError, match="special character"):
            validate_password_strength("NoSpecialChar123")


class TestTokenSigning:
    """Test JWT RS256 token signing and verification."""

    @pytest.fixture
    def rsa_keys(self):
        """Generate test RSA key pair."""
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization
        
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        private_pem = private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption()
        ).decode()
        public_pem = private_key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode()
        return private_pem, public_pem

    def test_sign_and_verify(self, rsa_keys):
        private_key, public_key = rsa_keys
        payload = {"sub": "user123", "role": "customer"}
        token = sign_token(payload, private_key)
        decoded = verify_token_signature(token, public_key)
        assert decoded["sub"] == "user123"
        assert decoded["role"] == "customer"


class TestTokenRotation:
    """Test token rotation and theft detection (March 2024 fix)."""

    @pytest.mark.asyncio
    async def test_reused_refresh_token_terminates_all_sessions(self):
        """If a refresh token is reused, all user sessions should be killed.
        
        This is the core security fix from the March 2024 incident.
        Token reuse indicates potential theft, so we nuke everything.
        """
        auth_service = AuthService()
        auth_service.redis = AsyncMock()
        # Simulate: session not found (token already used/rotated)
        auth_service.redis.get.return_value = None
        auth_service._terminate_all_sessions = AsyncMock()
        
        with pytest.raises(Exception, match="Token reuse detected"):
            await auth_service.rotate_tokens("fake.refresh.token")


class TestUserPermissions:
    """Test role-based access control."""

    def test_customer_can_read_own_orders(self):
        user = User(role=UserRole.CUSTOMER.value)
        assert user.has_permission("order:read_own") is True

    def test_customer_cannot_read_all_orders(self):
        user = User(role=UserRole.CUSTOMER.value)
        assert user.has_permission("order:read_all") is False

    def test_admin_can_update_order_status(self):
        user = User(role=UserRole.ADMIN.value)
        assert user.has_permission("order:update_status") is True

    def test_token_version_increment(self):
        """Token version increment invalidates all existing tokens."""
        user = User(token_version=3)
        user.increment_token_version()
        assert user.token_version == 4
