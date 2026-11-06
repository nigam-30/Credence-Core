"""
Credence Core — Test Suite Configuration & Migration Test Fixture (pytest)
Ensures zero-dependency automated testing from fresh clones and extracted release archives.
Executes genuine Alembic migrations ('alembic upgrade head') against an isolated test database,
verifies relational schema/indexes/foreign-keys, seeds synthetic test fixtures, and enforces test isolation.
"""

import os
import sys
import pytest
from sqlalchemy import inspect, text
from alembic.config import Config as AlembicConfig
from alembic import command as alembic_command

# Ensure repository root is on PYTHONPATH
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# 1. Enforce testing environment BEFORE any application module or model is imported
os.environ["FLASK_ENV"] = "testing"

# 2. Configure isolated temporary test database URL if not explicitly set
import tempfile
if "TEST_DATABASE_URL" not in os.environ or not os.environ["TEST_DATABASE_URL"].strip():
    _temp_db_path = os.path.join(tempfile.gettempdir(), f"credence_test_isolated_{os.getpid()}.db")
    os.environ["TEST_DATABASE_URL"] = f"sqlite:///{_temp_db_path.replace(os.sep, '/')}"

from database import validate_test_database_safety, mask_database_url
validate_test_database_safety(os.environ["TEST_DATABASE_URL"])

from backend.app.core.database import get_db, engine, get_db_url, SessionLocal
from backend.app.services.ledger import ledger_service, GL_CASH_VAULT
from models import (
    Base, User, Account, AccountBalance, Card, UPIProfile,
    Investment, TransactionLimit
)
import security


_golden_snapshot_conn = None


def seed_synthetic_fixtures():
    """Seed primary test fixture user, accounts, cards, UPI, limits, and balanced ledger deposit."""
    # 4. Seed primary test fixture user and account (40273146502136) if not present
    with get_db() as db:
        acc = db.query(Account).filter(Account.account_number == "40273146502136").first()
        if not acc:
            user = User(
                customer_id="CUST-DEMO-001",
                name="Demo User",
                email="demo@credence.bank",
                role="user",
                password_hash=security.hash_password("LegitPassword2026!"),
                pin_hash=security.hash_pin("1234"),
                pan="ABCDE1234F",
                employment_type="Salaried",
                status="ACTIVE"
            )
            db.add(user)
            db.flush()

            acc = Account(
                account_number="40273146502136",
                user_id=user.id,
                account_type="CUSTOMER_SAVINGS",
                status="ACTIVE"
            )
            db.add(acc)
            db.flush()

            card = Card(
                card_number_masked="************1234",
                pin_hash=security.hash_pin("1234"),
                card_network="Visa Platinum",
                expiry_month_year="12/30",
                account_number="40273146502136",
                status="ACTIVE"
            )
            db.add(card)

            upi = UPIProfile(
                account_number="40273146502136",
                upi_id="40273146502136@credence",
                upi_pin_hash=security.hash_pin("123456"),
                status="ACTIVE"
            )
            db.add(upi)

            inv = Investment(
                account_number="40273146502136",
                gold_grams=5.0,
                gold_total_invested_paise=3810250,
                gold_avg_buy_price_paise=762050
            )
            db.add(inv)

            lim = TransactionLimit(
                account_number="40273146502136",
                daily_limit_paise=50000000,
                per_txn_limit_paise=10000000,
                approval_threshold_paise=5000000
            )
            db.add(lim)
            db.commit()

            # Execute legitimate ledger deposit so double-entry ledger is genuinely balanced
            dep_res = ledger_service.execute(
                transaction_type="DEPOSIT",
                amount_rupees=50000.0,
                source_account=GL_CASH_VAULT,
                destination_account="40273146502136",
                description="Initial synthetic fixture seed deposit",
                actor="SYSTEM",
                ip="127.0.0.1"
            )
            if not dep_res or not dep_res.get("reference_id"):
                raise RuntimeError("Failed to execute initial balanced seed deposit for account 40273146502136!")

        # 5. Seed system admin/clearing account (99999999999999) if not present
        admin_acc = db.query(Account).filter(Account.account_number == "99999999999999").first()
        if not admin_acc:
            admin_user = User(
                customer_id="SYS-ADMIN-01",
                name="Admin User",
                email="admin@credence.bank",
                role="admin",
                password_hash=security.hash_password("AdminPassword2026!"),
                pin_hash=security.hash_pin("9999"),
                pan="ZZZZZ9999Z",
                status="ACTIVE"
            )
            db.add(admin_user)
            db.flush()

            admin_acc = Account(
                account_number="99999999999999",
                user_id=admin_user.id,
                account_type="SYSTEM_SETTLEMENT",
                status="ACTIVE"
            )
            db.add(admin_acc)
            db.flush()

            bal_admin = AccountBalance(
                account_number="99999999999999",
                balance_paise=0,
                lien_paise=0
            )
            db.add(bal_admin)
            db.commit()

    # 6. Verify overall double-entry ledger equilibrium
    recon = ledger_service.reconcile()
    if recon.get("status") != "HEALTHY":
        raise RuntimeError(f"Ledger reconciliation invariant failed after seeding: {recon}")


def run_isolated_migrations_and_seed():
    """
    Execute genuine Alembic migrations ('alembic upgrade head'), verify schema integrity,
    and seed synthetic test fixtures with zero silent exception suppression.
    """
    global _golden_snapshot_conn
    # 1. Execute genuine Alembic migrations
    alembic_ini_path = os.path.join(BASE_DIR, "alembic.ini")
    alembic_cfg = AlembicConfig(alembic_ini_path)
    alembic_cfg.set_main_option("script_location", os.path.join(BASE_DIR, "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", get_db_url())
    alembic_command.upgrade(alembic_cfg, "head")

    # 2. Verify current Alembic revision in the database
    with engine.connect() as conn:
        rev = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        if not rev:
            raise RuntimeError("Alembic migration failed: alembic_version table is empty!")
        if rev != "b3d83a1f7923":
            raise RuntimeError(f"Alembic migration revision mismatch: expected 'b3d83a1f7923', found '{rev}'")

    # 3. Verify actual schema tables and foreign keys
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    required_tables = {
        "users", "accounts", "account_balances", "ledger_entries", "transactions",
        "cards", "upi_profiles", "fixed_deposits", "loans", "investments", "sips",
        "ipo_applications", "recurring_deposits", "beneficiaries", "sessions",
        "audit_logs", "audit_trail", "disputes", "fraud_alerts", "support_tickets",
        "transaction_limits", "alembic_version"
    }
    missing_tables = required_tables - tables
    if missing_tables:
        raise RuntimeError(f"Alembic migration failed to generate required tables: {missing_tables}")

    fks = inspector.get_foreign_keys("accounts")
    if not fks:
        raise RuntimeError("Foreign key verification failed: no foreign keys found on 'accounts' table!")

    # Seed baseline fixtures
    seed_synthetic_fixtures()

    # Capture golden baseline snapshot for fast per-test restoration (SQLite)
    db_url = os.environ.get("TEST_DATABASE_URL", "")
    if db_url.startswith("sqlite:///") and "credence_test_isolated_" in db_url:
        import sqlite3
        db_path = db_url.replace("sqlite:///", "").split("?")[0]
        SessionLocal.remove()
        engine.dispose()
        if _golden_snapshot_conn is None:
            _golden_snapshot_conn = sqlite3.connect(":memory:")
        disk_conn = sqlite3.connect(db_path)
        disk_conn.backup(_golden_snapshot_conn)
        disk_conn.close()


def restore_test_database_isolation():
    """
    Enforce deterministic per-test database isolation.
    Wipes any uncommitted or committed test writes and restores the exact baseline state.
    Fails closed if restoration encounters any error.
    """
    try:
        SessionLocal.remove()
        engine.dispose()
        db_url = os.environ.get("TEST_DATABASE_URL", "")
        if db_url.startswith("sqlite:///") and _golden_snapshot_conn is not None:
            import sqlite3
            db_path = db_url.replace("sqlite:///", "").split("?")[0]
            dest_conn = sqlite3.connect(db_path)
            _golden_snapshot_conn.backup(dest_conn)
            dest_conn.close()
        elif "postgres" in db_url:
            with engine.connect() as conn:
                conn.execute(text(
                    "TRUNCATE TABLE users, accounts, account_balances, ledger_entries, transactions, "
                    "cards, upi_profiles, fixed_deposits, loans, investments, sips, "
                    "ipo_applications, recurring_deposits, beneficiaries, sessions, "
                    "audit_logs, audit_trail, disputes, fraud_alerts, support_tickets, "
                    "transaction_limits CASCADE"
                ))
                conn.commit()
            seed_synthetic_fixtures()
        SessionLocal.remove()
    except Exception as e:
        raise RuntimeError(f"FATAL: Per-test database isolation cleanup failed: {e}") from e


def pytest_sessionstart(session):
    """Pytest hook: Execute before any test runs."""
    run_isolated_migrations_and_seed()


@pytest.fixture(autouse=True)
def per_test_database_isolation(request):
    """
    Autouse fixture: Per-test database transaction & session isolation.
    Ensures every test starts with deterministic baseline data and committed changes are completely wiped.
    """
    if "TestDOMAgentJourneys" in getattr(request.node, "nodeid", ""):
        yield
        return
    restore_test_database_isolation()
    yield
    restore_test_database_isolation()


@pytest.fixture(autouse=True)
def clean_security_caches():
    """Autouse fixture: Reset in-memory rate limits, IP histories, and lockouts between tests."""
    security.FAILED_ATTEMPTS_STORE.clear()
    security.IP_REQUEST_HISTORY.clear()
    yield
    security.FAILED_ATTEMPTS_STORE.clear()
    security.IP_REQUEST_HISTORY.clear()


def pytest_sessionfinish(session, exitstatus):
    """Pytest hook: Clean up temporary isolated SQLite database file after all tests finish."""
    global _golden_snapshot_conn
    if _golden_snapshot_conn is not None:
        try:
            _golden_snapshot_conn.close()
        except Exception:
            pass
        _golden_snapshot_conn = None

    db_url = os.environ.get("TEST_DATABASE_URL", "")
    if db_url.startswith("sqlite:///") and "credence_test_isolated_" in db_url:
        db_path = db_url.replace("sqlite:///", "").split("?")[0]
        import time
        import gc
        cleaned = False
        for _ in range(5):
            try:
                SessionLocal.remove()
                engine.dispose()
                gc.collect()
                if os.path.exists(db_path):
                    os.remove(db_path)
                cleaned = True
                break
            except Exception:
                time.sleep(0.1)
        if not cleaned and os.path.exists(db_path):
            try:
                os.remove(db_path)
            except Exception as e:
                sys.stderr.write(f"\n[CLEANUP NOTICE] Could not remove temporary test DB '{db_path}': {e}\n")
