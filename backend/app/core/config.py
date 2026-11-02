"""
Credence Core — Application Configuration
Provides environment-aware configuration profiles, secret validation,
session security defaults, and storage path resolution.
"""

import os
import secrets
import datetime
import logging

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DATA_DIR = os.environ.get("DATA_DIR", BASE_DIR)
LOG_DIR = os.environ.get("LOG_DIR", os.path.join(BASE_DIR, "logs"))

KNOWN_INSECURE_KEYS = {
    "CREDENCE_CORE_ENTERPRISE_SECRET_KEY_PROD_2026",
    "change-me-to-a-secure-cryptographic-random-key-in-production",
    "change-me",
    "secret",
    "secret_key",
    "password",
    "123456",
    "DEV_SECRET_KEY_FOR_LOCAL_DEBUGGING_ONLY",
    "credence_fallback_secret_key_prod_32chars",
    "default",
}


class BaseConfig:
    """Base configuration common to all environments."""
    FLASK_ENV = os.environ.get("FLASK_ENV", "development").lower()
    SECRET_KEY = os.environ.get("SECRET_KEY", "")
    DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
    REDIS_URL = os.environ.get("REDIS_URL", "").strip()

    # Configured demo accounts allowed for demo login (must be explicitly provisioned)
    # Default to "40273146502136" in non-production environments if not explicitly configured
    _raw_demo = os.environ.get("CONFIGURED_DEMO_ACCOUNTS", "").strip()
    if _raw_demo:
        CONFIGURED_DEMO_ACCOUNTS = set(acc.strip() for acc in _raw_demo.split(",") if acc.strip())
    elif os.environ.get("FLASK_ENV", "development").lower() != "production":
        CONFIGURED_DEMO_ACCOUNTS = {"40273146502136"}
    else:
        CONFIGURED_DEMO_ACCOUNTS = set()

    # MFA secret encryption key (dedicated)
    MFA_ENCRYPTION_KEY = os.environ.get("MFA_ENCRYPTION_KEY", "")

    # Session cookie hardening
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "false").lower() in ("true", "1", "yes") or (
        os.environ.get("HTTPS") == "on" or os.environ.get("FLASK_ENV") == "production"
    )
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024  # 2MB ceiling
    PERMANENT_SESSION_LIFETIME = datetime.timedelta(minutes=30)

    # CORS Whitelist
    _origins = os.environ.get("CORS_TRUSTED_ORIGINS", "")
    if _origins:
        CORS_TRUSTED_ORIGINS = [o.strip() for o in _origins.split(",") if o.strip()]
    else:
        CORS_TRUSTED_ORIGINS = [
            "http://localhost:5000",
            "http://127.0.0.1:5000",
            "https://credence.bank",
            "https://credence-core.onrender.com",
        ]

    # Rate limiting parameters
    RATE_LIMIT_LOGIN_MAX = int(os.environ.get("RATE_LIMIT_LOGIN_MAX", 5))
    RATE_LIMIT_LOGIN_WINDOW = int(os.environ.get("RATE_LIMIT_LOGIN_WINDOW", 60))
    RATE_LIMIT_API_MAX = int(os.environ.get("RATE_LIMIT_API_MAX", 60))
    RATE_LIMIT_API_WINDOW = int(os.environ.get("RATE_LIMIT_API_WINDOW", 60))

    # Storage paths
    BASE_DIR = BASE_DIR
    DATA_DIR = DATA_DIR
    LOG_DIR = LOG_DIR
    PROFILES_JSON = os.path.join(DATA_DIR, "user_profiles.json")
    BANK_DATA_JSON = os.path.join(DATA_DIR, "bank_data.json")
    INVESTMENTS_JSON = os.path.join(DATA_DIR, "user_investments.json")


class DevelopmentConfig(BaseConfig):
    """Local development profile."""
    DEBUG = True
    TESTING = False
    SESSION_COOKIE_SECURE = False
    # Local fallback secret key if not set in environment
    SECRET_KEY = os.environ.get("SECRET_KEY") or "dev_ephemeral_key_for_local_debugging_only"


class TestingConfig(BaseConfig):
    """Automated test execution profile."""
    DEBUG = False
    TESTING = True
    SESSION_COOKIE_SECURE = False
    DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")
    SECRET_KEY = os.environ.get("SECRET_KEY") or "test_ephemeral_key_for_automated_testing_suite_only"


class ProductionConfig(BaseConfig):
    """Hardened production deployment profile."""
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True

    @classmethod
    def validate_secrets(cls):
        """Enforce strict secret safety in production. Startup must fail if missing or weak."""
        secret = (cls.SECRET_KEY or "").strip()
        if not secret:
            raise RuntimeError(
                "FATAL: Insecure SECRET_KEY configuration. Production startup aborted: "
                "SECRET_KEY environment variable is missing. Set a cryptographically strong key."
            )
        if secret in KNOWN_INSECURE_KEYS or len(secret) < 32:
            raise RuntimeError(
                "FATAL: Insecure SECRET_KEY configuration. Production startup aborted: "
                "The configured SECRET_KEY is too short or is a known insecure default. "
                "Must be a unique cryptographically random secret of at least 32 characters."
            )

        mfa_key = (cls.MFA_ENCRYPTION_KEY or os.environ.get("MFA_ENCRYPTION_KEY", "")).strip()
        if not mfa_key:
            raise RuntimeError(
                "FATAL: Insecure MFA_ENCRYPTION_KEY configuration. Production startup aborted: "
                "MFA_ENCRYPTION_KEY environment variable is missing. Set a dedicated 256-bit key."
            )
        if mfa_key in KNOWN_INSECURE_KEYS or len(mfa_key) < 32:
            raise RuntimeError(
                "FATAL: Insecure MFA_ENCRYPTION_KEY configuration. Production startup aborted: "
                "The configured MFA_ENCRYPTION_KEY is too short or is a known insecure default. "
                "Must be a unique cryptographically random secret of at least 32 characters."
            )
        if mfa_key == secret:
            raise RuntimeError(
                "FATAL: MFA_ENCRYPTION_KEY must be distinct from SECRET_KEY. Reusing keys is prohibited."
            )

        db_url = (cls.DATABASE_URL or os.environ.get("DATABASE_URL", "")).strip()
        if not db_url.startswith("postgresql://") and not db_url.startswith("postgres://"):
            raise RuntimeError(
                "FATAL: Production database must use PostgreSQL. SQLite is strictly forbidden in production."
            )


def get_config(env_name: str = None) -> type:
    """Return appropriate configuration class based on environment."""
    env = (env_name or os.environ.get("FLASK_ENV", "development")).lower()
    if env == "production":
        ProductionConfig.validate_secrets()
        return ProductionConfig
    elif env == "testing":
        return TestingConfig
    return DevelopmentConfig


# Active config resolved dynamically
Config = get_config()
