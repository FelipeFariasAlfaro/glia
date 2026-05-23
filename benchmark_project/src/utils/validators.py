"""
Input Validation Utilities.

Provides validation functions for user input across the application.
Validation errors raise ValueError with descriptive messages.

These validators are used by API routes before passing data to services.
They enforce business rules defined in config/constants.py.
"""

import re
from typing import List
from uuid import UUID

from src.config.constants import (
    PASSWORD_MIN_LENGTH, PASSWORD_REQUIRE_UPPERCASE,
    PASSWORD_REQUIRE_LOWERCASE, PASSWORD_REQUIRE_DIGIT,
    PASSWORD_REQUIRE_SPECIAL, MAX_ITEMS_PER_ORDER,
    MAX_QUANTITY_PER_ITEM
)


def validate_password_strength(password: str) -> None:
    """Validate password meets security requirements.
    
    Requirements (from constants.py):
    - Minimum 12 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character
    
    Raises ValueError with specific failure reason.
    """
    errors = []
    
    if len(password) < PASSWORD_MIN_LENGTH:
        errors.append(f"Password must be at least {PASSWORD_MIN_LENGTH} characters")
    
    if PASSWORD_REQUIRE_UPPERCASE and not re.search(r"[A-Z]", password):
        errors.append("Password must contain at least one uppercase letter")
    
    if PASSWORD_REQUIRE_LOWERCASE and not re.search(r"[a-z]", password):
        errors.append("Password must contain at least one lowercase letter")
    
    if PASSWORD_REQUIRE_DIGIT and not re.search(r"\d", password):
        errors.append("Password must contain at least one digit")
    
    if PASSWORD_REQUIRE_SPECIAL and not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        errors.append("Password must contain at least one special character")
    
    if errors:
        raise ValueError("; ".join(errors))


def validate_order_items(items: List[dict]) -> None:
    """Validate order items before processing.
    
    Checks:
    - At least one item in the order
    - No more than MAX_ITEMS_PER_ORDER items
    - Each item has valid product_id and quantity
    - Quantity within allowed range (1 to MAX_QUANTITY_PER_ITEM)
    """
    if not items:
        raise ValueError("Order must contain at least one item")
    
    if len(items) > MAX_ITEMS_PER_ORDER:
        raise ValueError(f"Order cannot exceed {MAX_ITEMS_PER_ORDER} items")
    
    for i, item in enumerate(items):
        if "product_id" not in item:
            raise ValueError(f"Item {i}: missing product_id")
        
        try:
            UUID(item["product_id"])
        except (ValueError, TypeError):
            raise ValueError(f"Item {i}: invalid product_id format")
        
        quantity = item.get("quantity", 0)
        if not isinstance(quantity, int) or quantity < 1:
            raise ValueError(f"Item {i}: quantity must be a positive integer")
        
        if quantity > MAX_QUANTITY_PER_ITEM:
            raise ValueError(f"Item {i}: quantity cannot exceed {MAX_QUANTITY_PER_ITEM}")


def validate_email(email: str) -> None:
    """Validate email format (basic regex check).
    
    Note: Full email validation is done by Pydantic's EmailStr type
    in the route models. This is a fallback for non-Pydantic contexts.
    """
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(pattern, email):
        raise ValueError(f"Invalid email format: {email}")


def validate_webhook_url(url: str) -> None:
    """Validate webhook URL meets security requirements.
    
    Requirements:
    - Must use HTTPS (no HTTP webhooks in production)
    - Must be a valid URL format
    - Cannot point to internal/private IP ranges
    - Maximum 500 characters
    """
    if len(url) > 500:
        raise ValueError("Webhook URL too long (max 500 characters)")
    
    if not url.startswith("https://"):
        raise ValueError("Webhook URL must use HTTPS")
    
    # Block internal IP ranges
    internal_patterns = [
        r"https?://localhost", r"https?://127\.", r"https?://10\.",
        r"https?://172\.(1[6-9]|2[0-9]|3[01])\.", r"https?://192\.168\."
    ]
    for pattern in internal_patterns:
        if re.match(pattern, url):
            raise ValueError("Webhook URL cannot point to internal addresses")


def validate_uuid(value: str, field_name: str = "id") -> UUID:
    """Validate and parse a UUID string."""
    try:
        return UUID(value)
    except (ValueError, TypeError):
        raise ValueError(f"Invalid {field_name}: must be a valid UUID")
