"""
Credence Core — QA Test Suite 1: Full API Regression Testing
Verifies consistent API contracts, deterministic responses, and status codes across all modules.
"""

import unittest
import json
from backend.app import create_app
from backend.app.core.database import get_db
from backend.app.models import User, Account
import security


class ApiRegressionTestSuite(unittest.TestCase):

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

    def test_health_and_observability_endpoints(self):
        """Verify liveness, readiness, and metrics endpoints."""
        res_live = self.client.get("/health/live")
        self.assertEqual(res_live.status_code, 200)
        self.assertEqual(res_live.get_json()["status"], "UP")

        res_ready = self.client.get("/health/ready")
        self.assertIn(res_ready.status_code, [200, 503])
        self.assertIn("components", res_ready.get_json())

        res_metrics = self.client.get("/api/metrics")
        self.assertEqual(res_metrics.status_code, 200)
        data = res_metrics.get_json()
        self.assertIn("requests_total", data)
        self.assertIn("latency_ms", data)

    def test_account_summary_contract(self):
        """Verify GET /api/account/<acc_no> contract."""
        headers = self._login_session()
        res = self.client.get("/api/account/40273146502136", headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("account_number", data)
        self.assertIn("balance", data)
        self.assertIn("status", data)

    def test_investment_performance_contract(self):
        """Verify GET /api/investments/performance returns validated schema."""
        headers = self._login_session()
        res = self.client.get("/api/investments/performance", headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertIn("summary", data)
        self.assertIn("asset_allocation", data)
        self.assertIn("gold", data)

    def test_spending_insights_contract(self):
        """Verify GET /api/analytics/insights returns financial analysis."""
        headers = self._login_session()
        res = self.client.get("/api/analytics/insights", headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertIn("cash_flow", data)
        self.assertIn("category_breakdown", data)
        self.assertIn("advisory_insights", data)

    def test_unauthenticated_api_rejection(self):
        """Verify all private endpoints reject unauthenticated requests."""
        endpoints = [
            ("/api/account/40273146502136", "GET"),
            ("/api/transfer", "POST"),
            ("/api/beneficiaries", "GET"),
            ("/api/notifications", "GET"),
            ("/api/support/tickets", "GET"),
            ("/api/admin/dashboard", "GET"),
        ]
        anon_client = self.app.test_client()
        for ep, method in endpoints:
            if method == "GET":
                res = anon_client.get(ep)
            else:
                res = anon_client.post(ep, json={})
            self.assertEqual(res.status_code, 401, f"Expected 401 for unauthenticated {method} {ep}")


if __name__ == "__main__":
    unittest.main()
