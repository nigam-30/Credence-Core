"""
Credence Core — Statement & Analytics Service
Compiles transaction history, computes spending analytics, and generates PDF statements.
"""

from typing import Dict, Any, List, Optional
from backend.app.core.database import get_db
from backend.app.models import LedgerEntry, Account
from backend.app.services.accounts import account_service
from backend.app.services.ledger import ledger_service
from backend.app.utils.pdf_generator import generate_account_statement_pdf


class StatementService:
    def get_account_history(self, account_number: str) -> List[Dict[str, Any]]:
        """Retrieve historical ledger entries for an account."""
        acc_str = str(account_number).strip()
        with get_db() as db:
            entries = (
                db.query(LedgerEntry)
                .filter(LedgerEntry.account_number == acc_str)
                .order_by(LedgerEntry.created_at.asc())
                .all()
            )
            history = []
            for e in entries:
                prefix = "+" if e.direction == "CREDIT" else "-"
                history.append({
                    "date": e.created_at.strftime("%d/%m/%Y %H:%M:%S"),
                    "type": e.description or ("Credit" if e.direction == "CREDIT" else "Debit"),
                    "amount": f"{prefix}{e.amount_paise / 100:.2f}",
                    "balance": f"{e.running_balance_paise / 100:.2f}",
                    "ref_id": e.reference_id,
                })
            return history

    def get_analytics(self, account_number: str) -> Dict[str, Any]:
        """Compute monthly spending analytics and cashflow metrics."""
        history = self.get_account_history(account_number)
        total_spent = 0.0
        total_income = 0.0
        categories = {
            "Transfers": 0.0,
            "Bills & Utilities": 0.0,
            "Investments & Wealth": 0.0,
            "Loans & EMI": 0.0,
            "Card & Other": 0.0
        }

        for item in history:
            amt_str = str(item.get("amount", "0")).replace(",", "")
            try:
                amt = float(amt_str)
            except Exception:
                continue

            narration = item.get("type", "").lower()
            if amt < 0:
                spend = abs(amt)
                total_spent += spend
                if "transfer" in narration or "imps" in narration or "neft" in narration:
                    categories["Transfers"] += spend
                elif "bill" in narration or "electricity" in narration or "water" in narration:
                    categories["Bills & Utilities"] += spend
                elif "sip" in narration or "gold" in narration or "rd" in narration or "fd" in narration:
                    categories["Investments & Wealth"] += spend
                elif "loan" in narration or "emi" in narration:
                    categories["Loans & EMI"] += spend
                else:
                    categories["Card & Other"] += spend
            elif amt > 0:
                total_income += amt

        return {
            "total_income": round(total_income, 2),
            "total_spent": round(total_spent, 2),
            "net_savings": round(total_income - total_spent, 2),
            "categories": {k: round(v, 2) for k, v in categories.items()}
        }

    def generate_pdf(self, account_number: str) -> bytes:
        """Generate PDF statement document for account."""
        details = account_service.get_account_details(account_number) or {}
        details["history"] = self.get_account_history(account_number)
        return generate_account_statement_pdf(account_number, details)


statement_service = StatementService()
