"""
Credence Core — Customer Dispute Controller (Phase 5)
Allows authenticated customers to file transaction disputes and check resolution status.
"""

from flask import Blueprint, request, jsonify, session
from backend.app.middleware.auth_middleware import login_required
from backend.app.middleware.csrf_middleware import verify_csrf_request
from backend.app.core.security import sanitize_text
from backend.app.services.disputes import dispute_service

dispute_bp = Blueprint("dispute_bp", __name__)


@dispute_bp.route("/api/disputes", methods=["POST"])
@login_required
def file_dispute():
    """File a dispute on a past transaction."""
    csrf_err = verify_csrf_request()
    if csrf_err:
        return csrf_err

    acc_no = session.get("user_id")
    req = request.get_json(silent=True) or {}
    reference_id = sanitize_text(req.get("reference_id", ""))
    reason = sanitize_text(req.get("reason", ""))
    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "127.0.0.1").split(",")[0].strip()

    res = dispute_service.create_dispute(acc_no, reference_id, reason, ip)
    status_code = res.get("status_code", 200)
    return jsonify(res), status_code


@dispute_bp.route("/api/disputes", methods=["GET"])
@login_required
def list_disputes():
    """List disputes filed by the authenticated customer."""
    acc_no = session.get("user_id")
    disputes = dispute_service.get_account_disputes(acc_no)
    return jsonify({"success": True, "disputes": disputes})
