"""
Credence Core — Phase 2 Database Isolation & Host Security Regression Tests
Proves:
1. Writes from one test do NOT leak into subsequent tests (genuine per-test isolation).
2. Independently committed transactions are completely isolated.
3. Unapproved PostgreSQL test hosts are strictly rejected (even if db name contains 'test').
4. Database URL normalization catches variations in schemes, casing, ports, and trailing slashes.
5. SQLite symlinks pointing to persistent database files are rejected.
6. Fail-closed behavior on connection, port, and environment identity validation.
"""

import os
import sys
import unittest
import datetime
from sqlalchemy import text

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import (
    validate_test_database_safety,
    normalize_database_url,
    get_test_pg_host_allowlist,
    get_db,
    engine,
    SessionLocal
)
from models import User, Account, AccountBalance, Transaction
import security


class TestPerTestIsolationLeakPrevention(unittest.TestCase):
    """
    Two-stage sequential test proving committed data from stage 1 is absent in stage 2.
    """
    LEAK_USER_EMAIL = "isolation_leak_probe_2026@credence.bank"
    LEAK_ACCOUNT_NO = "40999999999991"

    def test_01_create_and_commit_isolated_record(self):
        """Stage 1: Create and explicitly commit records to the test database."""
        with get_db() as db:
            u = User(
                customer_id="CUST-ISO-001",
                name="Isolation Probe User",
                email=self.LEAK_USER_EMAIL,
                role="user",
                password_hash=security.hash_password("ProbePass2026!"),
                status="ACTIVE"
            )
            db.add(u)
            db.flush()

            acc = Account(
                account_number=self.LEAK_ACCOUNT_NO,
                user_id=u.id,
                account_type="CUSTOMER_SAVINGS",
                status="ACTIVE"
            )
            db.add(acc)
            db.flush()

            bal = AccountBalance(
                account_number=self.LEAK_ACCOUNT_NO,
                balance_paise=1500000,
                lien_paise=0
            )
            db.add(bal)
            db.commit()

        # Verify record exists in current test
        with get_db() as db:
            found_user = db.query(User).filter(User.email == self.LEAK_USER_EMAIL).first()
            self.assertIsNotNone(found_user, "Record should be present in creating test")
            found_acc = db.query(Account).filter(Account.account_number == self.LEAK_ACCOUNT_NO).first()
            self.assertIsNotNone(found_acc, "Account should be present in creating test")

    def test_02_verify_previous_committed_record_is_strictly_absent(self):
        """Stage 2: Verify that record committed in test_01 was completely wiped and is absent."""
        with get_db() as db:
            found_user = db.query(User).filter(User.email == self.LEAK_USER_EMAIL).first()
            self.assertIsNone(
                found_user,
                f"Per-test isolation breach! User '{self.LEAK_USER_EMAIL}' committed in previous test leaked into next test!"
            )
            found_acc = db.query(Account).filter(Account.account_number == self.LEAK_ACCOUNT_NO).first()
            self.assertIsNone(
                found_acc,
                f"Per-test isolation breach! Account '{self.LEAK_ACCOUNT_NO}' committed in previous test leaked into next test!"
            )

    def test_03_deterministic_baseline_data_present(self):
        """Verify each test starts with the exact deterministic baseline fixtures."""
        with get_db() as db:
            demo_user = db.query(User).filter(User.customer_id == "CUST-DEMO-001").first()
            self.assertIsNotNone(demo_user, "Baseline demo user must be present")
            demo_acc = db.query(Account).filter(Account.account_number == "40273146502136").first()
            self.assertIsNotNone(demo_acc, "Baseline demo account must be present")
            bal = db.query(AccountBalance).filter(AccountBalance.account_number == "40273146502136").first()
            self.assertIsNotNone(bal, "Baseline balance must be present")
            self.assertEqual(bal.balance_paise, 5000000, "Demo user baseline balance must be ₹50,000 (5000000 paise)")


class TestPostgresHostSecurityAndSafety(unittest.TestCase):
    """
    Validates PostgreSQL host allowlisting, port checks, and URL normalization.
    """
    def test_unapproved_postgres_hosts_rejected_even_with_test_in_name(self):
        """Reject unapproved hosts regardless of whether database name contains 'test'."""
        unapproved = [
            "postgresql://evil-node.attacker.com:5432/credence_core_test",
            "postgresql://10.0.0.55:5432/my_test_db",
            "postgresql://internal-db.corp:5432/test_db",
            "postgresql://qa-cluster-01.cloud:5432/credence_test_isolated",
        ]
        for url in unapproved:
            with self.assertRaises(RuntimeError) as ctx:
                validate_test_database_safety(url)
            self.assertIn("unapproved", str(ctx.exception).lower())

    def test_approved_postgres_hosts_accepted_with_test_name(self):
        """Approved hosts in allowlist with 'test' in DB name pass validation."""
        approved = [
            "postgresql://localhost:5432/credence_core_test",
            "postgresql://127.0.0.1:5432/credence_test_ci",
            "postgresql://postgres-test:5432/test_database",
            "postgresql://test-db:5432/credence_test",
        ]
        for url in approved:
            # Should not raise
            validate_test_database_safety(url)

    def test_invalid_ports_rejected(self):
        """Validate database port bounds."""
        invalid_ports = [
            "postgresql://localhost:0/credence_test",
            "postgresql://localhost:65536/credence_test",
            "postgresql://localhost:99999/credence_test",
        ]
        for url in invalid_ports:
            with self.assertRaises(RuntimeError) as ctx:
                validate_test_database_safety(url)
            self.assertIn("invalid database port", str(ctx.exception).lower())

    def test_url_normalization_catches_equivalent_urls(self):
        """Ensure normalization catches disguised identical URLs."""
        url1 = "postgresql+psycopg2://admin:secret@127.0.0.1:5432/credence_test"
        url2 = "postgresql://other_user:diff_pass@127.0.0.1/credence_test/"
        norm1 = normalize_database_url(url1)
        norm2 = normalize_database_url(url2)
        self.assertEqual(norm1, norm2, f"Normalized URLs should match: {norm1} vs {norm2}")

        with self.assertRaises(RuntimeError) as ctx:
            validate_test_database_safety(url1, raw_database_url=url2)
        self.assertIn("cannot match", str(ctx.exception).lower())

    def test_sqlite_symlink_to_persistent_db_rejected(self):
        """Ensure symlinks pointing to persistent application database are caught and rejected."""
        import tempfile
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        prod_db = os.path.join(base_dir, "credence_core.db")

        temp_link = os.path.join(tempfile.gettempdir(), f"symlink_test_{os.getpid()}.db")
        if os.path.exists(temp_link):
            try:
                os.remove(temp_link)
            except Exception:
                pass

        try:
            os.symlink(prod_db, temp_link)
            # If symlink creation succeeded, validation MUST reject it
            with self.assertRaises(RuntimeError) as ctx:
                validate_test_database_safety(f"sqlite:///{temp_link}")
            self.assertTrue("symlink" in str(ctx.exception).lower() or "persistent" in str(ctx.exception).lower())
        except (OSError, NotImplementedError):
            # Windows without Developer Mode may not allow creating symlinks; verify path rejection directly
            with self.assertRaises(RuntimeError) as ctx:
                validate_test_database_safety(f"sqlite:///{prod_db}")
            self.assertIn("persistent", str(ctx.exception).lower())
        finally:
            if os.path.exists(temp_link):
                try:
                    os.remove(temp_link)
                except Exception:
                    pass

    def test_production_environment_rejects_test_validation(self):
        """Fail-closed: test validation must refuse to execute if FLASK_ENV=production."""
        old_env = os.environ.get("FLASK_ENV")
        try:
            os.environ["FLASK_ENV"] = "production"
            with self.assertRaises(RuntimeError) as ctx:
                validate_test_database_safety("sqlite:///:memory:")
            self.assertIn("cannot run in production", str(ctx.exception).lower())
        finally:
            if old_env is not None:
                os.environ["FLASK_ENV"] = old_env
            else:
                os.environ.pop("FLASK_ENV", None)


if __name__ == "__main__":
    unittest.main()
