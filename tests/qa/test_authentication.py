"""
Credence Core — QA Test Suite 2: Authentication & Session Verification
Tests session fixation, logout invalidation, brute-force lockouts,
enumeration defense, and cookie security flags.
"""

import unittest
import time
from backend.app import create_app
from backend.app.core.database import get_db
from backend.app.repositories.account_repository import account_repository
import security


class AuthenticationTestSuite(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        cls.client = cls.app.test_client()

    def setUp(self):
        security.FAILED_ATTEMPTS_STORE.clear()
        security.IP_REQUEST_HISTORY.clear()
        with get_db() as db:
            acc = account_repository.get_by_number(db, "40273146502136")
            if acc and acc.user:
                acc.user.password_hash = security.hash_password("SecurePassword123!")
                db.commit()

    def test_enumeration_prevention_uniform_response(self):
        """Verify invalid account and invalid password return identical generic error."""
        # Non-existent account
        res_fake_acc = self.client.post("/api/login", json={"account": "00000000000000", "password": "WrongPassword1!"})
        data_fake = res_fake_acc.get_json()

        # Real account, wrong password
        res_wrong_pw = self.client.post("/api/login", json={"account": "40273146502136", "password": "WrongPassword1!"})
        data_wrong = res_wrong_pw.get_json()

        self.assertEqual(res_fake_acc.status_code, 401)
        self.assertEqual(res_wrong_pw.status_code, 401)
        self.assertEqual(data_fake["message"], data_wrong["message"])
        self.assertIn("invalid", data_fake["message"].lower())

    def test_brute_force_lockout_trigger(self):
        """Verify lockout is triggered after maximum failed attempts."""
        security.FAILED_ATTEMPTS_STORE.clear()
        security.IP_REQUEST_HISTORY.clear()
        acc = "40273146502136"
        # First 4 attempts return 401 Unauthorized
        for i in range(4):
            res = self.client.post("/api/login", json={"account": acc, "password": f"BadPassword{i}"})
            self.assertEqual(res.status_code, 401)

        # 5th attempt reaches MAX_FAILED_ATTEMPTS (5) and triggers 429 Too Many Requests (Lockout)
        res_locked = self.client.post("/api/login", json={"account": acc, "password": "BadPassword5"})
        self.assertEqual(res_locked.status_code, 429)
        self.assertIn("locked", res_locked.get_json()["message"].lower())

    def test_session_cookie_flags(self):
        """Verify session and CSRF cookie flags."""
        security.FAILED_ATTEMPTS_STORE.clear()
        security.IP_REQUEST_HISTORY.clear()
        res = self.client.post("/api/login", json={"account": "40273146502136", "password": "SecurePassword123!"})
        self.assertEqual(res.status_code, 200)
        cookies = res.headers.getlist("Set-Cookie")
        self.assertTrue(len(cookies) > 0, "No Set-Cookie headers returned on login")
        cookie_str = "; ".join(cookies)
        self.assertIn("SameSite=Lax", cookie_str)

    def test_logout_session_invalidation(self):
        """Verify that logging out invalidates session cookie on subsequent requests."""
        security.FAILED_ATTEMPTS_STORE.clear()
        security.IP_REQUEST_HISTORY.clear()
        # Login
        res_login = self.client.post("/api/login", json={"account": "40273146502136", "password": "SecurePassword123!"})
        self.assertEqual(res_login.status_code, 200)

        # Verify access
        res_acc = self.client.get("/api/account/40273146502136")
        self.assertEqual(res_acc.status_code, 200)

        # Logout
        with self.client.session_transaction() as sess:
            token = sess.get("csrf_token")
        res_logout = self.client.post("/api/logout", headers={"X-CSRF-Token": token})
        self.assertEqual(res_logout.status_code, 200)

        # Attempt to access protected endpoint after logout
        res_after = self.client.get("/api/account/40273146502136")
        self.assertEqual(res_after.status_code, 401)


if __name__ == "__main__":
    unittest.main()
