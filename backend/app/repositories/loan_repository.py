"""
Credence Core — Loan Repository
Handles Loan accounts and repayment records.
"""

from typing import Optional, List
from sqlalchemy.orm import Session
from backend.app.models import Loan


class LoanRepository:
    def get_by_account_number(self, db: Session, account_number: str) -> Optional[Loan]:
        return db.query(Loan).filter(Loan.account_number == account_number).first()

    def get_by_loan_id(self, db: Session, loan_id: str) -> Optional[Loan]:
        return db.query(Loan).filter(Loan.loan_id == loan_id).first()


loan_repository = LoanRepository()
