"""
Credence Core — CSRF Protection Middleware
"""

from flask import request, session, jsonify
from backend.app.core.security import validate_csrf, csrf_protect, security_logger


def verify_csrf_request():
    """Verify CSRF token for mutating requests."""
    if request.method in ("POST", "PUT", "DELETE", "PATCH"):
        # Exclude public unauthenticated endpoints
        if request.path in ("/api/login", "/api/demo_login", "/api/create_account", "/api/csrf_token", "/api/mfa/verify"):
            return None

        # Validate CSRF
        if not validate_csrf(request):
            security_logger.warning(
                f"EVENT=CSRF_FAILURE ip={request.remote_addr} path={request.path} method={request.method}"
            )
            return jsonify({
                "success": False,
                "message": "Invalid or missing CSRF token. Please refresh the page and try again."
            }), 403
    return None
