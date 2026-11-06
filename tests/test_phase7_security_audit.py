"""
Credence Core — Phase 7: Independent Security Audit & Vulnerability Remediation Test Suite
Validates all Phase 7 remediations across Authentication, Authorization, Financial Transactions,
API Security, Input Validation, and Cryptographic Controls.
"""

import unittest
import json
import time
import secrets
import hmac
import hashlib
from decimal import Decimal

from backend.app import create_app
from backend.app.core.config import Config
from backend.app.core.database import get_db
from backend.app.services.authentication.auth_service import generate_mfa_ticket, verify_mfa_ticket
from backend.app.services.ledger import ledger_service
from models import User, Account, AccountBalance, Investment, SIP, TransactionLimit
import security


class Phase7SecurityAuditTestSuite(unittest.TestCase):
    """
    Independent verification test suite for Phase 7 security remediations.
    Exercises genuine HTTP endpoints, Argon2id auth, role-based controls,
    ledger invariants, and cryptographic HMAC protection.
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
        with get_db() as db:
            acc = db.query(Account).filter(Account.account_number == "40273146502136").first()
            if acc and acc.user:
                acc.user.password_hash = security.hash_password("AuditPassword2026!")
                acc.user.mfa_enabled = False
                acc.user.status = "ACTIVE"
                acc.user.role = "user"
                db.commit()

    def _login(self, client, account_number="40273146502136", password="AuditPassword2026!"):
        res = client.post(
            "/api/login",
            json={"account_number": account_number, "password": password},
            content_type="application/json"
        )
        self.assertEqual(res.status_code, 200, f"Login failed for {account_number}: {res.get_json()}")
        data = res.get_json()
        return data.get("csrf_token")

    # ══════════════════════════════════════════════════════════════
    # 1. FINANCIAL TRANSACTION SECURITY: DIGITAL GOLD SELL VULNERABILITY
    # ══════════════════════════════════════════════════════════════
    def test_gold_sell_zero_holdings_rejected(self):
        """Users with zero or insufficient gold holdings cannot sell gold to mint money."""
        client = self.app.test_client()
        csrf = self._login(client)

        # Clear any existing gold holdings for test account
        with get_db() as db:
            inv = db.query(Investment).filter(Investment.account_number == "40273146502136").first()
            if inv:
                inv.gold_grams = Decimal("0.0")
                inv.gold_total_invested_paise = 0
                db.commit()

        # Attempt to sell 5 grams of gold without owning any
        res = client.post(
            "/api/invest/gold_sell",
            json={"grams": 5.0},
            headers={"X-CSRF-Token": csrf},
            content_type="application/json"
        )
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data["success"])
        self.assertIn("Insufficient digital gold holdings", data["message"])

    def test_gold_sell_invalid_grams_rejected(self):
        """Selling negative or zero grams of gold must be rejected."""
        client = self.app.test_client()
        csrf = self._login(client)

        for invalid_grams in [0.0, -1.5, -100.0]:
            res = client.post(
                "/api/invest/gold_sell",
                json={"grams": invalid_grams},
                headers={"X-CSRF-Token": csrf},
                content_type="application/json"
            )
            self.assertEqual(res.status_code, 400)
            data = res.get_json()
            self.assertFalse(data["success"])

    def test_gold_buy_and_sell_lifecycle_and_ledger_balance(self):
        """Legitimate gold buy followed by partial sell updates holdings and maintains balanced ledger."""
        client = self.app.test_client()
        csrf = self._login(client)

        # 1. Ensure user has starting balance via canonical double-entry deposit
        client.post(
            "/api/deposit",
            json={"amount": 25000.0},
            headers={"X-CSRF-Token": csrf},
            content_type="application/json"
        )

        # 2. Buy gold: ₹15,241.00 (approx 2.0 grams)
        buy_res = client.post(
            "/api/invest/gold_buy",
            json={"amount": 15241.00},
            headers={"X-CSRF-Token": csrf},
            content_type="application/json"
        )
        self.assertEqual(buy_res.status_code, 200, buy_res.get_json())

        # Check holdings in DB
        with get_db() as db:
            inv = db.query(Investment).filter(Investment.account_number == "40273146502136").first()
            self.assertIsNotNone(inv)
            self.assertGreater(float(inv.gold_grams), 1.9)
            initial_grams = float(inv.gold_grams)

        # 3. Sell 1.0 gram
        sell_res = client.post(
            "/api/invest/gold_sell",
            json={"grams": 1.0},
            headers={"X-CSRF-Token": csrf},
            content_type="application/json"
        )
        self.assertEqual(sell_res.status_code, 200, sell_res.get_json())
        sell_data = sell_res.get_json()
        self.assertTrue(sell_data["success"])
        self.assertAlmostEqual(sell_data["grams"], 1.0, places=3)

        # 4. Verify reduced holdings in DB
        with get_db() as db:
            inv = db.query(Investment).filter(Investment.account_number == "40273146502136").first()
            self.assertAlmostEqual(float(inv.gold_grams), initial_grams - 1.0, places=3)

        # 5. Verify double-entry ledger remains strictly reconciled
        recon = ledger_service.reconcile()
        self.assertEqual(recon["status"], "HEALTHY")
        self.assertEqual(recon["discrepancy_paise"], 0)

    # ══════════════════════════════════════════════════════════════
    # 2. AUTHORIZATION & PRIVILEGE ENFORCEMENT: LEDGER REVERSALS
    # ══════════════════════════════════════════════════════════════
    def test_ledger_reverse_blocked_for_standard_user(self):
        """Standard customers must be rejected with HTTP 403 when attempting ledger reversals."""
        client = self.app.test_client()
        csrf = self._login(client)

        res = client.post(
            "/api/ledger/reverse",
            json={"reference_id": "TXN-TEST-123", "reason": "Unauthorized reversal attempt"},
            headers={"X-CSRF-Token": csrf},
            content_type="application/json"
        )
        self.assertEqual(res.status_code, 403)
        data = res.get_json()
        self.assertFalse(data["success"])
        self.assertIn("Administrative privileges required", data["message"])

    def test_ledger_reverse_allowed_for_admin(self):
        """Admin users are authorized to access the reversal endpoint."""
        client = self.app.test_client()
        with get_db() as db:
            acc = db.query(Account).filter(Account.account_number == "40273146502136").first()
            if acc and acc.user:
                acc.user.role = "admin"
                db.commit()

        csrf = self._login(client)
        res = client.post(
            "/api/ledger/reverse",
            json={"reference_id": "NON-EXISTENT-TXN", "reason": "Admin test"},
            headers={"X-CSRF-Token": csrf},
            content_type="application/json"
        )
        # Non-existent reference returns 400 Bad Request, NOT 403 Forbidden
        self.assertEqual(res.status_code, 400)
        self.assertIn("not found", res.get_json()["message"])

    # ══════════════════════════════════════════════════════════════
    # 3. INPUT VALIDATION & STABILITY: ACCOUNT CREATION
    # ══════════════════════════════════════════════════════════════
    def test_create_account_negative_deposit_rejected(self):
        """Negative initial deposit in account creation must return 400 Bad Request."""
        res = self.client.post(
            "/api/create_account",
            json={
                "name": "Audit Test User",
                "password": "StrongPassword2026!",
                "deposit": -500.0,
                "email": "audit_test_neg@credence.bank"
            },
            content_type="application/json"
        )
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data["success"])
        self.assertIn("cannot be negative", data["message"])

    def test_create_account_excessive_deposit_rejected(self):
        """Initial deposit exceeding ₹1 Crore must return 400 Bad Request."""
        res = self.client.post(
            "/api/create_account",
            json={
                "name": "Audit Test User",
                "password": "StrongPassword2026!",
                "deposit": 100_000_000.0,  # ₹10 Crore
                "email": "audit_test_exc@credence.bank"
            },
            content_type="application/json"
        )
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data["success"])
        self.assertIn("exceeds maximum allowed limit", data["message"])

    def test_create_account_no_name_error_crash(self):
        """Account creation with valid deposit succeeds smoothly without NameError."""
        unique_suffix = secrets.token_hex(4)
        pan_digits = f"{1000 + int(unique_suffix, 16) % 8999:04d}"
        res = self.client.post(
            "/api/create_account",
            json={
                "name": f"Audit Valid User {unique_suffix}",
                "password": "StrongPassword2026!",
                "deposit": 5000.0,
                "email": f"audit_{unique_suffix}@credence.bank",
                "pan": f"ABCDE{pan_digits}Z"
            },
            content_type="application/json"
        )
        self.assertEqual(res.status_code, 200, res.get_json())
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertIn("account_number", data)

    # ══════════════════════════════════════════════════════════════
    # 4. BOLA / IDOR PROTECTION: SIP LIFECYCLE ACTIONS
    # ══════════════════════════════════════════════════════════════
    def test_sip_action_cross_user_bola_rejected(self):
        """Customer cannot pause or cancel another customer's SIP investment (HTTP 403)."""
        # Create a SIP belonging to a different account (e.g. 99999999999999)
        test_sip_id = f"SIP-AUDIT-{secrets.token_hex(3)}"
        with get_db() as db:
            sip = SIP(
                sip_id=test_sip_id,
                account_number="99999999999999",
                fund_id="HDFC-TOP100",
                fund_name="HDFC Top 100 Fund",
                category="Large Cap",
                monthly_amount_paise=200000,
                invested_amount_paise=200000,
                current_value_paise=200000,
                status="Active"
            )
            db.add(sip)
            db.commit()

        client = self.app.test_client()
        csrf = self._login(client)

        # Authenticated user 40273146502136 tries to pause 99999999999999's SIP
        res = client.post(
            "/api/invest/sip_action",
            json={"sip_id": test_sip_id, "action": "pause"},
            headers={"X-CSRF-Token": csrf},
            content_type="application/json"
        )
        self.assertEqual(res.status_code, 403)
        data = res.get_json()
        self.assertFalse(data["success"])
        self.assertIn("Access denied", data["message"])

    def test_sip_action_own_sip_status_update(self):
        """Customer can pause, resume, and redeem their own SIP investments."""
        test_sip_id = f"SIP-OWN-{secrets.token_hex(3)}"
        with get_db() as db:
            sip = SIP(
                sip_id=test_sip_id,
                account_number="40273146502136",
                fund_id="ICICI-PRU-BLUE",
                fund_name="ICICI Prudential Bluechip",
                category="Large Cap",
                monthly_amount_paise=500000,
                invested_amount_paise=500000,
                current_value_paise=500000,
                status="Active"
            )
            db.add(sip)
            db.commit()

        client = self.app.test_client()
        csrf = self._login(client)

        # 1. Pause
        res_pause = client.post(
            "/api/invest/sip_action",
            json={"sip_id": test_sip_id, "action": "pause"},
            headers={"X-CSRF-Token": csrf},
            content_type="application/json"
        )
        self.assertEqual(res_pause.status_code, 200)
        self.assertEqual(res_pause.get_json()["status"], "Paused")

        # 2. Resume
        res_resume = client.post(
            "/api/invest/sip_action",
            json={"sip_id": test_sip_id, "action": "resume"},
            headers={"X-CSRF-Token": csrf},
            content_type="application/json"
        )
        self.assertEqual(res_resume.status_code, 200)
        self.assertEqual(res_resume.get_json()["status"], "Active")

        # 3. Cancel/Redeem
        res_cancel = client.post(
            "/api/invest/sip_action",
            json={"sip_id": test_sip_id, "action": "cancel"},
            headers={"X-CSRF-Token": csrf},
            content_type="application/json"
        )
        self.assertEqual(res_cancel.status_code, 200)
        self.assertEqual(res_cancel.get_json()["status"], "Redeemed")

        # Verify DB state
        with get_db() as db:
            updated_sip = db.query(SIP).filter(SIP.sip_id == test_sip_id).first()
            self.assertEqual(updated_sip.status, "Redeemed")

    # ══════════════════════════════════════════════════════════════
    # 5. INPUT BOUNDARIES: TRANSACTION LIMITS
    # ══════════════════════════════════════════════════════════════
    def test_settings_negative_limits_rejected(self):
        """Negative transaction limit configurations must be rejected with HTTP 400."""
        client = self.app.test_client()
        csrf = self._login(client)

        res = client.post(
            "/api/settings/limits",
            json={"daily_limit": -1000.0},
            headers={"X-CSRF-Token": csrf},
            content_type="application/json"
        )
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data["success"])

    def test_settings_excessive_limits_rejected(self):
        """Absurdly high limits exceeding ₹5 Crore must be rejected with HTTP 400."""
        client = self.app.test_client()
        csrf = self._login(client)

        res = client.post(
            "/api/settings/limits",
            json={"daily_limit": 600_000_000.0},  # ₹60 Crore
            headers={"X-CSRF-Token": csrf},
            content_type="application/json"
        )
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data["success"])

    def test_settings_valid_limits_accepted(self):
        """Valid transaction limits update cleanly and accurately."""
        client = self.app.test_client()
        csrf = self._login(client)

        res = client.post(
            "/api/settings/limits",
            json={"daily_limit": 250000.0, "per_txn_limit": 50000.0},
            headers={"X-CSRF-Token": csrf},
            content_type="application/json"
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])

    # ══════════════════════════════════════════════════════════════
    # 6. CRYPTOGRAPHIC DATA PROTECTION: MFA TICKET HMAC INTEGRITY
    # ══════════════════════════════════════════════════════════════
    def test_mfa_ticket_hmac_tamper_proofing(self):
        """Tampering with MFA ticket account or timestamp must fail HMAC signature verification."""
        ticket = generate_mfa_ticket(user_id=1, account_number="40273146502136")
        self.assertIsNotNone(ticket)

        # Valid ticket verifies
        verified = verify_mfa_ticket(ticket)
        self.assertIsNotNone(verified)
        u_id, acc_no = verified
        self.assertEqual(u_id, 1)
        self.assertEqual(acc_no, "40273146502136")

        # Tampered account number
        parts = ticket.split(":")
        tampered_ticket = f"{parts[0]}:99999999999999:{parts[2]}:{parts[3]}"
        self.assertIsNone(verify_mfa_ticket(tampered_ticket))

        # Tampered signature
        bad_sig_ticket = f"{parts[0]}:{parts[1]}:{parts[2]}:0123456789abcdef"
        self.assertIsNone(verify_mfa_ticket(bad_sig_ticket))


if __name__ == "__main__":
    unittest.main()
