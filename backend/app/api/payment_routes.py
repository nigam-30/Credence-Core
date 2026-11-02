"""
Credence Core — Payments Controller
"""

from flask import Blueprint, request, jsonify, session
from backend.app.middleware.auth_middleware import login_required, log_authz_failure
from backend.app.middleware.csrf_middleware import verify_csrf_request
from backend.app.services.payments import payment_service
from backend.app.schemas.validators import validate_amount, ValidationError
from backend.app.core.security import (
    verify_password,
    verify_pin,
    log_pin_failure,
    log_sensitive_operation,
    sanitize_text,
)
from backend.app.services.accounts import account_service
from backend.app.core.database import get_db
from backend.app.repositories.account_repository import account_repository

payment_bp = Blueprint("payment_bp", __name__)


@payment_bp.route("/api/pay_bill", methods=["POST"])
@login_required
def pay_bill_api():
    csrf_err = verify_csrf_request()
    if csrf_err:
        return csrf_err

    auth_user = session.get("user_id")
    req = request.get_json(silent=True) or {}
    req_acc = str(req.get("account", "")).strip()

    if req_acc and req_acc != auth_user and session.get("role") != "admin":
        log_authz_failure(auth_user, req_acc, "cross_account_bill_pay", request.remote_addr or "127.0.0.1")
        return jsonify({"success": False, "message": "Forbidden: Cannot pay bills from an account you do not own."}), 403

    acc_no = auth_user
    biller = sanitize_text(req.get("biller", "Bill"), max_length=50)
    company = sanitize_text(req.get("company", "Unknown"), max_length=50)
    method = sanitize_text(req.get("method", "Account Balance"), max_length=30)
    consumer_no = sanitize_text(req.get("consumer_no", ""), max_length=50)

    try:
        dec_amt = validate_amount(req.get("amount", "0"))
    except ValidationError as ve:
        return jsonify({"success": False, "message": str(ve)}), 400

    amount_val = float(dec_amt)

    # Credential Verification for Netbanking, Debit Card, UPI
    with get_db() as db:
        acc = account_repository.get_by_number(db, acc_no)
        user = acc.user if acc else None
        card = acc.cards[0] if (acc and acc.cards) else None
        upi = acc.upi_profile if acc else None

        if method == "Net Banking":
            nb_password = str(req.get("nb_password", ""))
            stored_hash = user.password_hash if user else ""
            if not stored_hash or not verify_password(stored_hash, nb_password):
                log_pin_failure(acc_no, "bill_pay_wrong_nb_password", request.remote_addr or "127.0.0.1")
                return jsonify({"success": False, "message": "Invalid Net Banking Password."}), 400

        elif method == "Debit Card":
            pin = str(req.get("pin", "")).strip()
            stored_pin_hash = card.pin_hash if card else (user.pin_hash if user else "")
            if not stored_pin_hash or not verify_pin(stored_pin_hash, pin):
                log_pin_failure(acc_no, "bill_pay_wrong_debit_pin", request.remote_addr or "127.0.0.1")
                return jsonify({"success": False, "message": "Invalid Debit Card PIN."}), 400

        elif method == "UPI":
            upi_pin = str(req.get("upi_pin", "")).strip()
            stored_upi_hash = upi.upi_pin_hash if upi else ""
            if not stored_upi_hash or not verify_pin(stored_upi_hash, upi_pin):
                log_pin_failure(acc_no, "bill_pay_wrong_upi_pin", request.remote_addr or "127.0.0.1")
                return jsonify({"success": False, "message": "Invalid UPI PIN."}), 400

    idem_key = req.get("idempotency_key") or request.headers.get("Idempotency-Key")

    txn = payment_service.process_bill_payment(
        account_number=acc_no,
        biller_name=company,
        category=biller,
        amount=amount_val,
        consumer_no=consumer_no or biller,
        payment_method=method,
        actor=auth_user,
        ip=request.remote_addr or "127.0.0.1",
        idempotency_key=idem_key
    )

    log_sensitive_operation(acc_no, f"bill_pay_{method}", amount_val, request.remote_addr or "127.0.0.1")

    return jsonify({
        "success": True,
        "reference_id": txn.get("reference_id"),
        "state": txn.get("state"),
        "message": f"Payment successful via {method}.",
        "result": f"Payment completed. Ref: {txn.get('reference_id')}"
    })


@payment_bp.route("/api/debit_payment", methods=["POST"])
@login_required
def debit_payment_api():
    csrf_err = verify_csrf_request()
    if csrf_err:
        return csrf_err

    auth_user = session.get("user_id")
    req = request.get_json(silent=True) or {}
    req_acc = str(req.get("account", "")).strip()

    if req_acc and req_acc != auth_user and session.get("role") != "admin":
        return jsonify({"success": False, "message": "Forbidden: Cannot process debit card payment for another account."}), 403

    acc_no = auth_user
    pin = str(req.get("pin", "")).strip()
    merchant = sanitize_text(req.get("merchant", "POS Merchant"), max_length=50)

    try:
        dec_amt = validate_amount(req.get("amount", "0"))
    except ValidationError as ve:
        return jsonify({"success": False, "message": str(ve)}), 400

    amount_val = float(dec_amt)

    with get_db() as db:
        acc = account_repository.get_by_number(db, acc_no)
        card = acc.cards[0] if (acc and acc.cards) else None
        user = acc.user if acc else None
        stored_pin_hash = card.pin_hash if card else (user.pin_hash if user else "")
        if not stored_pin_hash or not verify_pin(stored_pin_hash, pin):
            log_pin_failure(acc_no, "pos_debit_wrong_pin", request.remote_addr or "127.0.0.1")
            return jsonify({"success": False, "message": "Incorrect ATM PIN."}), 400

    idem_key = req.get("idempotency_key") or request.headers.get("Idempotency-Key")

    txn = payment_service.process_debit_card_payment(
        account_number=acc_no,
        merchant=merchant,
        amount=amount_val,
        actor=auth_user,
        ip=request.remote_addr or "127.0.0.1",
        idempotency_key=idem_key
    )

    log_sensitive_operation(acc_no, "pos_debit", amount_val, request.remote_addr or "127.0.0.1")

    return jsonify({
        "success": True,
        "reference_id": txn.get("reference_id"),
        "state": txn.get("state"),
        "message": f"Debit card payment of ₹{amount_val:,.2f} to {merchant} successful."
    })
