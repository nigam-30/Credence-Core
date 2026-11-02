"""
Credence Core — Account Repository
Handles Account and AccountBalance records, limits, and lookups.
"""

from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from backend.app.models import Account, AccountBalance
from backend.app.repositories.base_repository import BaseRepository


class AccountRepository(BaseRepository[Account]):
    def __init__(self):
        super().__init__(Account)

    def get_by_number(self, db: Session, account_number: str) -> Optional[Account]:
        return db.query(Account).filter(Account.account_number == str(account_number).strip()).first()

    def get_balance_record(self, db: Session, account_number: str) -> Optional[AccountBalance]:
        return db.query(AccountBalance).filter(AccountBalance.account_number == str(account_number).strip()).first()

    def update_balance(self, db: Session, account_number: str, new_balance_paise: int) -> AccountBalance:
        bal = self.get_balance_record(db, account_number)
        if not bal:
            bal = AccountBalance(account_number=account_number, balance_paise=new_balance_paise, lien_paise=0)
            db.add(bal)
        else:
            bal.balance_paise = new_balance_paise
            bal.version += 1
        db.flush()
        return bal

    def list_customer_accounts(self, db: Session) -> List[Account]:
        return db.query(Account).filter(~Account.account_number.in_(["99999999999999", "999999"])).all()


account_repository = AccountRepository()
