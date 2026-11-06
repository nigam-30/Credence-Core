"""
Credence Core — Loans Controller
"""

from flask import Blueprint, request, jsonify, session
from backend.app.middleware.auth_middleware import login_required, verify_account_ownership
from backend.app.middleware.csrf_middleware import verify_csrf_request
from backend.app.services.loans import loan_service
from backend.app.schemas.validators import validate_amount, ValidationError
from backend.app.core.security import sanitize_text
from backend.app.core.database import get_db
from backend.app.models import Loan

loan_bp = Blueprint("loan_bp", __name__)


@loan_bp.route("/api/apply_loan", methods=["POST"])
@login_required
def apply_loan_api():
    csrf_err = verify_csrf_request()
    if csrf_err:
        return csrf_err

    auth_user = session.get("user_id")
    req = request.get_json(silent=True) or {}
    req_acc = str(req.get("account", auth_user)).strip()

    if req_acc != auth_user and session.get("role") != "admin":
        return jsonify({"success": False, "message": "Forbidden: Cannot apply for loan on another account."}), 403

    loan_type = sanitize_text(req.get("loan_type", "Personal Loan"), max_length=50)

    try:
        dec_amt = validate_amount(req.get("amount", "0"), min_amount=1000.0)
    except ValidationError as ve:
        return jsonify({"success": False, "message": str(ve)}), 400

    amount_val = float(dec_amt)
    idem_key = req.get("idempotency_key") or request.headers.get("Idempotency-Key")

    target_acc = req_acc if session.get("role") == "admin" else auth_user
    txn = loan_service.apply_loan(
        account_number=target_acc,
        amount=amount_val,
        loan_type=loan_type,
        actor=auth_user,
        ip=request.remote_addr or "127.0.0.1",
        idempotency_key=idem_key
    )

    return jsonify({
        "success": True,
        "reference_id": txn.get("reference_id"),
        "state": txn.get("state"),
        "result": f"Loan of INR {amount_val:.2f} approved and credited.",
        "message": f"Loan of ₹{amount_val:,.2f} disbursed successfully! Ref: {txn.get('reference_id')}"
    })


@loan_bp.route("/api/repay_loan", methods=["POST"])
@login_required
def repay_loan_api():
    csrf_err = verify_csrf_request()
    if csrf_err:
        return csrf_err

    auth_user = session.get("user_id")
    req = request.get_json(silent=True) or {}
    req_acc = str(req.get("account", auth_user)).strip()

    if req_acc != auth_user and session.get("role") != "admin":
        return jsonify({"success": False, "message": "Forbidden: Cannot repay loan on another account."}), 403

    try:
        dec_amt = validate_amount(req.get("amount", "0"), min_amount=100.0)
    except ValidationError as ve:
        return jsonify({"success": False, "message": str(ve)}), 400

    amount_val = float(dec_amt)
    idem_key = req.get("idempotency_key") or request.headers.get("Idempotency-Key")

    target_acc = req_acc if session.get("role") == "admin" else auth_user
    txn = loan_service.repay_loan(
        account_number=target_acc,
        amount=amount_val,
        actor=auth_user,
        ip=request.remote_addr or "127.0.0.1",
        idempotency_key=idem_key
    )

    return jsonify({
        "success": True,
        "reference_id": txn.get("reference_id"),
        "state": txn.get("state"),
        "result": f"Loan repayment of INR {amount_val:.2f} successful.",
        "message": f"Loan repayment of ₹{amount_val:,.2f} completed! Ref: {txn.get('reference_id')}"
    })


@loan_bp.route("/api/loans/<acc_no>", methods=["GET"])
@login_required
def get_loans_api(acc_no):
    if not verify_account_ownership(acc_no):
        return jsonify({"success": False, "message": "Unauthorized account."}), 403

    with get_db() as db:
        loan = db.query(Loan).filter(Loan.account_number == str(acc_no)).first()
        if not loan:
            return jsonify({
                "loans": [],
                "total_outstanding": 0.0,
                "active_loans_count": 0
            })

        outstanding = float(loan.outstanding_amount_paise / 100)
        return jsonify({
            "loans": [
                {
                    "loan_id": loan.loan_id,
                    "type": loan.loan_type,
                    "principal": float(loan.principal_amount_paise / 100),
                    "outstanding": outstanding,
                    "interest_rate": float(loan.interest_rate_pct),
                    "emi": float(loan.monthly_emi_paise / 100),
                    "status": loan.status
                }
            ],
            "total_outstanding": outstanding,
            "active_loans_count": 1 if loan.status == "ACTIVE" else 0
        })
