"""
Credence Core — Card Repository
Handles Debit, Credit, and Virtual Card persistence.
"""

from typing import Optional, List
from sqlalchemy.orm import Session
from backend.app.models import Card


class CardRepository:
    def get_by_account_number(self, db: Session, account_number: str) -> Optional[Card]:
        return db.query(Card).filter(Card.account_number == account_number).first()

    def get_by_card_number(self, db: Session, card_number_masked: str) -> Optional[Card]:
        return db.query(Card).filter(Card.card_number_masked == card_number_masked).first()


card_repository = CardRepository()
