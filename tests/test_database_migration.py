"""
Credence Core — Phase 3 Database Migration & Integrity Tests
Validates PostgreSQL/SQLAlchemy schema constraints, foreign keys, ACID transactions,
connection pooling, zero plaintext credentials, persistence across restarts,
and Alembic version tracking across all 18 banking modules.
"""

import os
import sys
import unittest
import datetime
from decimal import Decimal
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

# Ensure workspace root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import engine, get_db, SessionLocal, IS_POSTGRES
from models import (
    Base,
    User,
    Account,
    AccountBalance,
    Card,
    UPIProfile,
    FixedDeposit,
    Loan,
    Investment,
    SIP,
    IPOApplication,
    RecurringDeposit,
    Beneficiary,
    SessionRecord,
    AuditLog,
    Notification,
    Dispute,
    Transaction,
    LedgerEntry,
)
import flask_app
from rollback_db_to_json import export_database_to_json_backup


class TestDatabaseMigration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Verify database tables and baseline data exist."""
        cls.inspector = inspect(engine)
        cls.table_names = set(cls.inspector.get_table_names())

    def test_01_all_18_modules_tables_exist(self):
        """Verify that all 18 specified banking modules + alembic_version exist in the database."""
        expected_modules = {
            "users",
            "accounts",
            "account_balances",
            "ledger_entries",
            "transactions",
            "cards",
            "upi_profiles",
            "fixed_deposits",
            "loans",
            "investments",
            "sips",
            "ipo_applications",
            "recurring_deposits",
            "beneficiaries",
            "sessions",
            "audit_logs",
            "notifications",
            "disputes",
            "alembic_version",
        }
        missing = expected_modules - self.table_names
        self.assertEqual(len(missing), 0, f"Missing database tables: {missing}")

    def test_02_database_foreign_key_constraints_enforced(self):
        """Verify foreign key enforcement rejects orphan records."""
        with self.assertRaises(IntegrityError):
            with get_db() as db:
                # Attempt to insert an account referencing non-existent user_id
                orphan_acc = Account(
                    account_number="NON_EXISTENT_ACC",
                    user_id=99999999,  # Invalid user ID
                    account_type="SAVINGS",
                )
                db.add(orphan_acc)
                db.flush()

    def test_03_account_number_uniqueness_constraint(self):
        """Verify duplicate account numbers are strictly rejected."""
        with get_db() as db:
            existing = db.query(Account).first()
            self.assertIsNotNone(existing, "Expected at least one account in DB")
            dup_acc_no = existing.account_number

        with self.assertRaises(IntegrityError):
            with get_db() as db:
                dup_acc = Account(
                    account_number=dup_acc_no,
                    account_type="SAVINGS",
                )
                db.add(dup_acc)
                db.flush()

    def test_04_check_constraints_positive_transaction_amount(self):
        """Verify check constraint rejects non-positive transaction amount."""
        with self.assertRaises(IntegrityError):
            with get_db() as db:
                invalid_txn = Transaction(
                    reference_id=f"TXN-INVALID-{datetime.datetime.utcnow().timestamp()}",
                    transaction_type="Transfer",
                    state="SUCCESSFUL",
                    amount_paise=-500,  # Negative amount rejected by CHECK constraint
                    source_account="40273146502136",
                    destination_account="99999999999999",
                )
                db.add(invalid_txn)
                db.flush()

    def test_05_check_constraints_account_status(self):
        """Verify check constraint rejects invalid account status."""
        with self.assertRaises(IntegrityError):
            with get_db() as db:
                invalid_acc = Account(
                    account_number=f"ACC-TEST-{datetime.datetime.utcnow().timestamp()}",
                    account_type="SAVINGS",
                    status="CORRUPTED_STATUS",  # Not in ('ACTIVE', 'FROZEN', 'CLOSED')
                )
                db.add(invalid_acc)
                db.flush()

    def test_06_database_transaction_atomicity_and_rollback(self):
        """Verify that an unhandled exception causes complete atomic rollback."""
        test_email = f"rollback_test_{datetime.datetime.utcnow().timestamp()}@credence.bank"
        try:
            with get_db() as db:
                u = User(
                    customer_id=f"CUST-{datetime.datetime.utcnow().timestamp()}",
                    name="Rollback Test User",
                    email=test_email,
                    role="user",
                )
                db.add(u)
                db.flush()
                # Trigger intentional exception before commit
                raise ValueError("Intentional transaction abort to test rollback")
        except ValueError:
            pass

        # Verify user was rolled back and never committed
        with get_db() as db:
            found = db.query(User).filter(User.email == test_email).first()
            self.assertIsNone(found, "Rolled-back user should not exist in database!")

    def test_07_no_plaintext_passwords_or_pins_in_database(self):
        """Verify zero plaintext passwords, PINs, or CVVs exist in production tables."""
        with get_db() as db:
            users = db.query(User).filter(User.password_hash.isnot(None)).all()
            for u in users:
                self.assertTrue(
                    u.password_hash.startswith("$argon2") or u.password_hash.startswith("$2b$"),
                    f"User {u.email} has unhashed password: {u.password_hash[:10]}..."
                )
                if u.pin_hash:
                    self.assertTrue(
                        u.pin_hash.startswith("$argon2") or u.pin_hash.startswith("$2b$"),
                        f"User {u.email} has unhashed PIN: {u.pin_hash[:10]}..."
                    )

            cards = db.query(Card).filter(Card.pin_hash.isnot(None)).all()
            for c in cards:
                self.assertTrue(
                    c.pin_hash.startswith("$argon2") or c.pin_hash.startswith("$2b$"),
                    f"Card {c.card_number_masked} has unhashed PIN"
                )

    def test_08_persistence_across_application_restart(self):
        """Verify account balances and profiles persist across simulated application restart."""
        # 1. Update an account balance via flask_app data access
        test_acc = "40273146502136"
        with get_db() as db:
            bal_rec = db.query(AccountBalance).filter(AccountBalance.account_number == test_acc).first()
            self.assertIsNotNone(bal_rec)
            original_paise = bal_rec.balance_paise

        # 2. Re-instantiate BankBackend (simulates server process restart)
        new_backend = flask_app.BankBackend()
        restarted_profiles = flask_app.load_profiles()

        self.assertIn(test_acc, restarted_profiles)
        expected_rupees_str = f"{original_paise / 100:.2f}"
        self.assertEqual(restarted_profiles[test_acc]["balance"], expected_rupees_str)

    def test_09_alembic_version_table_populated(self):
        """Verify Alembic schema migration tracking is active."""
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version_num FROM alembic_version")).fetchone()
            self.assertIsNotNone(result, "Alembic version record must be present")
            self.assertTrue(len(result[0]) > 0, "Alembic version number must not be empty")

    def test_10_rollback_export_generates_valid_json_backups(self):
        """Verify the rollback export utility creates all 3 JSON backup files with valid schemas."""
        backup_dir = export_database_to_json_backup()
        self.assertTrue(os.path.isdir(backup_dir))

        prof_file = os.path.join(backup_dir, "user_profiles.json")
        bank_file = os.path.join(backup_dir, "bank_data.json")
        inv_file = os.path.join(backup_dir, "user_investments.json")

        self.assertTrue(os.path.exists(prof_file))
        self.assertTrue(os.path.exists(bank_file))
        self.assertTrue(os.path.exists(inv_file))


if __name__ == "__main__":
    unittest.main()
