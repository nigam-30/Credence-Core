"""
Credence Core — Enterprise Distributed Redis Client
Provides robust connection pooling, credential redaction, and strict production enforcement.
In production, Redis connection failure will raise an error rather than silently degrading.
"""

import os
import re
from typing import Optional
from backend.app.core.config import Config
from backend.app.core.logging import security_logger

_REDIS_CLIENT = None
_REDIS_INITIALIZED = False


def redact_redis_url(url: str) -> str:
    """Mask credentials in Redis connection strings for safe logging."""
    if not url:
        return ""
    return re.sub(r"://([^:@]+):([^@]+)@", r"://\1:********@", url)


def get_redis_client():
    """
    Retrieve or initialize the singleton Redis connection pool.
    In production (FLASK_ENV=production), failure to connect raises a RuntimeError.
    In dev/testing, returns None if unavailable.
    """
    global _REDIS_CLIENT, _REDIS_INITIALIZED
    if _REDIS_INITIALIZED:
        return _REDIS_CLIENT

    redis_url = os.environ.get("REDIS_URL", "").strip() or getattr(Config, "REDIS_URL", "").strip()
    is_production = (os.environ.get("FLASK_ENV", "").lower() == "production")

    if not redis_url:
        _REDIS_INITIALIZED = True
        _REDIS_CLIENT = None
        if is_production:
            raise RuntimeError(
                "FATAL: REDIS_URL environment variable is mandatory in production for distributed security state. "
                "Process-local in-memory fallbacks are strictly prohibited in production."
            )
        return None

    try:
        import redis
        client = redis.Redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=3,
            socket_timeout=3,
            retry_on_timeout=True
        )
        client.ping()
        _REDIS_CLIENT = client
        _REDIS_INITIALIZED = True
        safe_url = redact_redis_url(redis_url)
        security_logger.info("Connected to Redis distributed security cluster at %s", safe_url)
        return _REDIS_CLIENT
    except Exception as e:
        safe_url = redact_redis_url(redis_url)
        _REDIS_INITIALIZED = True
        _REDIS_CLIENT = None
        if is_production:
            raise RuntimeError(
                f"FATAL: Unable to establish connection to production Redis at {safe_url}: {e}. "
                "Production startup aborted. Silent fallback to in-memory state is forbidden."
            ) from e
        security_logger.warning("Redis unavailable at %s (%s). Falling back to local development cache.", safe_url, e)
        return None
