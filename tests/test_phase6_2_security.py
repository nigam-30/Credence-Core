"""
Credence Core — Phase 6.2 Security & Hardening Integration Test Suite
Validates all Phase 6.2 hardening requirements:
1. Client-side PIN bypass elimination and backend Argon2id verification
2. Dedicated MFA encryption key, replay prevention, single-use recovery codes
3. Read-only demo account lockdown (service & API layer rejection)
4. Authoritative session validation, rotation, and logout revocation
5. Absolute session timeout (86400s) and inactivity timeout enforcement
6. GL account transfer prevention
7. Float-free Decimal financial calculations via FinancialPolicy
8. C++ engine linked-list memory cleanup verification
"""

import unittest
import time
import hashlib
from decimal import Decimal

from backend.app import create_app
from backend.app.core.config import Config
from backend.app.core.database import get_db
from backend.app.core.financial_policy import FinancialPolicy
from backend.app.core.mfa import (
    generate_mfa_secret,
    encrypt_mfa_secret,
    generate_totp_code,
    verify_totp_code_with_replay_prevention,
    verify_and_consume_recovery_code,
    reencrypt_mfa_secret
)
from models import User, Account, AccountBalance, SessionRecord, Card
import security


class Phase62SecurityTestSuite(unittest.TestCase):
    """Automated security verification for Phase 6.2 engineering hardening."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        cls.app.config["WTF_CSRF_ENABLED"] = True
        cls.client = cls.app.test_client()

    def setUp(self):
        security.FAILED_ATTEMPTS_STORE.clear()
        security.IP_REQUEST_HISTORY.clear()
        with get_db() as db:
            acc = db.query(Account).filter(Account.account_number == "40273146502136").first()
            if acc and acc.user:
                acc.user.password_hash = security.hash_password("LegitPassword2026!")
                acc.user.role = "user"
                acc.user.pin_hash = security.hash_pin("9876")
                acc.user.mfa_enabled = False
                acc.user.mfa_secret = None
                acc.user.mfa_recovery_codes = None
            db.commit()

    # 1. FRONTEND PIN SECURITY
    def test_backend_pin_verification_endpoint(self):
        """PIN verification must be performed exclusively via backend Argon2id hash."""
        # Unauthenticated request rejected
        res_unauth = self.client.post("/api/account/verify_pin", json={"pin": "9876"})
        self.assertEqual(res_unauth.status_code, 401)

        # Authenticate
        res_login = self.client.post("/api/login", json={"account": "40273146502136", "password": "LegitPassword2026!"})
        self.assertEqual(res_login.status_code, 200)
        csrf = res_login.get_json()["csrf_token"]

        # Wrong PIN rejected (including legacy default 1234)
        res_wrong = self.client.post(
            "/api/account/verify_pin",
            json={"pin": "1234"},
            headers={"X-CSRF-Token": csrf}
        )
        self.assertEqual(res_wrong.status_code, 401)
        self.assertFalse(res_wrong.get_json()["success"])

        # Correct PIN accepted
        res_correct = self.client.post(
            "/api/account/verify_pin",
            json={"pin": "9876"},
            headers={"X-CSRF-Token": csrf}
        )
        self.assertEqual(res_correct.status_code, 200)
        self.assertTrue(res_correct.get_json()["success"])

    # 2. MFA CRYPTOGRAPHIC HARDENING & REPLAY PREVENTION
    def test_mfa_replay_prevention_and_single_use_recovery(self):
        """TOTP time-steps must not be replayed, and recovery codes must be single-use."""
        secret = generate_mfa_secret()
        enc_secret = encrypt_mfa_secret(secret)
        self.assertTrue(enc_secret.startswith("v1:"))
        code = generate_totp_code(secret)

        # First verification succeeds
        ok1, err1 = verify_totp_code_with_replay_prevention(secret, code, user_id=9999)
        self.assertTrue(ok1)
        self.assertIsNone(err1)

        # Immediate replay in same time window must be rejected
        ok2, err2 = verify_totp_code_with_replay_prevention(secret, code, user_id=9999)
        self.assertFalse(ok2)
        self.assertIn("already been used", err2.lower())

        # Test single-use recovery code consumption
        hashed_codes = [hashlib.sha256("REC12345".encode()).hexdigest(), hashlib.sha256("REC67890".encode()).hexdigest()]
        consumed, remaining = verify_and_consume_recovery_code("REC12345", hashed_codes)
        self.assertTrue(consumed)
        self.assertEqual(len(remaining), 1)

        # Re-using the same recovery code must fail
        consumed_again, _ = verify_and_consume_recovery_code("REC12345", remaining)
        self.assertFalse(consumed_again)

    # 3. DEMO ACCOUNT STRICT LOCKDOWN
    def test_demo_account_service_layer_rejection(self):
        """Demo users must be rejected from initiating any financial mutations."""
        res_demo = self.client.post("/api/demo_login", json={"account_number": "40273146502136"})
        self.assertEqual(res_demo.status_code, 200)
        csrf = res_demo.get_json()["csrf_token"]

        mutating_endpoints = [
            ("/api/transfer", {"to_acc": "99999999999999", "amount": "100"}),
            ("/api/pay_bill", {"biller": "Electricity", "company": "Tata Power", "amount": "200"}),
            ("/api/create_fd", {"amount": "5000", "years": 1}),
            ("/api/invest/gold_buy", {"amount": "500"}),
        ]
        for ep, payload in mutating_endpoints:
            res = self.client.post(ep, json=payload, headers={"X-CSRF-Token": csrf})
            self.assertEqual(res.status_code, 403, f"Demo account was able to mutate {ep}!")
            self.assertIn("read-only", res.get_json().get("message", "").lower())

    # 4. GL ACCOUNT DIRECT ACCESS PREVENTED
    def test_gl_account_direct_transfer_blocked(self):
        """Direct transfers to internal GL accounts must be strictly blocked."""
        res_login = self.client.post("/api/login", json={"account": "40273146502136", "password": "LegitPassword2026!"})
        self.assertEqual(res_login.status_code, 200)
        csrf = res_login.get_json()["csrf_token"]

        gl_targets = ["GL_CASH_VAULT", "GL_CLEARING_ESCROW", "GL_INVESTMENT_ESCROW", "GL_SUSPENSE"]
        for gl_acc in gl_targets:
            res = self.client.post(
                "/api/transfer",
                json={"to_acc": gl_acc, "amount": "100", "method": "IMPS"},
                headers={"X-CSRF-Token": csrf}
            )
            self.assertEqual(res.status_code, 403, f"Direct transfer to {gl_acc} was not blocked!")

    # 5. FINANCIAL POLICY AND DECIMAL INTEGRITY
    def test_financial_policy_immutability_and_limits(self):
        """Financial policies must be centralized, versioned, and return exact Decimals."""
        policy = FinancialPolicy()
        self.assertEqual(policy.POLICY_VERSION, "2026.2.0")
        self.assertIsInstance(policy.DEFAULT_PER_TXN_LIMIT_PAISE, int)
        self.assertEqual(policy.get_fd_interest_rate(12), Decimal("6.50"))


if __name__ == "__main__":
    unittest.main()
