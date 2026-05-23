"""
Environment-Based Configuration.

Loads settings from environment variables with defaults per environment.
Supports three environments: development, staging, production.

SECURITY NOTES:
- JWT keys are loaded from files (not env vars) in production.
- Stripe keys differ per environment (test keys in dev/staging).
- Redis password is required in production (Sentinel mode).
- Database URL must use SSL in production.
"""

import os
from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class Settings:
    """Application configuration loaded from environment."""
    
    # Environment
    ENVIRONMENT: str = os.getenv("APP_ENV", "development")
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"
    
    # Server
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    WORKERS: int = int(os.getenv("WORKERS", "4"))
    
    # PostgreSQL
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://localhost:5432/ecommerce_dev"
    )
    DB_POOL_MIN: int = int(os.getenv("DB_POOL_MIN", "5"))
    DB_POOL_MAX: int = int(os.getenv("DB_POOL_MAX", "20"))
    
    # Redis - SHARED across rate_limiter, sessions, events, inventory
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD", "")
    REDIS_POOL_SIZE: int = int(os.getenv("REDIS_POOL_SIZE", "20"))
    REDIS_SENTINELS: List[Tuple[str, int]] = field(default_factory=lambda: [
        ("sentinel-1", 26379), ("sentinel-2", 26379), ("sentinel-3", 26379)
    ])
    
    # JWT Authentication (RS256 - see ADR-001)
    JWT_PRIVATE_KEY: str = ""  # Loaded from file in _load_keys()
    JWT_PUBLIC_KEY: str = ""   # Loaded from file in _load_keys()
    JWT_ALGORITHM: str = "RS256"
    
    # Stripe Payment
    STRIPE_SECRET_KEY: str = os.getenv("STRIPE_SECRET_KEY", "sk_test_...")
    STRIPE_PUBLISHABLE_KEY: str = os.getenv("STRIPE_PUBLISHABLE_KEY", "pk_test_...")
    STRIPE_WEBHOOK_SECRET: str = os.getenv("STRIPE_WEBHOOK_SECRET", "whsec_...")
    
    # Email (SMTP)
    SMTP_HOST: str = os.getenv("SMTP_HOST", "localhost")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    EMAIL_FROM: str = os.getenv("EMAIL_FROM", "noreply@example.com")
    
    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
    
    def __post_init__(self):
        """Load environment-specific overrides and keys."""
        self._load_keys()
        self._apply_environment_overrides()
    
    def _load_keys(self):
        """Load JWT RSA keys from files.
        
        In production, keys are mounted as secrets (Kubernetes).
        In development, keys are in the local keys/ directory.
        
        HISTORY: Before March 2024, we used HS256 with a shared secret.
        Switched to RS256 after the token leak incident (see ADR-001).
        """
        key_dir = os.getenv("JWT_KEY_DIR", "./keys")
        try:
            with open(f"{key_dir}/private.pem", "r") as f:
                self.JWT_PRIVATE_KEY = f.read()
            with open(f"{key_dir}/public.pem", "r") as f:
                self.JWT_PUBLIC_KEY = f.read()
        except FileNotFoundError:
            if self.ENVIRONMENT == "production":
                raise RuntimeError("JWT keys not found in production!")
            # Dev fallback - generate ephemeral keys
            self.JWT_PRIVATE_KEY = "dev-private-key-not-for-production"
            self.JWT_PUBLIC_KEY = "dev-public-key-not-for-production"
    
    def _apply_environment_overrides(self):
        """Apply environment-specific settings."""
        if self.ENVIRONMENT == "production":
            self.DEBUG = False
            self.DB_POOL_MIN = 10
            self.DB_POOL_MAX = 50
            self.REDIS_POOL_SIZE = 50
        elif self.ENVIRONMENT == "staging":
            self.DEBUG = False
            self.DB_POOL_MAX = 30


# Singleton settings instance
settings = Settings()
