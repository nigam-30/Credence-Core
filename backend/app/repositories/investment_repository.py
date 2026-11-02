"""
Credence Core — Investment Repository
Handles Gold, SIPs, IPO Applications, and Recurring Deposits persistence.
"""

from typing import Optional, List
from sqlalchemy.orm import Session
from backend.app.models import Investment, SIP, IPOApplication, RecurringDeposit


class InvestmentRepository:
    def get_gold_investment(self, db: Session, account_number: str) -> Optional[Investment]:
        return db.query(Investment).filter(Investment.account_number == account_number).first()

    def list_sips(self, db: Session, account_number: str) -> List[SIP]:
        return db.query(SIP).filter(SIP.account_number == account_number).all()

    def get_sip_by_id(self, db: Session, sip_id: str) -> Optional[SIP]:
        return db.query(SIP).filter(SIP.sip_id == sip_id).first()

    def list_ipos(self, db: Session, account_number: str) -> List[IPOApplication]:
        return db.query(IPOApplication).filter(IPOApplication.account_number == account_number).all()

    def list_rds(self, db: Session, account_number: str) -> List[RecurringDeposit]:
        return db.query(RecurringDeposit).filter(RecurringDeposit.account_number == account_number).all()


investment_repository = InvestmentRepository()
