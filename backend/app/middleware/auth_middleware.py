"""
Credence Core — Authentication & Authorization Middleware
"""

from functools import wraps
from flask import request, session, jsonify
from backend.app.core.security import (
    login_required,
    require_role,
    verify_account_ownership,
    log_authz_failure,
)

__all__ = ["login_required", "require_role", "verify_account_ownership", "log_authz_failure"]
