"""
Credence Core — Phase 1: Security Test Suite
Automated regression and vulnerability verification tests.
"""

import unittest
import json
import re
from flask_app import app, bank
import security

class CredenceSecurityTestSuite(unittest.TestCase):

    def setUp(self):
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = True
        self.client = app.test_client()
        # Reset brute-force tracking between test cases
        security.FAILED_ATTEMPTS_STORE.clear()

    def _login(self, client, account="40273146502136", role="user"):
        """Helper to establish an authenticated session for an account."""
        with client.session_transaction() as sess:
            sess["user_id"] = str(account)
            sess["role"] = role
            sess["auth_time"] = 9999999999.0  # Far future timestamp to prevent expiration during test
            sess["csrf_token"] = security.generate_csrf_token()
            token = sess["csrf_token"]
        return token

    # 1. UNAUTHORIZED ACCOUNT ACCESS
    def test_unauthorized_account_access_rejected(self):
        """Unauthenticated requests to account, statement, loans, and investments must return 401."""
        endpoints = [
            "/api/account/40273146502136",
            "/api/statement/40273146502136",
            "/api/loans/40273146502136",
            "/api/investments/40273146502136"
        ]
        for ep in endpoints:
            res = self.client.get(ep)
            self.assertEqual(res.status_code, 401, f"Endpoint {ep} did not enforce authentication (got {res.status_code})")
            data = res.get_json()
            self.assertFalse(data.get("success", True))

    # 2. CROSS-ACCOUNT / BOLA / IDOR PREVENTION
    def test_cross_account_bola_access_rejected(self):
        """An authenticated user must NOT be able to view another user's account, statements, or loans."""
        # Log in as user 40273146502136
        self._login(self.client, account="40273146502136", role="user")
        victim_acc = "99999999999999"

        endpoints = [
            f"/api/account/{victim_acc}",
            f"/api/statement/{victim_acc}",
            f"/api/loans/{victim_acc}",
            f"/api/investments/{victim_acc}"
        ]
        for ep in endpoints:
            res = self.client.get(ep)
            self.assertEqual(res.status_code, 403, f"BOLA vulnerability detected on {ep}: got {res.status_code} instead of 403")
            data = res.get_json()
            self.assertFalse(data.get("success", True))

    # 3. CROSS-ACCOUNT TRANSFERS
    def test_cross_account_transfer_rejected(self):
        """An authenticated user cannot transfer funds out of an account they do not own."""
        csrf_token = self._login(self.client, account="40273146502136", role="user")
        
        # User 40273146502136 attempts to transfer out of victim account 99999999999999
        payload = {
            "from_acc": "99999999999999",
            "to_acc": "40273146502136",
            "amount": "500"
        }
        res = self.client.post(
            "/api/transfer",
            json=payload,
            headers={"X-CSRF-Token": csrf_token}
        )
        self.assertEqual(res.status_code, 403, f"Cross-account transfer was not blocked with 403: got {res.status_code}")
        data = res.get_json()
        self.assertFalse(data.get("success", True))
        self.assertIn("do not own", data.get("message", "").lower())

    # 4. UNAUTHORIZED PIN RESET
    def test_unauthorized_pin_reset_rejected(self):
        """PIN reset must require authentication and validation of old credentials."""
        # Case A: Unauthenticated
        res = self.client.post("/api/reset_upi_pin", json={"account": "40273146502136", "upi_pin": "1234"})
        self.assertEqual(res.status_code, 401)

        # Case B: Authenticated, but no current password or old PIN supplied
        csrf_token = self._login(self.client, account="40273146502136", role="user")
        res = self.client.post(
            "/api/reset_upi_pin",
            json={"account": "40273146502136", "upi_pin": "9876", "password": "wrongpassword"},
            headers={"X-CSRF-Token": csrf_token}
        )
        self.assertEqual(res.status_code, 403)
        self.assertFalse(res.get_json().get("success", True))

    # 5. ACCOUNT ENUMERATION RESISTANCE
    def test_account_enumeration_resistance(self):
        """Login failure messages must be identical regardless of whether the account exists or password was wrong."""
        res_nonexistent = self.client.post(
            "/api/login",
            json={"account": "00000000000000", "password": "RandomPassword123"}
        )
        res_wrong_pw = self.client.post(
            "/api/login",
            json={"account": "40273146502136", "password": "WrongPassword123"}
        )

        self.assertEqual(res_nonexistent.status_code, 401)
        self.assertEqual(res_wrong_pw.status_code, 401)
        
        data_nonexistent = res_nonexistent.get_json()
        data_wrong_pw = res_wrong_pw.get_json()

        # Both must return the same generic user-facing message
        self.assertEqual(
            data_nonexistent.get("message"),
            data_wrong_pw.get("message"),
            "Error messages differ, enabling account enumeration!"
        )

    # 6. PASSWORD BRUTE-FORCE LOCKOUT
    def test_password_brute_force_lockout(self):
        """Repeated failed login attempts must trigger a lockout with HTTP 429."""
        target_account = "40273146502136"
        locked_out = False

        for i in range(7):
            res = self.client.post(
                "/api/login",
                json={"account": target_account, "password": f"BadPassword{i}"}
            )
            if res.status_code == 429:
                locked_out = True
                data = res.get_json()
                self.assertIn("locked", data.get("message", "").lower())
                break

        self.assertTrue(locked_out, "Account lockout was not triggered after multiple consecutive failed attempts.")

    # 7. SESSION EXPIRATION & LOGOUT INVALIDATION
    def test_session_expiration_and_logout(self):
        """Logging out must destroy the session and invalidate subsequent API access."""
        csrf_token = self._login(self.client, account="40273146502136", role="user")

        # Verify access while logged in
        res1 = self.client.get("/api/account/40273146502136")
        self.assertEqual(res1.status_code, 200)

        # Call logout
        res_logout = self.client.post("/api/logout")
        self.assertEqual(res_logout.status_code, 200)

        # Verify subsequent access is rejected with 401
        res2 = self.client.get("/api/account/40273146502136")
        self.assertEqual(res2.status_code, 401, "Session remained active after logout!")

    # 8. CSRF ATTACK PREVENTION
    def test_csrf_attack_blocked(self):
        """Mutating POST requests without valid CSRF tokens must be rejected with HTTP 403."""
        # Log in without setting valid CSRF header in request
        csrf_token = self._login(self.client, account="40273146502136", role="user")

        # Attempt A: Missing CSRF header entirely
        res_missing = self.client.post(
            "/api/deposit",
            json={"account": "40273146502136", "amount": "100"}
        )
        self.assertEqual(res_missing.status_code, 403, "POST request without CSRF token was not rejected with 403")

        # Attempt B: Tampered/invalid CSRF header
        res_invalid = self.client.post(
            "/api/deposit",
            json={"account": "40273146502136", "amount": "100"},
            headers={"X-CSRF-Token": "forged_malicious_token_12345"}
        )
        self.assertEqual(res_invalid.status_code, 403, "POST request with invalid CSRF token was not rejected with 403")

        # Attempt C: Valid CSRF header -> accepted past CSRF layer
        res_valid = self.client.post(
            "/api/deposit",
            json={"account": "40273146502136", "amount": "100"},
            headers={"X-CSRF-Token": csrf_token}
        )
        self.assertEqual(res_valid.status_code, 200)

    # 9. XSS PAYLOAD SANITIZATION
    def test_xss_payload_sanitization(self):
        """Dangerous HTML script tags and javascript injection characters must be escaped."""
        raw_xss = '<script>alert("pwned")</script><b>ValidText</b>'
        sanitized = security.sanitize_string(raw_xss)
        self.assertNotIn("<script>", sanitized)
        self.assertNotIn("</script>", sanitized)
        self.assertIn("&lt;script&gt;", sanitized)
        self.assertIn("&quot;pwned&quot;", sanitized)

    # 10. PRIVILEGE ESCALATION PREVENTION
    def test_privilege_escalation_prevented(self):
        """Non-admin users must NOT be able to access administrative endpoints or run raw C++ engine commands."""
        csrf_token = self._login(self.client, account="40273146502136", role="user")

        admin_endpoints = [
            ("/api/accounts", "GET", None),
            ("/api/demo_info", "GET", None),
            ("/api/execute", "POST", {"choice": "1", "inputs": ["40273146502136", "1000"]})
        ]

        for ep, method, payload in admin_endpoints:
            if method == "GET":
                res = self.client.get(ep)
            else:
                res = self.client.post(ep, json=payload, headers={"X-CSRF-Token": csrf_token})
            self.assertEqual(res.status_code, 403, f"Non-admin gained access to {ep} with status {res.status_code}")
            data = res.get_json()
            self.assertFalse(data.get("success", True))

    # 11. SENSITIVE CREDENTIAL LEAKAGE PREVENTION
    def test_no_credential_leakage(self):
        """Responses must never return PINs, passwords, or plain CVVs to the client."""
        csrf_token = self._login(self.client, account="40273146502136", role="user")
        res = self.client.get("/api/account/40273146502136")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()

        # Check that PIN, password, and CVV are not present in payload
        self.assertNotIn("pin", data)
        self.assertNotIn("cvv", data)
        self.assertNotIn("password_hash", data)
        self.assertNotIn("nb_pass", data)

        # Check debit card masking if present
        card_num = data.get("card_number")
        if card_num:
            self.assertTrue(
                "•" in card_num or "*" in card_num,
                f"Card number was not masked: {card_num}"
            )

    # 12. LEGITIMATE USER FUNCTIONALITY PRESERVED
    def test_legitimate_flow_preserved(self):
        """An authorized user can access their account details and execute a legitimate deposit."""
        csrf_token = self._login(self.client, account="40273146502136", role="user")
        res = self.client.get("/api/account/40273146502136")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data.get("account_number"), "40273146502136")

        # Deposit funds into own account
        res_dep = self.client.post(
            "/api/deposit",
            json={"account": "40273146502136", "amount": "250"},
            headers={"X-CSRF-Token": csrf_token}
        )
        self.assertEqual(res_dep.status_code, 200)
        self.assertTrue(res_dep.get_json().get("success"))


if __name__ == "__main__":
    unittest.main()
