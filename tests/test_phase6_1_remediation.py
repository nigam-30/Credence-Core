"""
Credence Core — Phase 6.1: Critical Security & Architecture Remediation Integration Test Suite
Validates that all audited vulnerabilities have been remediated in production code paths.
Per project instructions:
- Does NOT use session_transaction() to establish authentication in authentication tests.
- Uses real HTTP calls with cookie jar and CSRF token propagation.
"""

import unittest
import json
import time
import uuid
import hashlib
import concurrent.futures
from decimal import Decimal
from flask import Flask

from backend.app import create_app
from backend.app.core.config import Config
from backend.app.core.database import get_db, SessionLocal
from backend.app.core.mfa import generate_mfa_secret, verify_totp_code, generate_totp_code, decrypt_mfa_secret
from models import User, Account, AccountBalance, SessionRecord, Transaction
import security
import ledger


class Phase61RemediationTestSuite(unittest.TestCase):
    """
    Independent verification test suite for Phase 6.1 remediation.
    Exercises genuine HTTP endpoints, server-side session models, and double-entry ledger.
    """

    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        cls.app.config["WTF_CSRF_ENABLED"] = True
        cls.client = cls.app.test_client()

    def setUp(self):
        security.FAILED_ATTEMPTS_STORE.clear()
        security.IP_REQUEST_HISTORY.clear()
        # Ensure test account has known password and clean state
        with get_db() as db:
            acc = db.query(Account).filter(Account.account_number == "40273146502136").first()
            if acc and acc.user:
                acc.user.password_hash = security.hash_password("LegitPassword2026!")
                acc.user.mfa_enabled = False
                acc.user.mfa_secret = None
                acc.user.mfa_recovery_codes = None
                acc.user.status = "ACTIVE"
                db.commit()

    # ══════════════════════════════════════════════════════════════
    # P0.1: DEMO LOGIN VULNERABILITY REMEDIATION
    # ══════════════════════════════════════════════════════════════
    def test_arbitrary_demo_login_blocked(self):
        """1. Arbitrary account demo login must be strictly rejected with HTTP 403."""
        arbitrary_accounts = ["99999999999999", "12345678901234", "00000000000000"]
        for arb in arbitrary_accounts:
            res = self.client.post("/api/demo_login", json={"account_number": arb})
            self.assertEqual(res.status_code, 403, f"Arbitrary demo login for {arb} was not rejected!")
            data = res.get_json()
            self.assertFalse(data.get("success", True))
            self.assertIn("arbitrary", data.get("message", "").lower())

    def test_configured_demo_login_read_only(self):
        """2. Demo login permits explicitly configured accounts but enforces strict read-only role."""
        res = self.client.post("/api/demo_login", json={"account_number": "40273146502136"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["user"]["role"], "demo")
        csrf = data["csrf_token"]

        # Attempt mutating action as demo user (Must be blocked with HTTP 403)
        res_mutate = self.client.post(
            "/api/transfer",
            json={"to_acc": "99999999999999", "amount": "100", "method": "IMPS"},
            headers={"X-CSRF-Token": csrf}
        )
        self.assertEqual(res_mutate.status_code, 403)
        self.assertIn("read-only", res_mutate.get_json()["message"].lower())

    # ══════════════════════════════════════════════════════════════
    # P0.2: SERVER-SIDE POSTGRESQL SESSION STORAGE & ROTATION
    # ══════════════════════════════════════════════════════════════
    def test_password_auth_and_session_rotation(self):
        """3. Password login rotates session and writes active record to PostgreSQL."""
        res1 = self.client.post("/api/login", json={"account": "40273146502136", "password": "LegitPassword2026!"})
        self.assertEqual(res1.status_code, 200)
        tok1 = res1.get_json()["session_token"]
        csrf1 = res1.get_json()["csrf_token"]

        # Verify active session record in database
        with get_db() as db:
            s_rec = db.query(SessionRecord).filter(
                SessionRecord.account_number == "40273146502136",
                SessionRecord.is_active == True
            ).first()
            self.assertIsNotNone(s_rec)
            self.assertTrue(s_rec.is_active)

        # Login second time (Session rotation check)
        res2 = self.client.post("/api/login", json={"account": "40273146502136", "password": "LegitPassword2026!"})
        self.assertEqual(res2.status_code, 200)
        tok2 = res2.get_json()["session_token"]

        # Tokens must be distinct (Rotated upon each authenticated login)
        self.assertNotEqual(tok1, tok2, "Session token was not rotated upon subsequent login!")

    def test_stolen_session_replay_blocked_after_logout(self):
        """4. Logout must perform genuine server-side revocation; replaying token must return 401."""
        res_login = self.client.post("/api/login", json={"account": "40273146502136", "password": "LegitPassword2026!"})
        self.assertEqual(res_login.status_code, 200)
        data = res_login.get_json()
        token = data["session_token"]
        csrf = data["csrf_token"]

        # Access protected endpoint while logged in
        res_acc1 = self.client.get("/api/account/40273146502136")
        self.assertEqual(res_acc1.status_code, 200)

        # Server-side logout with CSRF
        res_logout = self.client.post("/api/logout", headers={"X-CSRF-Token": csrf})
        self.assertEqual(res_logout.status_code, 200)

        # Verify database session record is deactivated
        with get_db() as db:
            s_rec = db.query(SessionRecord).filter(SessionRecord.session_id == token).first()
            if s_rec:
                self.assertFalse(s_rec.is_active, "Session record in database was not marked inactive on logout!")

        # Clear client cookies to isolate Authorization header replay
        fresh_client = self.app.test_client()
        res_replay = fresh_client.get(
            "/api/account/40273146502136",
            headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(res_replay.status_code, 401, "Stolen session replay succeeded after logout!")

    def test_session_idle_timeout_expiration(self):
        """5. Expired session records in database must be rejected with HTTP 401."""
        res_login = self.client.post("/api/login", json={"account": "40273146502136", "password": "LegitPassword2026!"})
        self.assertEqual(res_login.status_code, 200)
        token = res_login.get_json()["session_token"]

        # Artificially expire the session in the database
        with get_db() as db:
            import datetime
            token_h = hashlib.sha256(token.encode("utf-8")).hexdigest()
            db.query(SessionRecord).filter(
                (SessionRecord.session_token_hash == token_h) | (SessionRecord.session_id == token)
            ).update({"expires_at": datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) - datetime.timedelta(minutes=5)})
            db.commit()

        # Request with fresh client without cookies to test expired token in header
        fresh_client = self.app.test_client()
        res_expired = fresh_client.get(
            "/api/account/40273146502136",
            headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(res_expired.status_code, 401)
        self.assertIn("expired", res_expired.get_json()["message"].lower())

    # ══════════════════════════════════════════════════════════════
    # P0.3: CSRF SYNCHRONIZER TOKEN VALIDATION
    # ══════════════════════════════════════════════════════════════
    def test_csrf_validation_on_all_mutations(self):
        """6. State-changing mutating operations must require valid CSRF synchronizer token."""
        res_login = self.client.post("/api/login", json={"account": "40273146502136", "password": "LegitPassword2026!"})
        self.assertEqual(res_login.status_code, 200)
        csrf = res_login.get_json()["csrf_token"]

        # Case A: Missing CSRF header entirely -> 403 Forbidden
        res_missing = self.client.post(
            "/api/deposit",
            json={"amount": "100"}
        )
        self.assertEqual(res_missing.status_code, 403)
        self.assertIn("csrf", res_missing.get_json()["message"].lower())

        # Case B: Forged/Tampered CSRF header -> 403 Forbidden
        res_forged = self.client.post(
            "/api/deposit",
            json={"amount": "100"},
            headers={"X-CSRF-Token": "forged_malicious_attacker_token"}
        )
        self.assertEqual(res_forged.status_code, 403)

        # Case C: Valid CSRF header -> 200 OK
        res_valid = self.client.post(
            "/api/deposit",
            json={"amount": "100"},
            headers={"X-CSRF-Token": csrf}
        )
        self.assertEqual(res_valid.status_code, 200)
        self.assertTrue(res_valid.get_json()["success"])

    # ══════════════════════════════════════════════════════════════
    # P0.4: SINGLE SOURCE OF FINANCIAL TRUTH & IDEMPOTENCY
    # ══════════════════════════════════════════════════════════════
    def test_idempotency_payload_fingerprint_conflict(self):
        """7. Replaying same idempotency key with conflicting payload must return HTTP 409 Conflict."""
        res_login = self.client.post("/api/login", json={"account": "40273146502136", "password": "LegitPassword2026!"})
        csrf = res_login.get_json()["csrf_token"]
        key = f"IDEM-TEST-{uuid.uuid4().hex[:8]}"

        # First execution: Deposit ₹100
        res1 = self.client.post(
            "/api/deposit",
            json={"amount": "100", "idempotency_key": key},
            headers={"X-CSRF-Token": csrf}
        )
        self.assertEqual(res1.status_code, 200)

        # Second execution with SAME key but DIFFERENT payload (Amount = 200)
        res_conflict = self.client.post(
            "/api/deposit",
            json={"amount": "200", "idempotency_key": key},
            headers={"X-CSRF-Token": csrf}
        )
        # Financial integrity engine must reject payload tampering on idempotency key
        self.assertEqual(res_conflict.status_code, 409)
        self.assertIn("conflict", res_conflict.get_json()["message"].lower())

    def test_atomic_transaction_rollback_on_failure(self):
        """8. Partial transaction failure must roll back completely without partial state persistence."""
        engine_inst = ledger.FinancialIntegrityEngine()
        acc_src = f"ACC_RB_SRC_{uuid.uuid4().hex[:6]}"
        acc_dst = f"ACC_RB_DST_{uuid.uuid4().hex[:6]}"
        engine_inst.ensure_account(acc_src, 0)
        engine_inst.ensure_account(acc_dst, 0)

        # Seed with legitimate deposit from GL_CASH_VAULT so double-entry books balance
        engine_inst.execute_transaction(
            transaction_type="DEPOSIT",
            amount_rupees="500.00",
            source_account=ledger.GL_CASH_VAULT,
            destination_account=acc_src,
            description="Initial seed for rollback test"
        )

        initial_src = engine_inst.get_account_balance(acc_src)["balance_paise"]
        self.assertEqual(initial_src, 50000)

        # Attempt transfer exceeding balance
        with self.assertRaises(ledger.InsufficientFundsError):
            engine_inst.execute_transaction(
                transaction_type="TRANSFER_IMPS",
                amount_rupees="1000.00",
                source_account=acc_src,
                destination_account=acc_dst,
                description="Should abort completely"
            )

        # Balances must be untouched
        final_src = engine_inst.get_account_balance(acc_src)["balance_paise"]
        final_dst = engine_inst.get_account_balance(acc_dst)["balance_paise"]
        self.assertEqual(initial_src, final_src)
        self.assertEqual(final_dst, 0)

    def test_canonical_ledger_zero_discrepancy(self):
        """9. Double-entry ledger mathematical reconciliation must verify debits == credits."""
        engine_inst = ledger.FinancialIntegrityEngine()
        recon = engine_inst.reconcile_ledger()
        self.assertEqual(recon["status"], "HEALTHY")
        self.assertEqual(recon["discrepancy_paise"], 0)
        self.assertEqual(recon["total_system_debits_paise"], recon["total_system_credits_paise"])

    # ══════════════════════════════════════════════════════════════
    # P1: ACTUAL MFA (TOTP + RECOVERY CODES + CHALLENGE)
    # ══════════════════════════════════════════════════════════════
    def test_mfa_full_lifecycle_and_challenge(self):
        """10. Full MFA enrollment, TOTP verification, challenge during login, and disable flow."""
        # 1. Login with password
        res_login = self.client.post("/api/login", json={"account": "40273146502136", "password": "LegitPassword2026!"})
        self.assertEqual(res_login.status_code, 200)
        csrf = res_login.get_json()["csrf_token"]

        # 2. Check MFA status (initially disabled)
        res_status = self.client.get("/api/mfa/status")
        self.assertEqual(res_status.status_code, 200)
        self.assertFalse(res_status.get_json()["mfa_enabled"])

        # 3. Setup MFA
        res_setup = self.client.post("/api/mfa/setup", headers={"X-CSRF-Token": csrf})
        self.assertEqual(res_setup.status_code, 200)
        setup_data = res_setup.get_json()
        self.assertIn("otpauth_uri", setup_data)
        self.assertIn("recovery_codes", setup_data)
        self.assertEqual(len(setup_data["recovery_codes"]), 8)
        plain_secret = setup_data["secret"]

        valid_code = generate_totp_code(plain_secret)

        # 4. Confirm MFA enrollment
        res_confirm = self.client.post(
            "/api/mfa/confirm",
            json={"totp_code": valid_code},
            headers={"X-CSRF-Token": csrf}
        )
        self.assertEqual(res_confirm.status_code, 200)
        self.assertTrue(res_confirm.get_json()["success"])

        # Verify MFA is now active and secret encrypted in database
        with get_db() as db:
            acc = db.query(Account).filter(Account.account_number == "40273146502136").first()
            user = acc.user
            self.assertTrue(user.mfa_enabled)
            self.assertIsNotNone(user.mfa_secret)

        # Logout
        self.client.post("/api/logout", headers={"X-CSRF-Token": csrf})

        # 5. Subsequent Login must trigger MFA Challenge
        res_chal = self.client.post("/api/login", json={"account": "40273146502136", "password": "LegitPassword2026!"})
        self.assertEqual(res_chal.status_code, 200)
        chal_data = res_chal.get_json()
        self.assertTrue(chal_data.get("mfa_required", False), "MFA Challenge was not triggered for enrolled user!")
        mfa_ticket = chal_data["mfa_ticket"]

        # 6. Verify MFA challenge with code
        fresh_code = generate_totp_code(plain_secret)
        res_mfa_verify = self.client.post(
            "/api/mfa/verify",
            json={"mfa_ticket": mfa_ticket, "totp_code": fresh_code}
        )
        self.assertEqual(res_mfa_verify.status_code, 200)
        mfa_data = res_mfa_verify.get_json()
        self.assertTrue(mfa_data["success"])
        new_csrf = mfa_data["csrf_token"]

        # 7. Disable MFA with password and current TOTP code
        disable_code = generate_totp_code(plain_secret)
        res_disable = self.client.post(
            "/api/mfa/disable",
            json={"password": "LegitPassword2026!", "totp_code": disable_code},
            headers={"X-CSRF-Token": new_csrf}
        )
        self.assertEqual(res_disable.status_code, 200)
        self.assertTrue(res_disable.get_json()["success"])

    # ══════════════════════════════════════════════════════════════
    # P1: CONFIGURATION & SECRET HARDENING VALIDATION
    # ══════════════════════════════════════════════════════════════
    def test_production_fails_on_weak_secret_key(self):
        """11. Production configuration must fail fast on missing or weak SECRET_KEY."""
        from backend.app.core.config import ProductionConfig
        orig_key = ProductionConfig.SECRET_KEY
        try:
            ProductionConfig.SECRET_KEY = "short"
            with self.assertRaises(RuntimeError) as ctx:
                ProductionConfig.validate_secrets()
            self.assertIn("32 characters", str(ctx.exception))
        finally:
            ProductionConfig.SECRET_KEY = orig_key

    def test_production_fails_on_known_insecure_secrets(self):
        """12. Production configuration must fail fast on known leaked default secrets."""
        from backend.app.core.config import ProductionConfig
        orig_key = ProductionConfig.SECRET_KEY
        try:
            ProductionConfig.SECRET_KEY = "CREDENCE_CORE_ENTERPRISE_SECRET_KEY_PROD_2026"
            with self.assertRaises(RuntimeError) as ctx:
                ProductionConfig.validate_secrets()
            self.assertIn("insecure default", str(ctx.exception).lower())
        finally:
            ProductionConfig.SECRET_KEY = orig_key


if __name__ == "__main__":
    unittest.main()
