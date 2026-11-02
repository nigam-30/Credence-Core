"""
Credence Core — Beneficiary Controller (Phase 5)
Allows customers to manage pre-registered payees and execute quick transfers.
"""

from flask import Blueprint, request, jsonify, session
from backend.app.middleware.auth_middleware import login_required
from backend.app.middleware.csrf_middleware import verify_csrf_request
from backend.app.core.security import sanitize_text
from backend.app.schemas.validators import validate_amount, ValidationError
from backend.app.services.beneficiaries import beneficiary_service

beneficiary_bp = Blueprint("beneficiary_bp", __name__)


@beneficiary_bp.route("/api/beneficiaries", methods=["GET"])
@login_required
def list_beneficiaries():
    """List registered beneficiaries for the authenticated user."""
    acc_no = session.get("user_id")
    bens = beneficiary_service.list_beneficiaries(acc_no)
    return jsonify({"success": True, "beneficiaries": bens})


@beneficiary_bp.route("/api/beneficiaries", methods=["POST"])
@login_required
def add_beneficiary():
    """Register a new payee beneficiary."""
    csrf_err = verify_csrf_request()
    if csrf_err:
        return csrf_err

    acc_no = session.get("user_id")
    req = request.get_json(silent=True) or {}
    name = sanitize_text(req.get("beneficiary_name", ""))
    ben_acc = sanitize_text(req.get("beneficiary_account_number", ""))
    ifsc = sanitize_text(req.get("ifsc_code", "CRDN0001001"))
    xfer_type = sanitize_text(req.get("transfer_type", "IMPS"))

    res = beneficiary_service.add_beneficiary(acc_no, name, ben_acc, ifsc, xfer_type)
    status_code = res.get("status_code", 200)
    return jsonify(res), status_code


@beneficiary_bp.route("/api/beneficiaries/<int:ben_id>", methods=["DELETE"])
@login_required
def delete_beneficiary(ben_id):
    """Delete a registered payee beneficiary."""
    csrf_err = verify_csrf_request()
    if csrf_err:
        return csrf_err

    acc_no = session.get("user_id")
    res = beneficiary_service.delete_beneficiary(acc_no, ben_id)
    status_code = res.get("status_code", 200)
    return jsonify(res), status_code


@beneficiary_bp.route("/api/beneficiaries/quick_transfer", methods=["POST"])
@login_required
def quick_transfer():
    """One-click transfer directly to a saved beneficiary."""
    csrf_err = verify_csrf_request()
    if csrf_err:
        return csrf_err

    acc_no = session.get("user_id")
    req = request.get_json(silent=True) or {}
    ben_id = req.get("beneficiary_id")
    raw_amount = req.get("amount")
    idempotency_key = req.get("idempotency_key")
    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "127.0.0.1").split(",")[0].strip()

    if not ben_id:
        return jsonify({"success": False, "message": "beneficiary_id is required."}), 400

    try:
        amount_dec = validate_amount(raw_amount)
    except ValidationError as e:
        return jsonify({"success": False, "message": str(e)}), 400

    res = beneficiary_service.quick_transfer(
        from_acc=acc_no,
        beneficiary_id=int(ben_id),
        amount=float(amount_dec),
        actor=acc_no,
        ip=ip,
        idempotency_key=idempotency_key
    )
    status_code = 200 if res.get("success") else 400
    return jsonify(res), status_code
