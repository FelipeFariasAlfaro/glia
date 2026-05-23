"""
User Model.

Defines user entity with role-based access control (RBAC).
Roles: customer, admin, support. Permissions are derived from role.

SECURITY:
- Passwords stored as bcrypt hashes (cost factor 12).
- Email is unique and indexed for fast lookup during authentication.
- Last login tracking for security audit trail.
- Account lockout after 5 failed attempts (tracked in Redis, not here).
"""

from uuid import UUID, uuid4
from datetime import datetime
from enum import Enum
from typing import List, Optional
from dataclasses import dataclass, field


class UserRole(Enum):
    CUSTOMER = "customer"
    ADMIN = "admin"
    SUPPORT = "support"


# Permission matrix - determines what each role can do
ROLE_PERMISSIONS = {
    UserRole.CUSTOMER: [
        "order:create", "order:read_own", "order:cancel_own",
        "product:read", "notification:read_own", "notification:update_own"
    ],
    UserRole.ADMIN: [
        "order:create", "order:read_all", "order:update_status", "order:cancel_any",
        "product:create", "product:read", "product:update", "product:delete",
        "user:read_all", "user:update_role",
        "notification:read_all", "notification:send"
    ],
    UserRole.SUPPORT: [
        "order:read_all", "order:update_status",
        "product:read", "user:read_all",
        "notification:read_all", "notification:send"
    ]
}


@dataclass
class User:
    """User entity with authentication and authorization data.
    
    The password_hash field uses bcrypt with cost factor 12.
    Token rotation tracking (token_version) was added after the March 2024
    token leak incident to allow mass-invalidation of all tokens for a user.
    """
    id: UUID = field(default_factory=uuid4)
    email: str = ""
    full_name: str = ""
    password_hash: str = ""
    role: str = UserRole.CUSTOMER.value
    is_active: bool = True
    token_version: int = 0  # Incremented to invalidate all tokens (post-incident addition)
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_login: Optional[datetime] = None
    failed_login_attempts: int = 0
    locked_until: Optional[datetime] = None

    def has_permission(self, permission: str) -> bool:
        """Check if user's role grants a specific permission."""
        role_enum = UserRole(self.role)
        return permission in ROLE_PERMISSIONS.get(role_enum, [])

    def can_access_order(self, order_user_id: UUID) -> bool:
        """Check if user can access a specific order."""
        if self.has_permission("order:read_all"):
            return True
        return self.id == order_user_id and self.has_permission("order:read_own")

    def increment_token_version(self):
        """Invalidate all existing tokens for this user.
        
        Used when token theft is detected (refresh token reuse).
        All tokens with version < current are rejected.
        """
        self.token_version += 1

    def to_dict(self, include_sensitive: bool = False) -> dict:
        """Serialize user, optionally excluding sensitive fields."""
        data = {
            "id": str(self.id), "email": self.email,
            "full_name": self.full_name, "role": self.role,
            "is_active": self.is_active, "created_at": self.created_at.isoformat()
        }
        if include_sensitive:
            data["token_version"] = self.token_version
            data["last_login"] = self.last_login.isoformat() if self.last_login else None
        return data
