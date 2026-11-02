"""
Credence Core — UPI Controller
"""

from flask import Blueprint, request, jsonify, session
from backend.app.middleware.auth_middleware import login_required, verify_account_ownership
from backend.app.middleware.csrf_middleware import verify_csrf_request
from backend.app.core.security import (
    hash_pin,
    verify_pin,
    verify_password,
    security_logger,
    sanitize_text,
)
from backend.app.core.database import get_db
from backend.app.models import UPIProfile, Account
from backend.app.repositories.account_repository import account_repository

upi_bp = Blueprint("upi_bp", __name__)


@upi_bp.route("/api/create_upi", methods=["POST"])
@login_required
def create_upi_api():
    csrf_err = verify_csrf_request()
    if csrf_err:
        return csrf_err

    req = request.get_json(silent=True) or {}
    acc = session.get("user_id") if session.get("role") != "admin" else sanitize_text(str(req.get("account", session.get("user_id"))))
    if not verify_account_ownership(acc):
        return jsonify({"success": False, "message": "Access denied: Unauthorized account."}), 403

    if session.get("is_demo"):
        return jsonify({"success": False, "message": "Demo accounts cannot modify security PINs."}), 403

    upi_id = sanitize_text(str(req.get("upi_id", "")))
    upi_pin = str(req.get("upi_pin", "")).strip()
    if not acc or not upi_id or not (upi_pin.isdigit() and len(upi_pin) in [4, 6]):
        return jsonify({"success": False, "message": "Missing info or invalid UPI PIN (must be 4-6 digits)"}), 400

    with get_db() as db:
        acc_rec = account_repository.get_by_number(db, str(acc))
        if not acc_rec:
            return jsonify({"success": False, "message": "Account not found."}), 404

        upi = db.query(UPIProfile).filter(UPIProfile.account_number == str(acc)).first()
        if not upi:
            upi = UPIProfile(
                account_number=str(acc),
                upi_id=upi_id,
                upi_pin_hash=hash_pin(upi_pin),
                status="ACTIVE"
            )
            db.add(upi)
        else:
            upi.upi_id = upi_id
            upi.upi_pin_hash = hash_pin(upi_pin)
        db.commit()

    security_logger.info(f"UPI ID created for account {acc}")
    return jsonify({"success": True, "message": "UPI ID Created"})


@upi_bp.route("/api/reset_upi_pin", methods=["POST"])
@login_required
def reset_upi_pin_api():
    csrf_err = verify_csrf_request()
    if csrf_err:
        return csrf_err

    req = request.get_json(silent=True) or {}
    acc = session.get("user_id") if session.get("role") != "admin" else sanitize_text(str(req.get("account", session.get("user_id"))))
    if not verify_account_ownership(acc):
        return jsonify({"success": False, "message": "Access denied: Unauthorized account."}), 403

    if session.get("is_demo"):
        return jsonify({"success": False, "message": "Demo accounts cannot modify security PINs."}), 403

    current_pass = str(req.get("password", "")).strip()
    old_pin = str(req.get("old_pin", "")).strip()
    new_upi_pin = str(req.get("upi_pin", "")).strip()

    if not (new_upi_pin.isdigit() and len(new_upi_pin) in [4, 6]):
        return jsonify({"success": False, "message": "Invalid new PIN (must be 4-6 digits)"}), 400

    with get_db() as db:
        acc_rec = account_repository.get_by_number(db, str(acc))
        if not acc_rec:
            return jsonify({"success": False, "message": "Account not found."}), 404

        user = acc_rec.user
        upi = acc_rec.upi_profile

        authorized = False
        # In security.verify_pin, signature is (stored_hash, candidate_pin)
        if old_pin and upi and upi.upi_pin_hash and verify_pin(upi.upi_pin_hash, old_pin):
            authorized = True
        elif current_pass and user and user.password_hash and verify_password(user.password_hash, current_pass):
            authorized = True

        if not authorized:
            security_logger.warning(f"Unauthorized UPI PIN reset attempt for account {acc}")
            return jsonify({
                "success": False,
                "message": "Verification failed: valid password or previous PIN required to reset UPI PIN."
            }), 403

        if not upi:
            upi = UPIProfile(
                account_number=str(acc),
                upi_id=f"user_{str(acc)[-4:]}@credence",
                upi_pin_hash=hash_pin(new_upi_pin),
                status="ACTIVE"
            )
            db.add(upi)
        else:
            upi.upi_pin_hash = hash_pin(new_upi_pin)
        db.commit()

    return jsonify({"success": True, "message": "UPI PIN Reset successful"})
