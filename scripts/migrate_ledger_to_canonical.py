"""
Credence Core — Migrate Dual SQLite Ledger into Canonical Database
Copies all historical ledger entries, transactions, audit trail, and account balances
into the canonical database (PostgreSQL / SQLAlchemy).
"""

import os
import sys
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import engine, get_db
from models import Account, AccountBalance, Transaction, LedgerEntry, AuditTrail, Dispute

LEDGER_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ledger.db")

def migrate():
    if not os.path.exists(LEDGER_DB_PATH):
        print(f"ledger.db not found at {LEDGER_DB_PATH}. Skipping migration.")
        return

    src_conn = sqlite3.connect(LEDGER_DB_PATH)
    src_conn.row_factory = sqlite3.Row
    src_c = src_conn.cursor()

    with get_db() as db:
        # Clear existing entries in correct dependency order
        db.query(Dispute).delete()
        db.query(LedgerEntry).delete()
        db.query(AuditTrail).delete()
        db.query(Transaction).delete()
        db.flush()

        # 1. Accounts & Balances
        src_c.execute("SELECT * FROM accounts")
        for row in src_c.fetchall():
            acc_num = row["account_number"]
            acc = db.query(Account).filter(Account.account_number == acc_num).first()
            if not acc:
                acc = Account(
                    account_number=acc_num,
                    account_type=row["account_type"] or "CUSTOMER_SAVINGS",
                    currency=row["currency"] or "INR",
                    status=row["status"] or "ACTIVE",
                    daily_transfer_limit_paise=row["daily_transfer_limit_paise"] or 50000000,
                    daily_transferred_paise=row["daily_transferred_paise"] or 0,
                    last_limit_reset_date=row["last_limit_reset_date"]
                )
                db.add(acc)
                db.flush()
            else:
                acc.status = row["status"] or acc.status
                acc.daily_transfer_limit_paise = row["daily_transfer_limit_paise"] or acc.daily_transfer_limit_paise
                acc.daily_transferred_paise = row["daily_transferred_paise"] or acc.daily_transferred_paise
                acc.last_limit_reset_date = row["last_limit_reset_date"] or acc.last_limit_reset_date

            bal = db.query(AccountBalance).filter(AccountBalance.account_number == acc_num).first()
            if not bal:
                bal = AccountBalance(
                    account_number=acc_num,
                    balance_paise=row["balance_paise"] or 0,
                    lien_paise=row["lien_paise"] or 0
                )
                db.add(bal)
            else:
                bal.balance_paise = row["balance_paise"] or 0
                bal.lien_paise = row["lien_paise"] or 0
        db.flush()

        # 2. Transactions
        src_c.execute("SELECT * FROM transactions")
        for row in src_c.fetchall():
            txn = Transaction(
                reference_id=row["reference_id"],
                idempotency_key=row["idempotency_key"],
                transaction_type=row["transaction_type"],
                state=row["state"],
                amount_paise=row["amount_paise"],
                source_account=row["source_account"],
                destination_account=row["destination_account"],
                description=row["description"],
                metadata_json=row["metadata_json"],
                error_reason=row["error_reason"],
                original_reference_id=row["original_reference_id"]
            )
            db.add(txn)
        db.flush()

        # 3. Ledger Entries
        src_c.execute("SELECT * FROM ledger_entries")
        for row in src_c.fetchall():
            le = LedgerEntry(
                reference_id=row["reference_id"],
                account_number=row["account_number"],
                direction=row["direction"],
                amount_paise=row["amount_paise"],
                running_balance_paise=row["running_balance_paise"],
                description=row["description"]
            )
            db.add(le)
        db.flush()

        # Re-align cached balance_paise to match canonical double-entry ledger legs exactly
        from sqlalchemy import func
        for bal in db.query(AccountBalance).all():
            acc_num = bal.account_number
            deb = db.query(func.coalesce(func.sum(LedgerEntry.amount_paise), 0)).filter(
                LedgerEntry.account_number == acc_num, LedgerEntry.direction == "DEBIT"
            ).scalar() or 0
            cred = db.query(func.coalesce(func.sum(LedgerEntry.amount_paise), 0)).filter(
                LedgerEntry.account_number == acc_num, LedgerEntry.direction == "CREDIT"
            ).scalar() or 0
            acc = db.query(Account).filter(Account.account_number == acc_num).first()
            is_asset = (acc and acc.account_type == "GL_ASSET") or (acc_num in ("GL_CASH_VAULT", "GL_LOAN_PRINCIPAL"))
            computed = (deb - cred) if is_asset else (cred - deb)
            bal.balance_paise = computed
        db.flush()

        # 4. Audit Trail
        src_c.execute("SELECT * FROM audit_trail")
        for row in src_c.fetchall():
            at = AuditTrail(
                reference_id=row["reference_id"],
                action=row["action"],
                from_state=row["from_state"],
                to_state=row["to_state"],
                actor=row["actor"] or "SYSTEM",
                ip_address=row["ip_address"] or "127.0.0.1",
                details_json=row["details_json"]
            )
            db.add(at)

    print("Canonical ledger migration successfully finished.")

if __name__ == "__main__":
    migrate()
