"""
Credence Core — Transfers & Deposits Controller
"""

from flask import Blueprint, request, jsonify, session
from backend.app.middleware.auth_middleware import login_required, log_authz_failure
from backend.app.middleware.csrf_middleware import verify_csrf_request
from backend.app.services.transfers import transfer_service
from backend.app.schemas.validators import (
    validate_account_number,
    validate_amount,
    ValidationError,
)
from backend.app.core.security import log_sensitive_operation, sanitize_text
from backend.app.core.database import get_db
from backend.app.repositories.account_repository import account_repository

transfer_bp = Blueprint("transfer_bp", __name__)


@transfer_bp.route("/api/deposit", methods=["POST"])
@login_required
def deposit():
    csrf_err = verify_csrf_request()
    if csrf_err:
        return csrf_err

    auth_user = session.get("user_id")
    req = request.get_json(silent=True) or {}
    raw_amt = req.get("amount", "0")

    try:
        dec_amt = validate_amount(raw_amt)
    except ValidationError as ve:
        return jsonify({"success": False, "message": str(ve)}), 400

    amount_val = float(dec_amt)
    idem_key = req.get("idempotency_key") or request.headers.get("Idempotency-Key")

    txn = transfer_service.process_deposit(
        account_number=auth_user,
        amount=amount_val,
        actor=auth_user,
        ip=request.remote_addr or "127.0.0.1",
        idempotency_key=idem_key
    )

    if not txn.get("success"):
        return jsonify({
            "success": False,
            "result": txn.get("message", "Deposit failed"),
            "message": txn.get("message", "Deposit failed")
        }), txn.get("status_code", 400)

    bal = txn.get("destination_balance_rupees", 0.0)
    log_sensitive_operation(auth_user, "deposit", amount_val, request.remote_addr or "127.0.0.1")

    return jsonify({
        "success": True,
        "reference_id": txn.get("reference_id"),
        "state": txn.get("state"),
        "amount": amount_val,
        "balance": bal,
        "message": f"Successfully deposited ₹{amount_val:,.2f} into Account #{auth_user}!"
    })


@transfer_bp.route("/api/transfer", methods=["POST"])
@login_required
def transfer():
    csrf_err = verify_csrf_request()
    if csrf_err:
        return csrf_err

    auth_user = session.get("user_id")
    req = request.get_json(silent=True) or {}
    req_from = str(req.get("from_acc", "")).strip()

    # BOLA / Cross-Account Transfer Prevention
    if req_from and req_from != auth_user and session.get("role") != "admin":
        log_authz_failure(auth_user, req_from, "cross_account_transfer", request.remote_addr or "127.0.0.1")
        return jsonify({
            "success": False,
            "result": "Forbidden: Cannot initiate transfers from an account you do not own.",
            "message": "Forbidden: Cannot initiate transfers from an account you do not own."
        }), 403

    from_acc = auth_user
    to_acc = str(req.get("to_acc", "")).strip()
    method = sanitize_text(req.get("method", "Direct Transfer"), max_length=30)

    if from_acc == to_acc:
        return jsonify({"success": False, "result": "Cannot transfer to self.", "message": "Cannot transfer to self."}), 400

    from ledger import SYSTEM_GL_ACCOUNTS
    if to_acc in SYSTEM_GL_ACCOUNTS or to_acc.startswith("GL_"):
        return jsonify({
            "success": False,
            "result": "Forbidden: Internal system and general ledger accounts cannot be used as direct transfer recipients.",
            "message": "Forbidden: Internal system and general ledger accounts cannot be used as direct transfer recipients."
        }), 403

    try:
        validate_account_number(to_acc)
    except ValidationError as ve:
        return jsonify({"success": False, "result": str(ve), "message": str(ve)}), 400

    try:
        dec_amt = validate_amount(req.get("amount", "0"))
    except ValidationError as ve:
        return jsonify({"success": False, "result": str(ve), "message": str(ve)}), 400

    amount_val = float(dec_amt)

    # Verify recipient account exists in database
    with get_db() as db:
        receiver_acc = account_repository.get_by_number(db, to_acc)
        if not receiver_acc:
            return jsonify({
                "success": False,
                "result": "Receiver account does not exist or is invalid.",
                "message": "Receiver account does not exist or is invalid."
            }), 400

    idem_key = req.get("idempotency_key") or request.headers.get("Idempotency-Key")

    txn = transfer_service.process_transfer(
        from_acc=from_acc,
        to_acc=to_acc,
        amount=amount_val,
        method=method,
        description=f"Transfer to {to_acc} ({method})",
        actor=auth_user,
        ip=request.remote_addr or "127.0.0.1",
        idempotency_key=idem_key
    )

    if not txn.get("success"):
        return jsonify({
            "success": False,
            "result": txn.get("message", "Transfer failed"),
            "message": txn.get("message", "Transfer failed")
        }), txn.get("status_code", 400)

    log_sensitive_operation(from_acc, f"transfer_{method}", amount_val, request.remote_addr or "127.0.0.1")

    return jsonify({
        "success": True,
        "reference_id": txn.get("reference_id"),
        "state": txn.get("state"),
        "result": f"Transfer completed successfully. Ref: {txn.get('reference_id')}",
        "message": "Transfer completed successfully."
    })
