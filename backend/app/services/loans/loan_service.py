"""
Credence Core — Loan Service
Handles retail loan applications, disbursals, and repayments.
"""

from typing import Dict, Any, Optional
from backend.app.core.database import get_db
from backend.app.models import Loan
from backend.app.services.ledger import ledger_service, GL_LOAN_PRINCIPAL
from backend.app.utils.currency import rupees_to_paise


class LoanService:
    def apply_loan(self, account_number: str, amount: float, loan_type: str, actor: str, ip: str,
                   idempotency_key: Optional[str] = None) -> Dict[str, Any]:
        """Approve and disburse a retail loan."""
        acc_str = str(account_number).strip()
        from backend.app.repositories.account_repository import account_repository
        with get_db() as db:
            acc = account_repository.get_by_number(db, acc_str)
            if acc and acc.user and acc.user.role == "demo":
                raise ValueError("Demo accounts are read-only and cannot apply for or repay loans.")

        txn = ledger_service.execute(
            transaction_type="LOAN_DISBURSAL",
            amount_rupees=amount,
            source_account=GL_LOAN_PRINCIPAL,
            destination_account=acc_str,
            description=f"Loan Disbursal - {loan_type}",
            idempotency_key=idempotency_key,
            actor=actor,
            ip=ip,
            metadata={"loan_type": loan_type}
        )

        with get_db() as db:
            loan = db.query(Loan).filter(Loan.account_number == acc_str).first()
            amt_paise = rupees_to_paise(amount)
            if not loan:
                loan = Loan(
                    loan_id=f"LN-{acc_str[-6:]}",
                    account_number=acc_str,
                    loan_type=loan_type,
                    principal_amount_paise=amt_paise,
                    outstanding_amount_paise=amt_paise,
                    status="ACTIVE"
                )
                db.add(loan)
            else:
                loan.principal_amount_paise += amt_paise
                loan.outstanding_amount_paise += amt_paise
            db.commit()

        return txn

    def repay_loan(self, account_number: str, amount: float, actor: str, ip: str,
                   idempotency_key: Optional[str] = None) -> Dict[str, Any]:
        """Repay outstanding loan balance."""
        acc_str = str(account_number).strip()
        from backend.app.repositories.account_repository import account_repository
        with get_db() as db:
            acc = account_repository.get_by_number(db, acc_str)
            if acc and acc.user and acc.user.role == "demo":
                raise ValueError("Demo accounts are read-only and cannot apply for or repay loans.")

        txn = ledger_service.execute(
            transaction_type="LOAN_REPAYMENT",
            amount_rupees=amount,
            source_account=acc_str,
            destination_account=GL_LOAN_PRINCIPAL,
            description=f"Loan Repayment",
            idempotency_key=idempotency_key,
            actor=actor,
            ip=ip,
            metadata={"channel": "NETBANKING"}
        )

        with get_db() as db:
            loan = db.query(Loan).filter(Loan.account_number == acc_str).first()
            if loan:
                amt_paise = rupees_to_paise(amount)
                loan.outstanding_amount_paise = max(0, loan.outstanding_amount_paise - amt_paise)
                if loan.outstanding_amount_paise == 0:
                    loan.status = "CLOSED"
                db.commit()

        return txn


loan_service = LoanService()
