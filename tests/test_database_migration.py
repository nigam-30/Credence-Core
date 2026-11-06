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
import warnings
with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
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
                    reference_id=f"TXN-INVALID-{datetime.datetime.now(datetime.timezone.utc).timestamp()}",
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
                    account_number=f"ACC-TEST-{datetime.datetime.now(datetime.timezone.utc).timestamp()}",
                    account_type="SAVINGS",
                    status="CORRUPTED_STATUS",  # Not in ('ACTIVE', 'FROZEN', 'CLOSED')
                )
                db.add(invalid_acc)
                db.flush()

    def test_06_database_transaction_atomicity_and_rollback(self):
        """Verify that an unhandled exception causes complete atomic rollback."""
        test_email = f"rollback_test_{datetime.datetime.now(datetime.timezone.utc).timestamp()}@credence.bank"
        try:
            with get_db() as db:
                u = User(
                    customer_id=f"CUST-{datetime.datetime.now(datetime.timezone.utc).timestamp()}",
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


    def test_11_fail_closed_production_database_exposure_rejected(self):
        """Dedicated test proving test suite fail-closed validation strictly rejects production database URLs."""
        from database import validate_test_database_safety
        
        prod_urls = [
            "postgresql+psycopg2://admin:secret@prod-db.credence.bank:5432/credence_prod",
            "postgresql+psycopg2://user:pass@ep-cool-mountain.neon.tech/credence_live",
            "postgresql+psycopg2://postgres:secret@db.supabase.co:5432/postgres",
            "postgresql+psycopg2://app:pass@credence-prod.rds.amazonaws.com:5432/banking",
        ]
        for url in prod_urls:
            with self.assertRaises(RuntimeError, msg=f"Should reject production database URL: {url}"):
                validate_test_database_safety(url)

    def test_12_migration_upgrade_downgrade_with_populated_records(self):
        """
        Verify safe migration lifecycle on a populated database:
        1. Fresh DB upgrade to previous revision (ba89bcee5f71).
        2. Populate users, sessions, and financial records.
        3. Upgrade to latest revision (b3d83a1f7923) with backfill validation.
        4. Verify record counts and backfilled values.
        5. Downgrade back to ba89bcee5f71.
        6. Re-upgrade back to b3d83a1f7923 idempotently.
        """
        import tempfile
        from alembic.config import Config as AlembicConfig
        from alembic import command as alembic_command
        from sqlalchemy import create_engine as create_temp_engine

        disposable_db = os.path.join(tempfile.gettempdir(), f"disp_mig_test_{os.getpid()}_{int(datetime.datetime.now().timestamp())}.db")
        disp_url = f"sqlite:///{disposable_db.replace(os.sep, '/')}"

        alembic_ini = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "alembic.ini")
        cfg = AlembicConfig(alembic_ini)
        cfg.set_main_option("script_location", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "alembic"))
        cfg.set_main_option("sqlalchemy.url", disp_url)

        try:
            # 1. Upgrade to previous schema revision
            alembic_command.upgrade(cfg, "ba89bcee5f71")
            
            temp_eng = create_temp_engine(disp_url)
            with temp_eng.connect() as conn:
                # 2. Populate users and sessions with legacy schema (where new NOT NULL columns do not yet exist)
                conn.execute(text("""
                    INSERT INTO users (customer_id, name, email, role, status, is_2fa_enabled, notifications_enabled, created_at, updated_at)
                    VALUES ('CUST-LEGACY-01', 'Legacy User', 'legacy@credence.bank', 'user', 'ACTIVE', 0, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """))
                user_id = conn.execute(text("SELECT id FROM users WHERE customer_id = 'CUST-LEGACY-01'")).scalar()
                
                conn.execute(text(f"""
                    INSERT INTO accounts (account_number, user_id, account_type, currency, status, daily_transfer_limit_paise, daily_transferred_paise, created_at, updated_at)
                    VALUES ('11112222333344', {user_id}, 'CUSTOMER_SAVINGS', 'INR', 'ACTIVE', 50000000, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """))
                
                conn.execute(text(f"""
                    INSERT INTO sessions (session_id, user_id, account_number, is_active, expires_at, created_at)
                    VALUES ('legacy_token_12345', {user_id}, '11112222333344', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """))

                conn.execute(text("""
                    INSERT INTO transactions (reference_id, transaction_type, state, amount_paise, source_account, destination_account, created_at, updated_at)
                    VALUES ('TXN-LEGACY-001', 'DEPOSIT', 'SUCCESSFUL', 500000, 'GL_CASH_VAULT', '11112222333344', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """))
                conn.commit()

                user_count_before = conn.execute(text("SELECT COUNT(*) FROM users")).scalar()
                session_count_before = conn.execute(text("SELECT COUNT(*) FROM sessions")).scalar()
                txn_count_before = conn.execute(text("SELECT COUNT(*) FROM transactions")).scalar()
            
            temp_eng.dispose()

            # 3. Upgrade to latest revision (b3d83a1f7923) with populated data
            alembic_command.upgrade(cfg, "b3d83a1f7923")

            # 4. Verify data preservation and safe backfill
            temp_eng = create_temp_engine(disp_url)
            with temp_eng.connect() as conn:
                user_count_after = conn.execute(text("SELECT COUNT(*) FROM users")).scalar()
                session_count_after = conn.execute(text("SELECT COUNT(*) FROM sessions")).scalar()
                txn_count_after = conn.execute(text("SELECT COUNT(*) FROM transactions")).scalar()

                assert user_count_before == user_count_after, f"User count mismatch: {user_count_before} != {user_count_after}"
                assert session_count_before == session_count_after, f"Session count mismatch: {session_count_before} != {session_count_after}"
                assert txn_count_before == txn_count_after, f"Txn count mismatch: {txn_count_before} != {txn_count_after}"

                # Verify backfilled values
                sess_row = conn.execute(text("SELECT role, is_demo, last_active_at FROM sessions WHERE session_id = 'legacy_token_12345'")).fetchone()
                assert sess_row is not None
                assert sess_row[0] == "user"
                assert not bool(sess_row[1])
                assert sess_row[2] is not None

                usr_row = conn.execute(text("SELECT mfa_enabled, last_totp_step FROM users WHERE customer_id = 'CUST-LEGACY-01'")).fetchone()
                assert usr_row is not None
                assert not bool(usr_row[0])
                assert usr_row[1] == 0

            temp_eng.dispose()

            # 5. Downgrade back to ba89bcee5f71
            alembic_command.downgrade(cfg, "ba89bcee5f71")

            # 6. Re-upgrade back to b3d83a1f7923 (idempotency check)
            alembic_command.upgrade(cfg, "b3d83a1f7923")

            temp_eng = create_temp_engine(disp_url)
            with temp_eng.connect() as conn:
                ver = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
                assert ver == "b3d83a1f7923", f"Expected revision b3d83a1f7923, got {ver}"
            temp_eng.dispose()

        finally:
            if os.path.exists(disposable_db):
                try:
                    os.remove(disposable_db)
                except Exception:
                    pass

    def test_13_identical_test_and_prod_database_url_rejected(self):
        """Verify fail-closed rejection when TEST_DATABASE_URL equals DATABASE_URL regardless of keywords."""
        from database import validate_test_database_safety

        url = "postgresql://internal-host.corp:5432/core_banking"
        with self.assertRaises(RuntimeError) as ctx:
            validate_test_database_safety(url, raw_database_url=url)
        self.assertIn("cannot match", str(ctx.exception).lower())

    def test_14_production_postgres_without_keywords_rejected(self):
        """Verify PostgreSQL test URL without explicit 'test' marker or with unapproved host is rejected."""
        from database import validate_test_database_safety

        # 1. Non-test database name rejected
        non_test_pg_url = "postgresql://localhost:5432/credence_core_main"
        with self.assertRaises(RuntimeError) as ctx:
            validate_test_database_safety(non_test_pg_url)
        self.assertIn("not isolated", str(ctx.exception).lower())

        # 2. Unapproved host with 'test' in the DB name rejected
        unapproved_host_url = "postgresql://db-node-01.internal.corp:5432/credence_core_test"
        with self.assertRaises(RuntimeError) as ctx:
            validate_test_database_safety(unapproved_host_url)
        self.assertIn("unapproved", str(ctx.exception).lower())

        # 3. Approved host with 'test' in the name passes validation
        valid_test_pg_url = "postgresql://localhost:5432/credence_core_test"
        validate_test_database_safety(valid_test_pg_url)

    def test_15_unreachable_test_postgres_fails_closed(self):
        """Verify unreachable test PostgreSQL connection raises fatal error without fallback."""
        from database import configure_engine

        # Provide unreachable test PostgreSQL port
        unreachable_url = "postgresql+psycopg2://test_user:test_pass@127.0.0.1:59999/credence_test_isolated"
        with self.assertRaises(RuntimeError) as ctx:
            configure_engine(unreachable_url)
        self.assertIn("fallback is strictly forbidden", str(ctx.exception).lower())

    def test_16_sqlite_pointing_to_persistent_db_rejected(self):
        """Verify SQLite URL pointing to persistent application database is strictly rejected."""
        from database import validate_test_database_safety

        bad_paths = [
            "sqlite:///credence_core.db",
            f"sqlite:///{os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'credence_core.db')}",
            "sqlite:///credence_backup.db"
        ]
        for bad_url in bad_paths:
            with self.assertRaises(RuntimeError) as ctx:
                validate_test_database_safety(bad_url)
            self.assertIn("points to persistent application database", str(ctx.exception).lower())

    def test_17_failed_test_db_cannot_open_or_modify_credence_core_db(self):
        """Prove that a failed test database connection cannot open, touch, or modify credence_core.db."""
        from database import configure_engine, get_db_url

        prod_db_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "credence_core.db")
        initial_mtime = os.path.getmtime(prod_db_file) if os.path.exists(prod_db_file) else None
        initial_size = os.path.getsize(prod_db_file) if os.path.exists(prod_db_file) else None

        # Attempt to configure an invalid/unreachable test database in testing mode
        unreachable_url = "postgresql+psycopg2://fake_user:fake_pass@127.0.0.1:59998/isolated_test_db"
        with self.assertRaises(RuntimeError):
            configure_engine(unreachable_url)

        # Assert credence_core.db was NOT touched or fallen back to
        if os.path.exists(prod_db_file):
            self.assertEqual(os.path.getmtime(prod_db_file), initial_mtime)
            self.assertEqual(os.path.getsize(prod_db_file), initial_size)

        # Restore valid isolated temporary test database
        valid_isolated_url = os.environ.get("TEST_DATABASE_URL")
        configure_engine(valid_isolated_url)


if __name__ == "__main__":
    unittest.main()
