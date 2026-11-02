"""
Credence Core — Card Service
Handles card issuance, status modification, PIN management, and credit card applications.
"""

from typing import Dict, Any, Optional
from backend.app.core.database import get_db
from backend.app.models import Card, Account
from backend.app.core.security import hash_pin, mask_card


class CardService:
    def block_debit_card(self, account_number: str) -> bool:
        """Block active debit card."""
        acc_str = str(account_number).strip()
        from backend.app.repositories.account_repository import account_repository
        with get_db() as db:
            acc = account_repository.get_by_number(db, acc_str)
            if acc and acc.user and acc.user.role == "demo":
                return False
            card = db.query(Card).filter(Card.account_number == acc_str, Card.status == "ACTIVE").first()
            if not card:
                return False
            card.status = "BLOCKED"
            db.commit()
            return True

    def issue_new_debit_card(self, account_number: str, pin: str) -> Dict[str, Any]:
        """Issue a new debit card if no active card exists."""
        acc_str = str(account_number).strip()
        from backend.app.repositories.account_repository import account_repository
        with get_db() as db:
            acc = account_repository.get_by_number(db, acc_str)
            if acc and acc.user and acc.user.role == "demo":
                return {"success": False, "message": "Demo accounts are read-only and cannot request cards."}

            active_card = db.query(Card).filter(Card.account_number == acc_str, Card.status == "ACTIVE").first()
            if active_card:
                return {"success": False, "message": "You already have an active debit card."}

            card_num = f"4092 8819 2401 {acc_str[-4:]}"
            card = Card(
                account_number=acc_str,
                card_type="DEBIT",
                card_number_masked=card_num,
                card_network="Visa",
                expiry_month_year="10/30",
                pin_hash=hash_pin(pin),
                status="ACTIVE"
            )
            db.add(card)
            db.commit()
            return {
                "success": True,
                "message": "New debit card issued successfully.",
                "card": {
                    "cardNumber": card_num,
                    "expiry": "10/30",
                    "company": "Visa"
                }
            }


card_service = CardService()
