"""
Credence Core — Rate Limiting Middleware
"""

from flask import request, jsonify
from backend.app.core.security import check_ip_rate_limit, rate_limit


def apply_rate_limit(key_prefix: str, max_requests: int = 60, window_seconds: int = 60):
    """Enforce in-memory sliding window rate limit on endpoint."""
    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "127.0.0.1").split(",")[0].strip()
    key = f"{key_prefix}:{ip}"
    allowed = check_ip_rate_limit(key, max_requests, window_seconds)
    if not allowed:
        return jsonify({
            "success": False,
            "message": f"Rate limit exceeded. Please wait {window_seconds} seconds before retrying."
        }), 429
    return None
