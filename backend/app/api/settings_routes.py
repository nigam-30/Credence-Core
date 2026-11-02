"""
Credence Core — Settings & Profile Controller
"""

import re
import json
import datetime
from flask import Blueprint, request, jsonify, session
from backend.app.middleware.auth_middleware import login_required, require_role, verify_account_ownership
from backend.app.middleware.csrf_middleware import verify_csrf_request
from backend.app.core.security import (
    hash_password,
    verify_password,
    sanitize_text,
    security_logger,
)
from backend.app.core.mfa import (
    generate_mfa_secret,
    get_totp_uri,
    verify_totp_code,
    generate_recovery_codes,
    encrypt_mfa_secret,
    decrypt_mfa_secret,
)
from backend.app.core.database import get_db
from backend.app.models import User, Account, TransactionLimit
from backend.app.repositories.account_repository import account_repository
from backend.app.utils.cpp_bench import cpp_harness
from backend.app.utils.currency import rupees_to_paise

settings_bp = Blueprint("settings_bp", __name__)


@settings_bp.route("/api/update_profile", methods=["POST"])
@login_required
def update_profile_api():
    csrf_err = verify_csrf_request()
    if csrf_err:
        return csrf_err

    req = request.get_json(silent=True) or {}
    acc_no = session.get("user_id") if session.get("role") != "admin" else sanitize_text(str(req.get("account_number", session.get("user_id"))))
    if not verify_account_ownership(acc_no):
        return jsonify({"success": False, "message": "Access denied: Unauthorized account."}), 403

    email = sanitize_text(str(req.get("email", ""))).strip()
    dob = sanitize_text(str(req.get("dob", ""))).strip()

    if not re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", email):
        return jsonify({"success": False, "message": "Invalid email formatting."}), 400

    if not re.match(r"^\d{4}-\d{2}-\d{2}$", dob):
        return jsonify({"success": False, "message": "Date of birth must be YYYY-MM-DD"}), 400

    with get_db() as db:
        acc = account_repository.get_by_number(db, str(acc_no))
        if not acc or not acc.user:
            return jsonify({"success": False, "message": "Account not found."}), 404
        user = acc.user
        user.email = email
        user.dob = dob
        db.commit()

    security_logger.info(f"Profile updated for account {acc_no}")
    return jsonify({"success": True, "message": "Profile updated successfully"})


@settings_bp.route("/api/settings/password", methods=["POST"])
@login_required
def update_password_api():
    csrf_err = verify_csrf_request()
    if csrf_err:
        return csrf_err

    req = request.get_json(silent=True) or {}
    acc_no = session.get("user_id") if session.get("role") != "admin" else sanitize_text(str(req.get("account_number", session.get("user_id"))))
    if not verify_account_ownership(acc_no):
        return jsonify({"success": False, "message": "Access denied: Unauthorized account."}), 403

    old_p = str(req.get("old_password", ""))
    new_p = str(req.get("new_password", ""))

    with get_db() as db:
        acc = account_repository.get_by_number(db, str(acc_no))
        if not acc or not acc.user:
            return jsonify({"success": False, "message": "Account not found."}), 404
        user = acc.user

        if not user.password_hash or not verify_password(user.password_hash, old_p):
            security_logger.warning(f"Failed password change attempt for account {acc_no}: current password incorrect")
            return jsonify({"success": False, "message": "Current password incorrect."}), 400

        if len(new_p) < 8 or not re.search(r"[A-Za-z]", new_p) or not re.search(r"[0-9]", new_p):
            return jsonify({
                "success": False,
                "message": "New password must be at least 8 characters long and contain letters and numbers."
            }), 400

        user.password_hash = hash_password(new_p)
        db.commit()

    security_logger.info(f"Password successfully changed for account {acc_no}")
    return jsonify({"success": True, "message": "Password updated successfully."})


@settings_bp.route("/api/mfa/status", methods=["GET"])
@settings_bp.route("/api/settings/2fa", methods=["GET"])
@login_required
def get_mfa_status():
    auth_acc = getattr(request, "authenticated_account", session.get("user_id"))
    with get_db() as db:
        acc = account_repository.get_by_number(db, str(auth_acc))
        if not acc or not acc.user:
            return jsonify({"success": False, "message": "Account not found."}), 404
        user = acc.user
        return jsonify({
            "success": True,
            "mfa_enabled": bool(getattr(user, "mfa_enabled", False)),
            "enrolled_at": str(user.mfa_enrolled_at) if user.mfa_enrolled_at else None
        })


@settings_bp.route("/api/mfa/setup", methods=["POST"])
@login_required
def mfa_setup():
    csrf_err = verify_csrf_request()
    if csrf_err:
        return csrf_err

    if getattr(request, "is_demo", False):
        return jsonify({"success": False, "message": "Demo accounts cannot configure MFA."}), 403

    auth_acc = getattr(request, "authenticated_account", session.get("user_id"))
    with get_db() as db:
        acc = account_repository.get_by_number(db, str(auth_acc))
        if not acc or not acc.user:
            return jsonify({"success": False, "message": "Account not found."}), 404
        user = acc.user
        secret = generate_mfa_secret()
        email = user.email or f"{auth_acc}@credence.bank"
        otpauth_uri = get_totp_uri(secret, email)
        plain_codes, hashed_codes = generate_recovery_codes(8)

        session["pending_mfa_secret"] = secret
        session["pending_mfa_hashed_codes"] = json.dumps(hashed_codes)

        return jsonify({
            "success": True,
            "secret": secret,
            "otpauth_uri": otpauth_uri,
            "recovery_codes": plain_codes,
            "message": "Scan the QR code or enter secret in your authenticator app, then confirm via /api/mfa/confirm."
        })


@settings_bp.route("/api/mfa/confirm", methods=["POST"])
@login_required
def mfa_confirm():
    csrf_err = verify_csrf_request()
    if csrf_err:
        return csrf_err

    if getattr(request, "is_demo", False):
        return jsonify({"success": False, "message": "Demo accounts cannot configure MFA."}), 403

    req = request.get_json(silent=True) or {}
    totp_code = req.get("totp_code") or req.get("code")
    pending_secret = session.get("pending_mfa_secret")
    pending_codes = session.get("pending_mfa_hashed_codes")

    if not pending_secret or not totp_code:
        return jsonify({
            "success": False,
            "message": "Pending MFA setup not found or missing verification code. Initiate setup via /api/mfa/setup first."
        }), 400

    if not verify_totp_code(pending_secret, str(totp_code).strip()):
        return jsonify({"success": False, "message": "Invalid authentication code. Please check your authenticator clock."}), 400

    auth_acc = getattr(request, "authenticated_account", session.get("user_id"))
    with get_db() as db:
        acc = account_repository.get_by_number(db, str(auth_acc))
        if not acc or not acc.user:
            return jsonify({"success": False, "message": "Account not found."}), 404
        user = acc.user
        user.mfa_secret = encrypt_mfa_secret(pending_secret)
        user.mfa_recovery_codes = pending_codes
        user.mfa_enabled = True
        user.is_2fa_enabled = True
        user.mfa_enrolled_at = datetime.datetime.utcnow()
        db.commit()

    session.pop("pending_mfa_secret", None)
    session.pop("pending_mfa_hashed_codes", None)
    security_logger.info(f"MFA successfully enabled for account {auth_acc}")
    return jsonify({
        "success": True,
        "message": "Two-factor authentication successfully verified and enabled."
    })


@settings_bp.route("/api/mfa/disable", methods=["POST"])
@login_required
def mfa_disable():
    csrf_err = verify_csrf_request()
    if csrf_err:
        return csrf_err

    if getattr(request, "is_demo", False):
        return jsonify({"success": False, "message": "Demo accounts cannot modify MFA."}), 403

    req = request.get_json(silent=True) or {}
    pwd = req.get("password")
    totp_code = req.get("totp_code") or req.get("code")

    if not pwd or not totp_code:
        return jsonify({"success": False, "message": "Both current password and current TOTP code are required to disable MFA."}), 400

    auth_acc = getattr(request, "authenticated_account", session.get("user_id"))
    with get_db() as db:
        acc = account_repository.get_by_number(db, str(auth_acc))
        if not acc or not acc.user:
            return jsonify({"success": False, "message": "Account not found."}), 404
        user = acc.user
        if not user.password_hash or not verify_password(user.password_hash, pwd):
            return jsonify({"success": False, "message": "Incorrect password."}), 401

        plain_secret = decrypt_mfa_secret(user.mfa_secret)
        if not plain_secret or not verify_totp_code(plain_secret, str(totp_code).strip()):
            return jsonify({"success": False, "message": "Invalid authentication code."}), 401

        user.mfa_enabled = False
        user.is_2fa_enabled = False
        user.mfa_secret = None
        user.mfa_recovery_codes = None
        user.mfa_enrolled_at = None
        db.commit()

    security_logger.info(f"MFA successfully disabled for account {auth_acc}")
    return jsonify({
        "success": True,
        "message": "Two-factor authentication disabled successfully."
    })


@settings_bp.route("/api/settings/2fa", methods=["POST"])
@login_required
def toggle_2fa_api():
    csrf_err = verify_csrf_request()
    if csrf_err:
        return csrf_err

    if getattr(request, "is_demo", False):
        return jsonify({"success": False, "message": "Demo accounts cannot configure MFA."}), 403

    auth_acc = getattr(request, "authenticated_account", session.get("user_id"))
    with get_db() as db:
        acc = account_repository.get_by_number(db, str(auth_acc))
        if not acc or not acc.user:
            return jsonify({"success": False, "message": "Account not found."}), 404
        user = acc.user
        if user.mfa_enabled:
            return jsonify({
                "success": False,
                "message": "Disabling MFA requires password and current TOTP code. Submit request to /api/mfa/disable."
            }), 400
        else:
            return jsonify({
                "success": True,
                "action_required": "setup",
                "message": "To enable two-factor authentication, initiate enrollment via /api/mfa/setup."
            }), 200


@settings_bp.route("/api/settings/notifications", methods=["POST"])
@login_required
def toggle_notifications_api():
    csrf_err = verify_csrf_request()
    if csrf_err:
        return csrf_err

    req = request.get_json(silent=True) or {}
    acc_no = session.get("user_id") if session.get("role") != "admin" else sanitize_text(str(req.get("account_number", session.get("user_id"))))
    if not verify_account_ownership(acc_no):
        return jsonify({"success": False, "message": "Access denied: Unauthorized account."}), 403

    with get_db() as db:
        acc = account_repository.get_by_number(db, str(acc_no))
        if not acc or not acc.user:
            return jsonify({"success": False, "message": "Account not found."}), 404
        user = acc.user
        current = user.notifications_enabled
        user.notifications_enabled = not current
        db.commit()
        status = "enabled" if not current else "disabled"

    security_logger.info(f"Notifications {status} for account {acc_no}")
    return jsonify({"success": True, "message": f"Notifications {status}."})


@settings_bp.route("/api/settings/limits", methods=["GET"])
@login_required
def get_limits_api():
    """Get transaction limits for authenticated account."""
    acc_no = session.get("user_id")
    with get_db() as db:
        lim = db.query(TransactionLimit).filter(TransactionLimit.account_number == acc_no).first()
        if not lim:
            return jsonify({
                "success": True,
                "daily_limit_rupees": 500000.0,
                "per_txn_limit_rupees": 100000.0,
                "approval_threshold_rupees": 50000.0
            })
        return jsonify({
            "success": True,
            "daily_limit_rupees": lim.daily_limit_paise / 100.0,
            "per_txn_limit_rupees": lim.per_txn_limit_paise / 100.0,
            "approval_threshold_rupees": lim.approval_threshold_paise / 100.0
        })


@settings_bp.route("/api/settings/limits", methods=["POST"])
@login_required
def update_limits_api():
    """Update transaction limits for account."""
    csrf_err = verify_csrf_request()
    if csrf_err:
        return csrf_err

    acc_no = session.get("user_id")
    req = request.get_json(silent=True) or {}
    daily = req.get("daily_limit")
    per_txn = req.get("per_txn_limit")
    threshold = req.get("approval_threshold")

    with get_db() as db:
        lim = db.query(TransactionLimit).filter(TransactionLimit.account_number == acc_no).first()
        if not lim:
            lim = TransactionLimit(account_number=acc_no)
            db.add(lim)

        if daily is not None:
            lim.daily_limit_paise = rupees_to_paise(float(daily))
        if per_txn is not None:
            lim.per_txn_limit_paise = rupees_to_paise(float(per_txn))
        if threshold is not None:
            lim.approval_threshold_paise = rupees_to_paise(float(threshold))

        db.commit()

    return jsonify({"success": True, "message": "Transaction limits updated successfully."})


@settings_bp.route("/api/execute", methods=["POST"])
@login_required
@require_role("admin")
def execute_command_api():
    """Privileged admin command execution benchmark interface."""
    csrf_err = verify_csrf_request()
    if csrf_err:
        return csrf_err

    req = request.get_json(silent=True) or {}
    choice = sanitize_text(str(req.get("choice", "")))
    inputs = [sanitize_text(str(i)) for i in req.get("inputs", [])]
    security_logger.warning(f"Admin C++ execute command called by {session.get('user_id')} with choice {choice}")

    if cpp_harness.is_available:
        out = cpp_harness.execute_raw(choice, inputs)
        return jsonify({"success": True, "result": out})
    return jsonify({"success": True, "result": f"Executed simulation choice {choice} with {len(inputs)} inputs."})
