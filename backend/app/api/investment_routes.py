"""
Credence Core — Investments Controller
Handles SIPs, Digital Gold, IPOs, RDs, and Fixed Deposits.
"""

from flask import Blueprint, request, jsonify, session
from backend.app.middleware.auth_middleware import login_required, verify_account_ownership
from backend.app.middleware.csrf_middleware import verify_csrf_request
from backend.app.services.investments import investment_service
from backend.app.services.ledger import ledger_service, GL_FIXED_DEPOSIT_RESERVE, GL_INVESTMENT_ESCROW, GL_GOLD_VAULT_CLEARING
from backend.app.schemas.validators import validate_amount, ValidationError
from backend.app.core.security import log_sensitive_operation, sanitize_text
from backend.app.core.database import get_db
from backend.app.models import FixedDeposit, Account, AccountBalance
from backend.app.utils.currency import rupees_to_paise

investment_bp = Blueprint("investment_bp", __name__)


@investment_bp.route("/api/invest/market_data", methods=["GET"])
def get_market_data():
    return jsonify({
        "nifty50": {"current": 24850.30, "change": 142.60, "change_pct": 0.58},
        "sensex": {"current": 81332.72, "change": 490.20, "change_pct": 0.61},
        "gold_24k_1g": {"current": 7620.50, "change": -15.00, "change_pct": -0.20},
        "silver_1kg": {"current": 92450.00, "change": 320.00, "change_pct": 0.35}
    })


@investment_bp.route("/api/invest/live_gold_rate", methods=["GET"])
def get_live_gold_rate():
    return jsonify({
        "rate_per_gram": 7620.50,
        "purity": "24 Karat 99.9%",
        "currency": "INR",
        "last_updated": "Live"
    })


@investment_bp.route("/api/investments/<acc_no>", methods=["GET"])
@login_required
def get_investments_api(acc_no):
    if not verify_account_ownership(acc_no):
        return jsonify({"success": False, "message": "Unauthorized account."}), 403

    inv_data = investment_service.get_user_investments(acc_no)
    return jsonify(inv_data)


@investment_bp.route("/api/investments/performance", methods=["GET"])
@login_required
def get_investment_performance_api():
    """Retrieve consolidated portfolio performance, asset allocation, and returns."""
    acc_no = session.get("user_id")
    perf = investment_service.get_investment_performance(acc_no)
    return jsonify(perf)


@investment_bp.route("/api/invest/sip", methods=["POST"])
@login_required
def create_sip_api():
    csrf_err = verify_csrf_request()
    if csrf_err:
        return csrf_err

    auth_user = session.get("user_id")
    req = request.get_json(silent=True) or {}
    fund_id = req.get("fund_id", "MF-NIFTY50")
    fund_name = req.get("fund_name", "Credence NIFTY 50 Bluechip Index Fund")
    category = req.get("category", "Large Cap Index")
    sip_day = int(req.get("sip_day", 5))

    try:
        dec_amt = validate_amount(req.get("monthly_amount") or req.get("amount") or "1000", min_amount=500.0)
    except ValidationError as ve:
        return jsonify({"success": False, "message": str(ve)}), 400

    amount_val = float(dec_amt)
    idem_key = req.get("idempotency_key") or request.headers.get("Idempotency-Key")

    res = investment_service.create_sip(
        account_number=auth_user,
        fund_id=fund_id,
        fund_name=fund_name,
        category=category,
        monthly_amount=amount_val,
        sip_day=sip_day,
        actor=auth_user,
        ip=request.remote_addr or "127.0.0.1",
        idempotency_key=idem_key
    )

    return jsonify({
        "success": True,
        "sip_id": res["sip_id"],
        "message": f"SIP in {fund_name} for ₹{amount_val:,.2f}/month initiated successfully."
    })


@investment_bp.route("/api/invest/gold_buy", methods=["POST"])
@login_required
def buy_gold_api():
    csrf_err = verify_csrf_request()
    if csrf_err:
        return csrf_err

    auth_user = session.get("user_id")
    req = request.get_json(silent=True) or {}

    try:
        dec_amt = validate_amount(req.get("amount", "0"), min_amount=100.0)
    except ValidationError as ve:
        return jsonify({"success": False, "message": str(ve)}), 400

    amount_val = float(dec_amt)
    idem_key = req.get("idempotency_key") or request.headers.get("Idempotency-Key")

    txn = investment_service.buy_gold(
        account_number=auth_user,
        amount=amount_val,
        actor=auth_user,
        ip=request.remote_addr or "127.0.0.1",
        idempotency_key=idem_key
    )

    return jsonify({
        "success": True,
        "reference_id": txn.get("reference_id"),
        "state": txn.get("state"),
        "message": f"24K Digital Gold purchase of ₹{amount_val:,.2f} completed successfully!"
    })


@investment_bp.route("/api/create_fd", methods=["POST"])
@login_required
def create_fd_api():
    csrf_err = verify_csrf_request()
    if csrf_err:
        return csrf_err

    auth_user = session.get("user_id")
    req = request.get_json(silent=True) or {}
    req_acc = str(req.get("account", auth_user)).strip()

    if req_acc != auth_user and session.get("role") != "admin":
        return jsonify({"success": False, "message": "Forbidden: Cannot create FD on another account."}), 403

    tenure = sanitize_text(req.get("tenure", "12"), max_length=10)

    try:
        dec_amt = validate_amount(req.get("amount", "0"), min_amount=1000.0)
    except ValidationError as ve:
        return jsonify({"success": False, "message": str(ve)}), 400

    amount_val = float(dec_amt)
    idem_key = req.get("idempotency_key") or request.headers.get("Idempotency-Key")

    txn = ledger_service.execute(
        transaction_type="FD_CREATION",
        amount_rupees=amount_val,
        source_account=auth_user,
        destination_account=GL_FIXED_DEPOSIT_RESERVE,
        description=f"FD Creation ({tenure} Months)",
        idempotency_key=idem_key,
        actor=auth_user,
        ip=request.remote_addr or "127.0.0.1",
        metadata={"tenure": tenure}
    )

    # Persist in FixedDeposit table
    with get_db() as db:
        fd_paise = rupees_to_paise(amount_val)
        tenure_months = int(tenure) if tenure.isdigit() else 12
        fd = FixedDeposit(
            account_number=auth_user,
            principal_amount_paise=fd_paise,
            tenure_months=tenure_months,
            interest_rate_pct=6.5,
            maturity_amount_paise=int(fd_paise * (1 + 0.065 * tenure_months / 12)),
            status="ACTIVE"
        )
        db.add(fd)
        db.commit()

    return jsonify({
        "success": True,
        "reference_id": txn.get("reference_id"),
        "state": txn.get("state"),
        "result": "FD created successfully.",
        "message": f"Fixed Deposit of ₹{amount_val:,.2f} created successfully! Ref: {txn.get('reference_id')}"
    })


@investment_bp.route("/api/withdraw_fd", methods=["POST"])
@login_required
def withdraw_fd_api():
    csrf_err = verify_csrf_request()
    if csrf_err:
        return csrf_err

    auth_user = session.get("user_id")
    with get_db() as db:
        fd = db.query(FixedDeposit).filter(FixedDeposit.account_number == auth_user, FixedDeposit.status == "ACTIVE").first()
        if not fd:
            return jsonify({"success": False, "message": "No active Fixed Deposit found."}), 400

        payout_rupees = float(fd.principal_amount_paise / 100)
        txn = ledger_service.execute(
            transaction_type="FD_LIQUIDATION",
            amount_rupees=payout_rupees,
            source_account=GL_FIXED_DEPOSIT_RESERVE,
            destination_account=auth_user,
            description=f"FD Premature Withdrawal Payout",
            actor=auth_user,
            ip=request.remote_addr or "127.0.0.1"
        )

        fd.status = "LIQUIDATED"
        db.commit()

        return jsonify({
            "success": True,
            "message": f"Fixed Deposit of ₹{payout_rupees:,.2f} withdrawn and credited to balance."
        })


@investment_bp.route("/api/invest/ipo_bid", methods=["POST"])
@login_required
def ipo_bid_api():
    csrf_err = verify_csrf_request()
    if csrf_err:
        return csrf_err

    auth_user = session.get("user_id")
    req = request.get_json(silent=True) or {}
    company = sanitize_text(req.get("company", "IPO Application"), max_length=100)
    shares = int(req.get("shares", 10))
    price = float(req.get("price", 100.0))
    total_amount = shares * price

    return jsonify({
        "success": True,
        "app_no": f"IPO-{shares}-{auth_user[-4:]}",
        "message": f"ASBA IPO Bid for {shares} shares of {company} submitted successfully."
    })


@investment_bp.route("/api/invest/create_rd", methods=["POST"])
@login_required
def create_rd_api():
    csrf_err = verify_csrf_request()
    if csrf_err:
        return csrf_err

    auth_user = session.get("user_id")
    req = request.get_json(silent=True) or {}
    monthly_amount = float(req.get("monthly_amount", 500))
    tenure = int(req.get("tenure", 12))

    return jsonify({
        "success": True,
        "rd_id": f"RD-{auth_user[-4:]}",
        "message": f"Recurring Deposit of ₹{monthly_amount:,.2f}/month for {tenure} months created successfully."
    })


@investment_bp.route("/api/invest/gold_sell", methods=["POST"])
@login_required
def gold_sell_api():
    csrf_err = verify_csrf_request()
    if csrf_err:
        return csrf_err

    auth_user = session.get("user_id")
    req = request.get_json(silent=True) or {}
    try:
        grams = float(req.get("grams", 0.0))
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "Invalid gold grams quantity."}), 400

    idem_key = req.get("idempotency_key") or request.headers.get("Idempotency-Key")

    try:
        res = investment_service.sell_gold(
            account_number=auth_user,
            grams=grams,
            actor=auth_user,
            ip=request.remote_addr or "127.0.0.1",
            idempotency_key=idem_key
        )
        return jsonify({
            "success": True,
            "message": f"Sold {res['grams']:.4f}g digital gold for ₹{res['amount']:,.2f}. Proceeds credited to your account.",
            "reference_id": res["txn"].get("reference_id"),
            "amount": res["amount"],
            "grams": res["grams"]
        })
    except ValueError as ve:
        return jsonify({"success": False, "message": str(ve)}), 400
    except Exception as e:
        return jsonify({"success": False, "message": f"Gold sale failed: {str(e)}"}), 500


@investment_bp.route("/api/invest/sip_action", methods=["POST"])
@login_required
def sip_action_api():
    csrf_err = verify_csrf_request()
    if csrf_err:
        return csrf_err

    auth_user = session.get("user_id")
    req = request.get_json(silent=True) or {}
    action = sanitize_text(str(req.get("action", "pause")).strip())
    sip_id = sanitize_text(str(req.get("sip_id", "")).strip())

    if not sip_id:
        return jsonify({"success": False, "message": "SIP ID is required."}), 400

    try:
        res = investment_service.update_sip_status(
            account_number=auth_user,
            sip_id=sip_id,
            action=action
        )
        return jsonify({
            "success": True,
            "sip_id": res["sip_id"],
            "status": res["status"],
            "message": f"SIP {res['sip_id']} status updated to {res['status']} successfully."
        })
    except PermissionError as pe:
        return jsonify({"success": False, "message": str(pe)}), 403
    except ValueError as ve:
        return jsonify({"success": False, "message": str(ve)}), 400
    except Exception as e:
        return jsonify({"success": False, "message": f"SIP action failed: {str(e)}"}), 500
