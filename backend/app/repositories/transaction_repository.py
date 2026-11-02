"""
Credence Core — Transaction & Ledger Repository
Handles persistence of Transactions and Ledger Entries.
"""

import datetime
from typing import Optional, List
from sqlalchemy.orm import Session
from backend.app.models import Transaction, LedgerEntry
from backend.app.repositories.base_repository import BaseRepository


class TransactionRepository(BaseRepository[Transaction]):
    def __init__(self):
        super().__init__(Transaction)

    def get_by_reference_id(self, db: Session, reference_id: str) -> Optional[Transaction]:
        return db.query(Transaction).filter(Transaction.reference_id == reference_id).first()

    def get_by_idempotency_key(self, db: Session, key: str) -> Optional[Transaction]:
        if not key:
            return None
        return db.query(Transaction).filter(Transaction.idempotency_key == key).first()

    def list_account_entries(self, db: Session, account_number: str) -> List[LedgerEntry]:
        return (
            db.query(LedgerEntry)
            .filter(LedgerEntry.account_number == str(account_number))
            .order_by(LedgerEntry.created_at.asc())
            .all()
        )


    def search_transactions(
        self,
        db: Session,
        account_number: Optional[str] = None,
        query: Optional[str] = None,
        txn_type: Optional[str] = None,
        state: Optional[str] = None,
        min_amount_paise: Optional[int] = None,
        max_amount_paise: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Transaction]:
        q = db.query(Transaction)
        if account_number:
            q = q.filter(
                (Transaction.source_account == account_number) |
                (Transaction.destination_account == account_number)
            )
        if query:
            pattern = f"%{query}%"
            q = q.filter(
                (Transaction.reference_id.ilike(pattern)) |
                (Transaction.description.ilike(pattern)) |
                (Transaction.source_account.ilike(pattern)) |
                (Transaction.destination_account.ilike(pattern))
            )
        if txn_type:
            q = q.filter(Transaction.transaction_type.ilike(f"%{txn_type}%"))
        if state:
            q = q.filter(Transaction.state == state.upper())
        if min_amount_paise is not None:
            q = q.filter(Transaction.amount_paise >= min_amount_paise)
        if max_amount_paise is not None:
            q = q.filter(Transaction.amount_paise <= max_amount_paise)
        if start_date:
            try:
                dt_start = datetime.datetime.fromisoformat(start_date)
                q = q.filter(Transaction.created_at >= dt_start)
            except Exception:
                pass
        if end_date:
            try:
                dt_end = datetime.datetime.fromisoformat(end_date)
                q = q.filter(Transaction.created_at <= dt_end)
            except Exception:
                pass

        return q.order_by(Transaction.id.desc()).offset(offset).limit(limit).all()


transaction_repository = TransactionRepository()
