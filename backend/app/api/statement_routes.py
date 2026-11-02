"""
Credence Core — Statements & Analytics Controller
"""

from flask import Blueprint, jsonify, session, make_response, request
from backend.app.middleware.auth_middleware import login_required, verify_account_ownership
from backend.app.services.statements import statement_service
from backend.app.services.analytics import analytics_service
from backend.app.core.security import sanitize_text, security_logger
from backend.app.core.database import get_db
from backend.app.repositories.transaction_repository import transaction_repository
from backend.app.utils.currency import rupees_to_paise

statement_bp = Blueprint("statement_bp", __name__)


@statement_bp.route("/api/statement/<acc_no>", methods=["GET"])
@statement_bp.route("/api/statement_pdf/<acc_no>", methods=["GET"])
@login_required
def get_statement_pdf_api(acc_no):
    acc_no = sanitize_text(str(acc_no).strip())
    if not verify_account_ownership(acc_no):
        security_logger.warning(f"Unauthorized statement access attempt on {acc_no} by {session.get('user_id')}")
        return jsonify({"success": False, "message": "Access denied: Unauthorized account access."}), 403

    pdf_bytes = statement_service.generate_pdf(acc_no)
    response = make_response(pdf_bytes)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f"attachment; filename=statement_{acc_no}.pdf"
    return response


@statement_bp.route("/api/analytics/<acc_no>", methods=["GET"])
@login_required
def get_analytics_api(acc_no):
    acc_no = sanitize_text(str(acc_no).strip())
    if not verify_account_ownership(acc_no):
        security_logger.warning(f"Unauthorized analytics access attempt on {acc_no} by {session.get('user_id')}")
        return jsonify({"success": False, "message": "Access denied: Unauthorized account access."}), 403

    analytics = statement_service.get_analytics(acc_no)
    return jsonify(analytics)


@statement_bp.route("/api/analytics/insights", methods=["GET"])
@login_required
def get_spending_insights_api():
    """Detailed monthly spending insights and inflow/outflow breakdown."""
    acc_no = session.get("user_id")
    insights = analytics_service.get_spending_insights(acc_no)
    return jsonify(insights)


@statement_bp.route("/api/transactions/search", methods=["GET"])
@login_required
def search_transactions_api():
    """Advanced search and multi-parameter filtering for transactions."""
    acc_no = session.get("user_id") if session.get("role") != "admin" else request.args.get("account_number")
    query = request.args.get("q") or request.args.get("search")
    txn_type = request.args.get("type")
    state = request.args.get("status") or request.args.get("state")
    min_amt = request.args.get("min_amount")
    max_amt = request.args.get("max_amount")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    limit = min(int(request.args.get("limit", 50)), 200)
    offset = int(request.args.get("offset", 0))

    min_paise = rupees_to_paise(float(min_amt)) if min_amt else None
    max_paise = rupees_to_paise(float(max_amt)) if max_amt else None

    with get_db() as db:
        txns = transaction_repository.search_transactions(
            db=db,
            account_number=acc_no,
            query=query,
            txn_type=txn_type,
            state=state,
            min_amount_paise=min_paise,
            max_amount_paise=max_paise,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            offset=offset
        )

        return jsonify({
            "success": True,
            "count": len(txns),
            "transactions": [
                {
                    "reference_id": t.reference_id,
                    "idempotency_key": t.idempotency_key,
                    "transaction_type": t.transaction_type,
                    "state": t.state,
                    "amount_rupees": t.amount_paise / 100.0,
                    "source_account": t.source_account,
                    "destination_account": t.destination_account,
                    "description": t.description,
                    "created_at": t.created_at.isoformat()
                }
                for t in txns
            ]
        })
