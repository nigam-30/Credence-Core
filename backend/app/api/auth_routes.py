"""
Credence Core — Authentication Controller
"""

import os
from flask import Blueprint, request, jsonify, session
from backend.app.core.security import generate_csrf_token, check_ip_rate_limit, validate_csrf
from backend.app.core.config import Config
from backend.app.middleware.csrf_middleware import verify_csrf_request
from backend.app.services.authentication import auth_service

auth_bp = Blueprint("auth_bp", __name__)


def _is_secure_cookie() -> bool:
    return (
        os.environ.get("FLASK_ENV") == "production" or
        os.environ.get("SESSION_COOKIE_SECURE", "false").lower() in ("true", "1", "yes")
    )


@auth_bp.route("/api/csrf_token", methods=["GET"])
def get_csrf_token():
    token = generate_csrf_token()
    resp = jsonify({"csrf_token": token})
    resp.set_cookie("csrf_token", token, samesite="Lax", httponly=False, secure=_is_secure_cookie())
    return resp


@auth_bp.route("/api/login", methods=["POST"])
def login():
    req = request.get_json(silent=True) or {}
    acc_no = req.get("account_number") or req.get("account") or req.get("username")
    pwd = req.get("password")
    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "127.0.0.1").split(",")[0].strip()

    # Rate limiting
    allowed = check_ip_rate_limit(f"login:{ip}", max_requests=30, window_seconds=60)
    if not allowed:
        return jsonify({
            "success": False,
            "message": "Too many login attempts. Please wait 60 seconds before retrying."
        }), 429

    if not acc_no or not pwd:
        return jsonify({"success": False, "message": "Invalid account number or password."}), 401

    res = auth_service.authenticate_user(str(acc_no), str(pwd), ip)
    if res.get("mfa_required"):
        return jsonify({
            "success": True,
            "mfa_required": True,
            "mfa_ticket": res["mfa_ticket"],
            "message": res.get("message", "MFA required")
        }), 200

    if res["success"]:
        payload = {
            "success": True,
            "account": res["user"]["account_number"],
            "message": "Login successful.",
            "user": res["user"],
            "csrf_token": res["csrf_token"]
        }
        # In testing environments, include session_token in JSON so automated test suites can verify token rotation
        from flask import current_app
        if current_app.config.get("TESTING"):
            payload["session_token"] = res["session_token"]

        resp = jsonify(payload)
        is_sec = _is_secure_cookie()
        resp.set_cookie("session_token", res["session_token"], samesite="Lax", httponly=True, secure=is_sec)
        resp.set_cookie("csrf_token", res["csrf_token"], samesite="Lax", httponly=False, secure=is_sec)
        return resp
    return jsonify({"success": False, "message": res["message"]}), res["status_code"]


@auth_bp.route("/api/mfa/verify", methods=["POST"])
def verify_mfa():
    req = request.get_json(silent=True) or {}
    ticket = req.get("mfa_ticket")
    totp_code = req.get("totp_code") or req.get("code")
    recovery_code = req.get("recovery_code")
    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "127.0.0.1").split(",")[0].strip()

    if not ticket or (not totp_code and not recovery_code):
        return jsonify({"success": False, "message": "MFA ticket and code are required."}), 400

    res = auth_service.verify_mfa_login(ticket, totp_code, recovery_code, ip)
    if res["success"]:
        resp = jsonify({
            "success": True,
            "account": res["user"]["account_number"],
            "message": res["message"],
            "user": res["user"],
            "csrf_token": res["csrf_token"]
        })
        is_sec = _is_secure_cookie()
        resp.set_cookie("session_token", res["session_token"], samesite="Lax", httponly=True, secure=is_sec)
        resp.set_cookie("csrf_token", res["csrf_token"], samesite="Lax", httponly=False, secure=is_sec)
        return resp
    return jsonify({"success": False, "message": res["message"]}), res.get("status_code", 401)


@auth_bp.route("/api/demo_login", methods=["POST"])
def demo_login():
    if not Config.CONFIGURED_DEMO_ACCOUNTS:
        return jsonify({
            "success": False,
            "message": "Demo login is disabled: no demo accounts are provisioned in this environment."
        }), 403

    req = request.get_json(silent=True) or {}
    acc_no = req.get("account_number") or req.get("account")
    if not acc_no:
        return jsonify({"success": False, "message": "Account number is required for demo login."}), 400

    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "127.0.0.1").split(",")[0].strip()

    res = auth_service.authenticate_demo(str(acc_no), ip)
    if res["success"]:
        resp = jsonify({
            "success": True,
            "account": res["user"]["account_number"],
            "message": res["message"],
            "user": res["user"],
            "csrf_token": res["csrf_token"]
        })
        is_sec = _is_secure_cookie()
        resp.set_cookie("session_token", res["session_token"], samesite="Lax", httponly=True, secure=is_sec)
        resp.set_cookie("csrf_token", res["csrf_token"], samesite="Lax", httponly=False, secure=is_sec)
        return resp
    return jsonify({"success": False, "message": res["message"]}), res["status_code"]


@auth_bp.route("/api/logout", methods=["POST"])
def logout():
    # Verify CSRF on logout when client provides CSRF header
    client_csrf = request.headers.get("X-CSRF-Token") or request.headers.get("X-XSRF-Token")
    if client_csrf:
        csrf_err = verify_csrf_request()
        if csrf_err:
            return csrf_err

    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "127.0.0.1").split(",")[0].strip()
    res = auth_service.logout_user(ip)
    resp = jsonify(res)
    resp.delete_cookie("session")
    resp.delete_cookie("session_token")
    resp.delete_cookie("csrf_token")
    return resp
