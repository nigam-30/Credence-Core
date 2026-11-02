"""
Credence Core — Customer Support Controller (Phase 5)
Allows customers to submit support tickets, track resolutions, and view responses.
"""

from flask import Blueprint, request, jsonify, session
from backend.app.middleware.auth_middleware import login_required
from backend.app.middleware.csrf_middleware import verify_csrf_request
from backend.app.core.security import sanitize_text
from backend.app.services.support import support_service

support_bp = Blueprint("support_bp", __name__)


@support_bp.route("/api/support/tickets", methods=["POST"])
@login_required
def create_ticket():
    """Customer submits a new support ticket."""
    csrf_err = verify_csrf_request()
    if csrf_err:
        return csrf_err

    acc_no = session.get("user_id")
    req = request.get_json(silent=True) or {}
    subject = sanitize_text(req.get("subject", ""))
    category = sanitize_text(req.get("category", "GENERAL"))
    priority = sanitize_text(req.get("priority", "MEDIUM"))
    message = sanitize_text(req.get("message", ""))
    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "127.0.0.1").split(",")[0].strip()

    res = support_service.create_ticket(acc_no, subject, category, priority, message, ip)
    status_code = res.get("status_code", 200)
    return jsonify(res), status_code


@support_bp.route("/api/support/tickets", methods=["GET"])
@login_required
def list_my_tickets():
    """List support tickets submitted by the authenticated customer."""
    acc_no = session.get("user_id")
    tickets = support_service.get_customer_tickets(acc_no)
    return jsonify({"success": True, "tickets": tickets})
