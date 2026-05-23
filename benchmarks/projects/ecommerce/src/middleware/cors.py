"""
CORS (Cross-Origin Resource Sharing) Configuration.

Configures allowed origins, methods, and headers for cross-origin requests.
Settings vary by environment:
- Development: permissive (localhost origins)
- Staging: restricted to staging domains
- Production: strict whitelist of production domains

SECURITY NOTE:
- Credentials (cookies, auth headers) are only allowed for whitelisted origins.
- Wildcard (*) is never used in production.
- Preflight responses are cached for 1 hour to reduce OPTIONS requests.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config.settings import settings


# Origin whitelist per environment
CORS_ORIGINS = {
    "development": [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
    ],
    "staging": [
        "https://staging.example.com",
        "https://admin-staging.example.com",
    ],
    "production": [
        "https://www.example.com",
        "https://admin.example.com",
        "https://app.example.com",
    ]
}


def configure_cors(app: FastAPI) -> None:
    """Apply CORS middleware with environment-appropriate settings.
    
    In production:
    - Only whitelisted origins are allowed
    - Credentials are enabled (for cookie-based auth on web)
    - Exposed headers include pagination metadata
    
    In development:
    - All localhost origins are allowed
    - More permissive for easier local development
    """
    origins = CORS_ORIGINS.get(settings.ENVIRONMENT, CORS_ORIGINS["production"])
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-Refresh-Token",
            "X-Idempotency-Key",
            "X-Request-ID",
        ],
        expose_headers=[
            "X-Total-Count",
            "X-Page-Count",
            "X-Rate-Limit-Remaining",
            "X-Rate-Limit-Reset",
        ],
        max_age=3600,  # Cache preflight for 1 hour
    )
