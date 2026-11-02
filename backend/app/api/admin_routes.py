"""
Credence Core — Admin Operations Controller (Phase 5)
Provides high-level banking operations dashboard, account freeze/unfreeze,
audit inspection, transaction approval workflows, and fraud monitoring.
Strictly restricted to users with role='admin'.
"""

from flask import Blueprint, request, jsonify, session
from backend.app.middleware.auth_middleware import login_required, require_role
from backend.app.middleware.csrf_middleware import verify_csrf_request
from backend.app.core.security import sanitize_text
from backend.app.services.admin import admin_service
from backend.app.services.fraud import fraud_service
from backend.app.services.disputes import dispute_service
from backend.app.services.support import support_service

admin_bp = Blueprint("admin_bp", __name__)


# ══════════════════════════════════════════════════════════════
# 1. ADMIN OPERATIONS DASHBOARD
# ══════════════════════════════════════════════════════════════
@admin_bp.route("/api/admin/dashboard", methods=["GET"])
@login_required
@require_role("admin")
def get_admin_dashboard():
    """Retrieve bank-wide operational KPIs and system summaries."""
    summary = admin_service.get_dashboard_summary()
    return jsonify(summary)


# ══════════════════════════════════════════════════════════════
# 2. ACCOUNT FREEZE & UNFREEZE
# ══════════════════════════════════════════════════════════════
@admin_bp.route("/api/admin/accounts/<acc_no>/freeze", methods=["POST"])
@login_required
@require_role("admin")
def freeze_account(acc_no):
    """Administratively freeze an account to suspend debits."""
    csrf_err = verify_csrf_request()
    if csrf_err:
        return csrf_err

    req = request.get_json(silent=True) or {}
    reason = sanitize_text(req.get("reason", "Administrative risk hold"))
    admin_user = session.get("user_id", "ADMIN")
    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "127.0.0.1").split(",")[0].strip()

    res = admin_service.freeze_account(acc_no, reason, admin_user, ip)
    status_code = res.get("status_code", 200)
    return jsonify(res), status_code


@admin_bp.route("/api/admin/accounts/<acc_no>/unfreeze", methods=["POST"])
@login_required
@require_role("admin")
def unfreeze_account(acc_no):
    """Administratively unfreeze an account and restore services."""
    csrf_err = verify_csrf_request()
    if csrf_err:
        return csrf_err

    req = request.get_json(silent=True) or {}
    reason = sanitize_text(req.get("reason", "Verification complete"))
    admin_user = session.get("user_id", "ADMIN")
    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "127.0.0.1").split(",")[0].strip()

    res = admin_service.unfreeze_account(acc_no, reason, admin_user, ip)
    status_code = res.get("status_code", 200)
    return jsonify(res), status_code


# ══════════════════════════════════════════════════════════════
# 3. AUDIT HISTORY VIEWER
# ══════════════════════════════════════════════════════════════
@admin_bp.route("/api/admin/audit_logs", methods=["GET"])
@login_required
@require_role("admin")
def get_audit_logs():
    """Retrieve system audit logs with actor and action filters."""
    actor = request.args.get("actor")
    action = request.args.get("action")
    account_number = request.args.get("account_number")
    limit = min(int(request.args.get("limit", 100)), 500)
    offset = int(request.args.get("offset", 0))

    logs = admin_service.get_audit_logs(actor, action, account_number, limit, offset)
    return jsonify(logs)


# ══════════════════════════════════════════════════════════════
# 4. TRANSACTION LIMITS & APPROVAL WORKFLOW
# ══════════════════════════════════════════════════════════════
@admin_bp.route("/api/admin/approvals", methods=["GET"])
@login_required
@require_role("admin")
def get_pending_approvals():
    """List pending high-value transactions awaiting administrative approval."""
    approvals = admin_service.get_pending_approvals()
    return jsonify({"success": True, "pending_transactions": approvals})


@admin_bp.route("/api/admin/approvals/<ref_id>/action", methods=["POST"])
@login_required
@require_role("admin")
def process_approval_action(ref_id):
    """Approve or Reject a pending transaction."""
    csrf_err = verify_csrf_request()
    if csrf_err:
        return csrf_err

    req = request.get_json(silent=True) or {}
    action = sanitize_text(req.get("action", ""))
    reason = sanitize_text(req.get("reason", "Reviewed by bank administration"))
    admin_user = session.get("user_id", "ADMIN")
    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "127.0.0.1").split(",")[0].strip()

    res = admin_service.process_approval(ref_id, action, reason, admin_user, ip)
    status_code = res.get("status_code", 200)
    return jsonify(res), status_code


# ══════════════════════════════════════════════════════════════
# 5. FRAUD MONITORING & SUSPICIOUS ALERTS
# ══════════════════════════════════════════════════════════════
@admin_bp.route("/api/admin/fraud/alerts", methods=["GET"])
@login_required
@require_role("admin")
def get_fraud_alerts():
    """Retrieve rule-based fraud detection alerts."""
    limit = min(int(request.args.get("limit", 50)), 100)
    alerts = fraud_service.get_alerts(limit=limit)
    return jsonify({"success": True, "alerts": alerts})


@admin_bp.route("/api/admin/fraud/resolve", methods=["POST"])
@login_required
@require_role("admin")
def resolve_fraud_alert():
    """Resolve or dismiss a fraud alert."""
    csrf_err = verify_csrf_request()
    if csrf_err:
        return csrf_err

    req = request.get_json(silent=True) or {}
    alert_id = sanitize_text(req.get("alert_id", ""))
    action = sanitize_text(req.get("action", "DISMISS"))
    admin_user = session.get("user_id", "ADMIN")

    ok = fraud_service.resolve_alert(alert_id, action, admin_user)
    if not ok:
        return jsonify({"success": False, "message": "Alert not found."}), 404
    return jsonify({"success": True, "message": f"Alert '{alert_id}' marked as {action}."})


# ══════════════════════════════════════════════════════════════
# 6. DISPUTE MANAGEMENT (ADMIN)
# ══════════════════════════════════════════════════════════════
@admin_bp.route("/api/admin/disputes", methods=["GET"])
@login_required
@require_role("admin")
def list_admin_disputes():
    """List all customer transaction disputes."""
    status = request.args.get("status")
    disputes = dispute_service.list_all_disputes(status)
    return jsonify({"success": True, "disputes": disputes})


@admin_bp.route("/api/admin/disputes/<dispute_id>/resolve", methods=["POST"])
@login_required
@require_role("admin")
def resolve_dispute(dispute_id):
    """Resolve a dispute (APPROVE_REFUND with automatic ledger reversal, or REJECT)."""
    csrf_err = verify_csrf_request()
    if csrf_err:
        return csrf_err

    req = request.get_json(silent=True) or {}
    action = sanitize_text(req.get("action", ""))
    notes = sanitize_text(req.get("notes", "Reviewed by bank administration"))
    admin_user = session.get("user_id", "ADMIN")
    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "127.0.0.1").split(",")[0].strip()

    res = dispute_service.resolve_dispute(dispute_id, action, notes, admin_user, ip)
    status_code = res.get("status_code", 200)
    return jsonify(res), status_code


# ══════════════════════════════════════════════════════════════
# 7. SUPPORT TICKET MANAGEMENT (ADMIN)
# ══════════════════════════════════════════════════════════════
@admin_bp.route("/api/admin/support/tickets", methods=["GET"])
@login_required
@require_role("admin")
def list_admin_tickets():
    """List all customer support tickets."""
    status = request.args.get("status")
    priority = request.args.get("priority")
    category = request.args.get("category")
    tickets = support_service.list_all_tickets(status, priority, category)
    return jsonify({"success": True, "tickets": tickets})


@admin_bp.route("/api/admin/support/tickets/<ticket_id>/reply", methods=["POST"])
@login_required
@require_role("admin")
def reply_support_ticket(ticket_id):
    """Admin responds to customer ticket."""
    csrf_err = verify_csrf_request()
    if csrf_err:
        return csrf_err

    req = request.get_json(silent=True) or {}
    response_text = sanitize_text(req.get("response", ""))
    status = sanitize_text(req.get("status", "IN_PROGRESS"))
    admin_user = session.get("user_id", "ADMIN")
    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "127.0.0.1").split(",")[0].strip()

    res = support_service.reply_ticket(ticket_id, response_text, status, admin_user, ip)
    status_code = res.get("status_code", 200)
    return jsonify(res), status_code
