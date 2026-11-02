"""
Credence Core — Ledger & Reconciliation Controller
"""

from flask import Blueprint, request, jsonify, session
from backend.app.middleware.auth_middleware import login_required, require_role, verify_account_ownership
from backend.app.middleware.csrf_middleware import verify_csrf_request
from backend.app.services.ledger import ledger_service
from backend.app.core.security import sanitize_text

ledger_bp = Blueprint("ledger_bp", __name__)


@ledger_bp.route("/api/ledger/reverse", methods=["POST"])
@login_required
def reverse_transaction_api():
    csrf_err = verify_csrf_request()
    if csrf_err:
        return csrf_err

    req = request.get_json(silent=True) or {}
    ref_id = sanitize_text(str(req.get("reference_id", "")))
    reason = sanitize_text(str(req.get("reason", "Customer requested reversal")))

    if not ref_id:
        return jsonify({"success": False, "message": "Reference ID is required."}), 400

    result = ledger_service.reverse(
        reference_id=ref_id,
        reason=reason,
        actor=session.get("user_id") or "SYSTEM",
        ip=request.remote_addr or "127.0.0.1"
    )
    return jsonify(result)


@ledger_bp.route("/api/ledger/reconcile", methods=["GET"])
@login_required
@require_role("admin")
def reconcile_ledger_api():
    report = ledger_service.reconcile()
    return jsonify(report)


@ledger_bp.route("/api/ledger/history/<acc_no>", methods=["GET"])
@login_required
def get_ledger_history_api(acc_no):
    acc_no = sanitize_text(str(acc_no).strip())
    if not verify_account_ownership(acc_no):
        return jsonify({"success": False, "message": "Access denied: Unauthorized account access."}), 403

    history = ledger_service.get_history(acc_no)
    return jsonify({"success": True, "history": history})
