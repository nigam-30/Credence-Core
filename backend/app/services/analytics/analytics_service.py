"""
Credence Core — Financial Analytics & Spending Insights Service (Phase 5)
Calculates monthly category breakdowns, cash flow inflow vs outflow,
spending velocity, and personalized budget insights from verified ledger entries.
"""

from typing import Dict, Any, List
from collections import defaultdict
import datetime
from sqlalchemy import func

from backend.app.core.database import get_db
from backend.app.models import Account, Transaction, LedgerEntry, AccountBalance


class AnalyticsService:

    def get_spending_insights(self, account_number: str) -> Dict[str, Any]:
        """Compute spending insights, inflow/outflow, and category distribution."""
        acc_str = str(account_number).strip()
        with get_db() as db:
            # Query all ledger entries for this account
            entries = db.query(LedgerEntry).filter(
                LedgerEntry.account_number == acc_str
            ).order_by(LedgerEntry.id.desc()).all()

            total_inflow_paise = 0
            total_outflow_paise = 0
            category_totals_paise = defaultdict(int)
            monthly_trend = defaultdict(lambda: {"inflow_paise": 0, "outflow_paise": 0})

            for e in entries:
                amount = e.amount_paise
                direction = e.direction  # "DEBIT" or "CREDIT"
                month_key = e.created_at.strftime("%b %Y")

                if direction == "CREDIT":
                    total_inflow_paise += amount
                    monthly_trend[month_key]["inflow_paise"] += amount
                else:
                    total_outflow_paise += amount
                    monthly_trend[month_key]["outflow_paise"] += amount

                    # Categorize debit entries based on transaction type or description
                    desc = (e.description or "").lower()
                    if "bill" in desc or "utility" in desc or "electricity" in desc or "mobile" in desc:
                        cat = "Utilities & Bills"
                    elif "card" in desc or "debit" in desc or "merchant" in desc:
                        cat = "Card & Shopping"
                    elif "sip" in desc or "gold" in desc or "invest" in desc or "deposit" in desc:
                        cat = "Investments & Savings"
                    elif "loan" in desc or "emi" in desc:
                        cat = "Loan Repayments"
                    elif "transfer" in desc:
                        cat = "Money Transfers"
                    else:
                        cat = "General Banking"

                    category_totals_paise[cat] += amount

            # Total Balance
            bal_rec = db.query(AccountBalance).filter(AccountBalance.account_number == acc_str).first()
            current_balance = (bal_rec.balance_paise / 100.0) if bal_rec else 0.0

            # Convert paise to rupees
            inflow_rupees = total_inflow_paise / 100.0
            outflow_rupees = total_outflow_paise / 100.0
            net_savings_rupees = inflow_rupees - outflow_rupees
            savings_rate = (net_savings_rupees / inflow_rupees * 100.0) if inflow_rupees > 0 else 0.0

            categories = [
                {
                    "category": cat,
                    "amount_rupees": amt_paise / 100.0,
                    "percentage": round((amt_paise / total_outflow_paise * 100.0), 1) if total_outflow_paise > 0 else 0.0
                }
                for cat, amt_paise in sorted(category_totals_paise.items(), key=lambda x: x[1], reverse=True)
            ]

            trend_list = [
                {
                    "month": m,
                    "inflow_rupees": data["inflow_paise"] / 100.0,
                    "outflow_rupees": data["outflow_paise"] / 100.0,
                    "net_rupees": (data["inflow_paise"] - data["outflow_paise"]) / 100.0
                }
                for m, data in monthly_trend.items()
            ]

            # Generate smart budgeting insights
            insights = []
            if savings_rate >= 30:
                insights.append(f"Excellent savings rate of {savings_rate:.1f}%. You are exceeding healthy financial baselines.")
            elif savings_rate > 0:
                insights.append(f"Your savings rate is {savings_rate:.1f}%. Consider setting up an automatic SIP to boost wealth accumulation.")
            else:
                insights.append("Outflow currently exceeds inflow. Review high-expenditure categories to optimize cash flow.")

            if categories:
                top_cat = categories[0]
                insights.append(f"Highest expenditure is in '{top_cat['category']}' representing {top_cat['percentage']}% of total outflow.")

            return {
                "success": True,
                "current_balance": current_balance,
                "cash_flow": {
                    "total_inflow_rupees": inflow_rupees,
                    "total_outflow_rupees": outflow_rupees,
                    "net_savings_rupees": net_savings_rupees,
                    "savings_rate_pct": round(savings_rate, 2)
                },
                "category_breakdown": categories,
                "monthly_trend": trend_list,
                "advisory_insights": insights
            }


analytics_service = AnalyticsService()
