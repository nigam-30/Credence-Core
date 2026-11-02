"""
Credence Core — User Repository
Handles User identity persistence, lookup by CIF, email, PAN.
"""

from typing import Optional, List
from sqlalchemy.orm import Session
from backend.app.models import User
from backend.app.repositories.base_repository import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self):
        super().__init__(User)

    def get_by_customer_id(self, db: Session, customer_id: str) -> Optional[User]:
        return db.query(User).filter(User.customer_id == customer_id).first()

    def get_by_email(self, db: Session, email: str) -> Optional[User]:
        if not email:
            return None
        return db.query(User).filter(User.email == email.lower().strip()).first()

    def get_by_account_number(self, db: Session, account_number: str) -> Optional[User]:
        from backend.app.models import Account
        acc = db.query(Account).filter(Account.account_number == account_number).first()
        return acc.user if acc else None


user_repository = UserRepository()
