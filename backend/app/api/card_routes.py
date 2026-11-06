"""
Credence Core — Cards & Ancillary Services Controller
"""

from flask import Blueprint, request, jsonify, session
from backend.app.middleware.auth_middleware import login_required, verify_account_ownership
from backend.app.middleware.csrf_middleware import verify_csrf_request
from backend.app.services.cards import card_service
from backend.app.schemas.validators import validate_pin, ValidationError
from backend.app.core.security import verify_password, sanitize_text
from backend.app.core.database import get_db
from backend.app.repositories.account_repository import account_repository

card_bp = Blueprint("card_bp", __name__)


@card_bp.route("/api/block_card", methods=["POST"])
@login_required
def block_card_api():
    csrf_err = verify_csrf_request()
    if csrf_err:
        return csrf_err

    auth_user = session.get("user_id")
    req = request.get_json(silent=True) or {}
    req_acc = str(req.get("account", auth_user)).strip()

    if req_acc != auth_user and session.get("role") != "admin":
        return jsonify({"success": False, "message": "Unauthorized account."}), 403

    target_acc = req_acc if session.get("role") == "admin" else auth_user
    success = card_service.block_debit_card(target_acc)
    if success:
        return jsonify({"success": True, "message": "Debit card securely blocked."})
    return jsonify({"success": False, "message": "No active debit card found."}), 400


@card_bp.route("/api/issue_card", methods=["POST"])
@login_required
def issue_card_api():
    csrf_err = verify_csrf_request()
    if csrf_err:
        return csrf_err

    auth_user = session.get("user_id")
    req = request.get_json(silent=True) or {}
    pin = req.get("pin", "")

    try:
        validate_pin(pin)
    except ValidationError:
        return jsonify({"success": False, "message": "Valid 4-digit PIN is required."}), 400

    res = card_service.issue_new_debit_card(auth_user, pin)
    if res["success"]:
        return jsonify(res)
    return jsonify(res), 400


@card_bp.route("/api/services/order_chequebook", methods=["POST"])
@login_required
def order_chequebook_api():
    csrf_err = verify_csrf_request()
    if csrf_err:
        return csrf_err

    auth_user = session.get("user_id")
    req = request.get_json(silent=True) or {}
    req_acc = str(req.get("account", auth_user)).strip()

    if req_acc != auth_user and session.get("role") != "admin":
        return jsonify({"success": False, "message": "Unauthorized account."}), 403

    leaves = req.get("leaves", "25")
    return jsonify({
        "success": True,
        "message": f"Chequebook with {leaves} leaves ordered successfully. Dispatched to registered address."
    })


@card_bp.route("/api/services/order_physical_card", methods=["POST"])
@login_required
def order_physical_card_api():
    csrf_err = verify_csrf_request()
    if csrf_err:
        return csrf_err

    auth_user = session.get("user_id")
    req = request.get_json(silent=True) or {}
    req_acc = str(req.get("account", auth_user)).strip()

    if req_acc != auth_user and session.get("role") != "admin":
        return jsonify({"success": False, "message": "Unauthorized account."}), 403

    card_type = sanitize_text(req.get("card_type", "Classic Debit"), max_length=30)
    return jsonify({
        "success": True,
        "message": f"Physical {card_type} card dispatched to registered address."
    })


@card_bp.route("/api/apply_cc", methods=["POST"])
@login_required
def apply_cc_api():
    csrf_err = verify_csrf_request()
    if csrf_err:
        return csrf_err

    auth_user = session.get("user_id")
    req = request.get_json(silent=True) or {}
    card_type = sanitize_text(req.get("card_type", "Credence Platinum"), max_length=50)

    return jsonify({
        "success": True,
        "message": f"Credit card application for {card_type} received. Pre-approved limit ₹150,000.00.",
        "result": f"Credit Card Application for {card_type} Approved."
    })
