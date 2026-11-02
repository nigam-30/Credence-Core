"""
Credence Core — QA Test Suite 6: Isolated Penetration Testing
Evaluates defenses against SQL injection, XSS, BOLA/IDOR, privilege escalation,
and oversized payload Denial-of-Service attacks.
"""

import unittest
from backend.app import create_app
import security


class PenetrationSecurityTestSuite(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        cls.client = cls.app.test_client()

    def _login_session(self, account="40273146502136", role="user"):
        with self.client.session_transaction() as sess:
            sess["user_id"] = str(account)
            sess["role"] = role
            sess["auth_time"] = 9999999999.0
            sess["csrf_token"] = security.generate_csrf_token()
            token = sess["csrf_token"]
        return {"X-CSRF-Token": token}

    def test_sql_injection_defense(self):
        """Verify SQL injection payloads in login and transaction searches are neutralized."""
        sqli_payloads = [
            "' OR '1'='1",
            "admin'--",
            "' UNION SELECT null, null, null--",
            "'; DROP TABLE accounts; --"
        ]
        for payload in sqli_payloads:
            res_login = self.client.post("/api/login", json={"account": payload, "password": "Password123!"})
            # Must reject with 400 (validation error) or 401, NEVER 500 or bypass
            self.assertIn(res_login.status_code, [400, 401])

        # Transaction search with SQLi payload
        headers = self._login_session()
        res_search = self.client.get("/api/transactions/search?query=' OR 1=1--", headers=headers)
        self.assertEqual(res_search.status_code, 200)
        # Should return safe JSON results without executing raw SQL
        self.assertTrue(isinstance(res_search.get_json()["transactions"], list))

    def test_cross_site_scripting_sanitization(self):
        """Verify XSS vectors in input strings are neutralized."""
        headers = self._login_session()
        xss_payloads = [
            "<script>alert('pwned')</script>",
            "<img src=x onerror=alert(document.cookie)>",
            "javascript:alert(1)"
        ]
        for xss in xss_payloads:
            res_ticket = self.client.post(
                "/api/support/tickets",
                json={"subject": xss, "category": "GENERAL", "priority": "LOW", "message": f"Help {xss}"},
                headers=headers
            )
            self.assertEqual(res_ticket.status_code, 200)
            data = res_ticket.get_json()
            self.assertTrue(data["success"])

        # Fetch tickets and ensure script tags are not rendered raw
        res_list = self.client.get("/api/support/tickets", headers=headers)
        self.assertEqual(res_list.status_code, 200)
        for t in res_list.get_json()["tickets"]:
            self.assertNotIn("<script>", t["subject"])

    def test_bola_idor_cross_account_block(self):
        """Verify BOLA: Customer A cannot view or debit from Customer B's account."""
        victim_acc = "99999999999999"
        headers_attacker = self._login_session(account="40273146502136", role="user")

        # Attacker attempts to initiate transfer specifying from_acc as victim
        res_transfer = self.client.post(
            "/api/transfer",
            json={"from_acc": victim_acc, "to_acc": "40273146502136", "amount": "100", "method": "IMPS"},
            headers=headers_attacker
        )
        self.assertEqual(res_transfer.status_code, 403)
        self.assertIn("cannot initiate transfers", res_transfer.get_json()["message"].lower())

    def test_privilege_escalation_block(self):
        """Verify non-admin user cannot access administrative operations."""
        headers_user = self._login_session(account="40273146502136", role="user")
        admin_endpoints = [
            ("/api/admin/dashboard", "GET"),
            ("/api/admin/audit_logs", "GET"),
            ("/api/admin/accounts/40273146502136/freeze", "POST"),
            ("/api/admin/fraud/alerts", "GET"),
        ]
        for ep, method in admin_endpoints:
            if method == "GET":
                res = self.client.get(ep, headers=headers_user)
            else:
                res = self.client.post(ep, json={"reason": "Hacking"}, headers=headers_user)
            self.assertEqual(res.status_code, 403, f"Non-admin reached {ep}")

    def test_oversized_payload_protection(self):
        """Verify oversized request (> 2MB MAX_CONTENT_LENGTH) is rejected with 413."""
        headers = self._login_session()
        huge_payload = "A" * (3 * 1024 * 1024)  # 3 MB
        res = self.client.post(
            "/api/support/tickets",
            data=huge_payload,
            content_type="application/json",
            headers=headers
        )
        self.assertIn(res.status_code, [400, 413])


if __name__ == "__main__":
    unittest.main()
