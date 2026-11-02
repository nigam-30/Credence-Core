"""
Credence Core — Accounts Controller
"""

from flask import Blueprint, request, jsonify, session
from backend.app.middleware.auth_middleware import login_required, require_role, verify_account_ownership
from backend.app.services.accounts import account_service
from backend.app.schemas.validators import (
    validate_account_number,
    validate_pin,
    validate_password_strength,
    ValidationError,
)

account_bp = Blueprint("account_bp", __name__)


@account_bp.route("/api/create_account", methods=["POST"])
def create_account_api():
    req = request.get_json(silent=True) or {}
    name = (req.get("name") or "").strip()
    deposit_raw = req.get("deposit", 0.0)
    debit_opt = req.get("debit", "n")
    pin = req.get("pin")
    upi_pin = req.get("upi_pin")
    pwd = req.get("password")
    email = req.get("email")
    pan = req.get("pan")

    if not name:
        return jsonify({"success": False, "message": "Customer name is required."}), 400

    if not pwd:
        return jsonify({"success": False, "message": "Password is required."}), 400

    try:
        validate_password_strength(pwd)
    except ValidationError:
        return jsonify({
            "success": False,
            "message": "Netbanking password must be at least 8 characters long and contain both letters and digits."
        }), 400

    if debit_opt.lower() == "y":
        if not pin:
            return jsonify({"success": False, "message": "Debit card PIN is required when requesting a card."}), 400
        try:
            validate_pin(pin)
        except ValidationError:
            return jsonify({"success": False, "message": "Debit card PIN must be exactly 4 digits."}), 400

    if upi_pin:
        try:
            validate_pin(upi_pin, allow_6_digit=True)
        except ValidationError:
            return jsonify({"success": False, "message": "UPI PIN must be 4 or 6 digits."}), 400

    res = account_service.create_account(
        name=name,
        deposit=deposit,
        debit_opt=debit_opt,
        pin=pin,
        upi_pin=upi_pin,
        password=pwd,
        email=email,
        pan=pan
    )
    return jsonify(res)


@account_bp.route("/api/account/<acc_no>", methods=["GET"])
@login_required
def get_account_api(acc_no):
    if not verify_account_ownership(acc_no):
        return jsonify({"success": False, "message": "Unauthorized: Cannot access another user's account details."}), 403

    details = account_service.get_account_details(acc_no)
    if not details:
        return jsonify({"error": "Not found"}), 404
    return jsonify(details)


@account_bp.route("/api/account/verify_pin", methods=["POST"])
@login_required
def verify_account_pin_api():
    """
    Verify user's security PIN on the backend without exposing PIN hashes
    or performing client-side verification.
    """
    from backend.app.core.security import verify_pin, check_ip_rate_limit, log_pin_failure
    from backend.app.middleware.csrf_middleware import verify_csrf_request
    from backend.app.core.database import get_db
    from backend.app.repositories.account_repository import account_repository

    csrf_err = verify_csrf_request()
    if csrf_err:
        return csrf_err

    auth_acc = session.get("user_id")
    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "127.0.0.1").split(",")[0].strip()

    if not check_ip_rate_limit(f"pin_verify:{auth_acc}:{ip}", max_requests=5, window_seconds=300):
        return jsonify({
            "success": False,
            "message": "Too many failed PIN attempts. Please wait 5 minutes before retrying."
        }), 429

    req = request.get_json(silent=True) or {}
    pin = req.get("pin")
    if not pin or len(str(pin).strip()) not in (4, 6):
        return jsonify({"success": False, "message": "Invalid PIN format. PIN must be 4 or 6 digits."}), 400

    with get_db() as db:
        acc = account_repository.get_by_number(db, auth_acc)
        if not acc or not acc.user:
            return jsonify({"success": False, "message": "Account not found."}), 404

        user = acc.user
        stored_hash = user.pin_hash
        if not stored_hash or not verify_pin(stored_hash, str(pin).strip()):
            log_pin_failure(auth_acc, "balance_reveal_pin", ip)
            return jsonify({"success": False, "message": "Incorrect PIN. Access denied."}), 401

    return jsonify({"success": True, "message": "PIN verified successfully."})


@account_bp.route("/api/accounts", methods=["GET"])
@login_required
@require_role("admin")
def list_accounts_api():
    accounts = account_service.list_all_accounts()
    return jsonify(accounts)


@account_bp.route("/api/demo_info", methods=["GET"])
@login_required
@require_role("admin")
def get_demo_info_api():
    """Privileged admin endpoint for system demo context."""
    return jsonify({
        "status": "operational",
        "system_account": "GL_CLEARING_ESCROW",
        "institution": "Credence Core Bank"
    })
