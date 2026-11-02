"""
Credence Core — Middleware Package
"""

from backend.app.middleware.auth_middleware import (
    login_required,
    require_role,
    verify_account_ownership,
    log_authz_failure,
)
from backend.app.middleware.csrf_middleware import verify_csrf_request
from backend.app.middleware.cors_middleware import apply_security_headers
from backend.app.middleware.rate_limiter import apply_rate_limit
from backend.app.middleware.error_handlers import register_error_handlers

__all__ = [
    "login_required",
    "require_role",
    "verify_account_ownership",
    "log_authz_failure",
    "verify_csrf_request",
    "apply_security_headers",
    "apply_rate_limit",
    "register_error_handlers",
]
