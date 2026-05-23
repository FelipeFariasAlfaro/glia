"""
Business Rules and Constants.

Centralized configuration for business logic parameters.
These values are referenced across multiple services.

IMPORTANT: Changes here affect multiple services. Review impact before modifying:
- TOKEN_EXPIRY_* → auth_service, auth routes
- ORDER_* → order_service, inventory_service
- RATE_LIMIT_* → rate_limiter middleware, notification_service
- STOCK_* → inventory_service, product routes
- PAYMENT_* → payment_service, order_service
- WEBHOOK_* → webhook_worker, notification_service
"""

# ============================================================
# Authentication & Sessions
# ============================================================

# JWT token expiry (seconds)
TOKEN_EXPIRY_ACCESS = 900  # 15 minutes (reduced from 3600 after March 2024 incident)
TOKEN_EXPIRY_REFRESH = 604800  # 7 days

# Session management
MAX_SESSIONS_PER_USER = 5  # Max concurrent sessions before oldest is evicted
SESSION_INACTIVITY_TIMEOUT = 1800  # 30 minutes of inactivity → session expired

# Account security
MAX_FAILED_LOGIN_ATTEMPTS = 5  # Lock account after this many failures
ACCOUNT_LOCKOUT_DURATION = 900  # 15 minutes lockout

# Password requirements
PASSWORD_MIN_LENGTH = 12
PASSWORD_REQUIRE_UPPERCASE = True
PASSWORD_REQUIRE_LOWERCASE = True
PASSWORD_REQUIRE_DIGIT = True
PASSWORD_REQUIRE_SPECIAL = True

# ============================================================
# Orders & Inventory
# ============================================================

# Reservation TTL - how long inventory is held before auto-release
ORDER_RESERVATION_TTL = 900  # 15 minutes
STOCK_RESERVATION_TTL_SECONDS = 900  # Same as above (used by inventory_service)

# Low stock threshold - triggers alert when available stock drops below this
LOW_STOCK_THRESHOLD = 10

# Order limits
MAX_ITEMS_PER_ORDER = 50
MAX_QUANTITY_PER_ITEM = 100

# Tax rate (simplified - real implementation would use tax service)
DEFAULT_TAX_RATE = 0.08  # 8%

# ============================================================
# Payments
# ============================================================

# How long a payment authorization is valid before it must be captured
PAYMENT_CAPTURE_WINDOW_HOURS = 72  # 3 days (Stripe allows up to 7)

# Refund processing
REFUND_PROCESSING_DAYS = 5  # Typical refund processing time

# ============================================================
# Rate Limiting
# ============================================================

# API rate limits (requests per window)
RATE_LIMIT_DEFAULT = 100  # per minute
RATE_LIMIT_AUTH = 5  # login attempts per minute
RATE_LIMIT_REGISTER = 3  # registrations per 5 minutes

# Notification rate limits (per hour)
EMAIL_RATE_LIMIT = 10
PUSH_RATE_LIMIT = 30
WEBHOOK_RATE_LIMIT = 100

# ============================================================
# Webhooks
# ============================================================

# Retry configuration for webhook delivery
WEBHOOK_MAX_RETRIES = 5
WEBHOOK_BACKOFF_BASE = 2  # Exponential backoff: 2^attempt seconds
WEBHOOK_TIMEOUT_SECONDS = 10  # Max time to wait for webhook response

# ============================================================
# Caching
# ============================================================

# Redis cache TTLs (seconds)
CACHE_PRODUCT_LIST_TTL = 300  # 5 minutes
CACHE_PRODUCT_DETAIL_TTL = 60  # 1 minute (shorter due to stock changes)
CACHE_USER_PREFERENCES_TTL = 600  # 10 minutes
