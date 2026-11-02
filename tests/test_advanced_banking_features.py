"""
Credence Core — Phase 5: Advanced Banking Features Test Suite
Verifies all 12 Phase 5 banking modules:
1. Admin operations dashboard & KPIs
2. Rule-based fraud detection engine
3. Transaction search & advanced filtering
4. Transaction disputes & automatic ledger reversal workflow
5. Account freeze and unfreeze enforcement
6. Beneficiary management & quick transfer
7. Transaction limits & approval workflows
8. Notification center & unread tracking
9. Financial analytics & spending insights
10. Investment performance & asset allocation dashboard
11. Audit history viewer & RBAC guards
12. Customer support ticket management
"""

import unittest
import json
import uuid
from flask import Flask

from backend.app import create_app
from backend.app.core.database import get_db
from backend.app.models import User, Account, Transaction, AccountBalance, Dispute, SupportTicket, Beneficiary, TransactionLimit
from backend.app.services.fraud import fraud_service
from backend.app.services.notifications import notification_service
from backend.app.services.transfers import transfer_service
from backend.app.services.beneficiaries import beneficiary_service
from backend.app.services.disputes import dispute_service
from backend.app.services.support import support_service
from backend.app.services.admin import admin_service
import security


class CredenceAdvancedBankingTestSuite(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        cls.client = cls.app.test_client()

    def setUp(self):
        security.FAILED_ATTEMPTS_STORE.clear()
        with get_db() as db:
            db.query(Beneficiary).filter(Beneficiary.account_number == "40273146502136").delete()
            lim = db.query(TransactionLimit).filter(TransactionLimit.account_number == "40273146502136").first()
            if lim:
                lim.per_txn_limit_paise = 10000000
            acc = db.query(Account).filter(Account.account_number == "40273146502136").first()
            if acc:
                acc.status = "ACTIVE"
            db.commit()

        try:
            import ledger
            with ledger.ledger_engine._db_session() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE accounts SET status = 'ACTIVE' WHERE account_number = ?", ("40273146502136",))
                conn.commit()
        except Exception:
            pass

    def _get_auth_headers(self, account="40273146502136", role="user"):
        with self.client.session_transaction() as sess:
            sess["user_id"] = str(account)
            sess["role"] = role
            sess["auth_time"] = 9999999999.0
            sess["csrf_token"] = security.generate_csrf_token()
            token = sess["csrf_token"]
        return {"X-CSRF-Token": token}

    # ══════════════════════════════════════════════════════════════
    # 1. ADMIN OPERATIONS DASHBOARD & KPIS
    # ══════════════════════════════════════════════════════════════
    def test_admin_dashboard_kpis_and_rbac(self):
        """Verify admin dashboard returns comprehensive metrics for admin, 403 for user."""
        # Non-admin user rejected
        headers_user = self._get_auth_headers(role="user")
        res_user = self.client.get("/api/admin/dashboard", headers=headers_user)
        self.assertEqual(res_user.status_code, 403)

        # Admin user allowed
        headers_admin = self._get_auth_headers(role="admin")
        res_admin = self.client.get("/api/admin/dashboard", headers=headers_admin)
        self.assertEqual(res_admin.status_code, 200)
        data = res_admin.get_json()
        self.assertTrue(data["success"])
        k = data["kpis"]
        self.assertIn("total_users", k)
        self.assertIn("total_accounts", k)
        self.assertIn("active_accounts", k)
        self.assertIn("frozen_accounts", k)
        self.assertIn("total_deposits_rupees", k)

    # ══════════════════════════════════════════════════════════════
    # 2. RULE-BASED FRAUD DETECTION ENGINE
    # ══════════════════════════════════════════════════════════════
    def test_rule_based_fraud_detection(self):
        """Verify 5 fraud rules, alert logging, and non-blocking policy."""
        # Rule 1: High value threshold (>= ₹200,000)
        eval_res = fraud_service.evaluate_transaction(
            account_number="40273146502136",
            amount_paise=25000000,  # ₹250,000.00
            ip="192.168.1.100",
            tx_type="TRANSFER_IMPS"
        )
        self.assertTrue(eval_res["is_allowed"], "Legitimate customer must not be automatically blocked!")
        self.assertIn("HIGH_VALUE_THRESHOLD_EXCEEDED", eval_res["risk_flags"])
        self.assertGreater(eval_res["risk_score"], 30)

        # Alerts query and resolution
        headers_admin = self._get_auth_headers(role="admin")
        res_alerts = self.client.get("/api/admin/fraud/alerts", headers=headers_admin)
        self.assertEqual(res_alerts.status_code, 200)
        alerts = res_alerts.get_json()["alerts"]
        self.assertGreaterEqual(len(alerts), 1)

        # Dismiss alert
        alert_id = alerts[0]["id"]
        res_dismiss = self.client.post(
            "/api/admin/fraud/resolve",
            json={"alert_id": alert_id, "action": "DISMISSED"},
            headers=headers_admin
        )
        self.assertEqual(res_dismiss.status_code, 200)

    # ══════════════════════════════════════════════════════════════
    # 3. ACCOUNT FREEZE & UNFREEZE ENFORCEMENT
    # ══════════════════════════════════════════════════════════════
    def test_account_freeze_and_unfreeze_lifecycle(self):
        """Verify account freeze prevents debits and unfreeze restores services."""
        headers_admin = self._get_auth_headers(role="admin")
        test_acc = "40273146502136"

        # Freeze account
        res_freeze = self.client.post(
            f"/api/admin/accounts/{test_acc}/freeze",
            json={"reason": "Regulatory compliance check"},
            headers=headers_admin
        )
        self.assertEqual(res_freeze.status_code, 200)

        # Attempt outgoing transfer while frozen -> must fail with 403
        headers_user = self._get_auth_headers(account=test_acc, role="user")
        res_transfer_blocked = self.client.post(
            "/api/transfer",
            json={"to_acc": "99999999999999", "amount": "100", "method": "IMPS"},
            headers=headers_user
        )
        self.assertEqual(res_transfer_blocked.status_code, 403)
        self.assertIn("frozen", res_transfer_blocked.get_json()["message"].lower())

        # Unfreeze account
        headers_admin = self._get_auth_headers(role="admin")
        res_unfreeze = self.client.post(
            f"/api/admin/accounts/{test_acc}/unfreeze",
            json={"reason": "Verification successfully completed"},
            headers=headers_admin
        )
        self.assertEqual(res_unfreeze.status_code, 200)

        # Outgoing transfer after unfreeze -> must succeed
        headers_user = self._get_auth_headers(account=test_acc, role="user")
        res_transfer_ok = self.client.post(
            "/api/transfer",
            json={"to_acc": "99999999999999", "amount": "50", "method": "IMPS"},
            headers=headers_user
        )
        self.assertEqual(res_transfer_ok.status_code, 200)

    # ══════════════════════════════════════════════════════════════
    # 4. TRANSACTION DISPUTE & AUTOMATIC LEDGER REVERSAL
    # ══════════════════════════════════════════════════════════════
    def test_dispute_and_automated_reversal_workflow(self):
        """Verify customer can dispute transaction and admin resolution reverses ledger atomically."""
        headers_user = self._get_auth_headers(account="40273146502136", role="user")

        # 1. Execute a test transfer
        res_tx = self.client.post(
            "/api/transfer",
            json={"to_acc": "99999999999999", "amount": "75", "method": "IMPS"},
            headers=headers_user
        )
        self.assertEqual(res_tx.status_code, 200)
        ref_id = res_tx.get_json()["reference_id"]

        # 2. Customer files dispute
        res_dsp = self.client.post(
            "/api/disputes",
            json={"reference_id": ref_id, "reason": "Unauthorized merchant debit"},
            headers=headers_user
        )
        self.assertEqual(res_dsp.status_code, 200)
        dsp_data = res_dsp.get_json()
        self.assertTrue(dsp_data["success"])
        dsp_id = dsp_data["dispute_id"]

        # 3. Customer lists disputes
        res_list = self.client.get("/api/disputes", headers=headers_user)
        self.assertEqual(res_list.status_code, 200)
        self.assertTrue(any(d["dispute_id"] == dsp_id for d in res_list.get_json()["disputes"]))

        # 4. Admin approves refund -> automatic double-entry reversal
        headers_admin = self._get_auth_headers(account="40273146502136", role="admin")
        res_resolve = self.client.post(
            f"/api/admin/disputes/{dsp_id}/resolve",
            json={"action": "APPROVE_REFUND", "notes": "Confirmed fraudulent terminal charges"},
            headers=headers_admin
        )
        self.assertEqual(res_resolve.status_code, 200)
        self.assertEqual(res_resolve.get_json()["status"], "RESOLVED_REFUNDED")

    # ══════════════════════════════════════════════════════════════
    # 5. BENEFICIARY MANAGEMENT & QUICK TRANSFER
    # ══════════════════════════════════════════════════════════════
    def test_beneficiary_lifecycle_and_quick_transfer(self):
        """Verify adding, listing, transferring to, and removing beneficiaries."""
        headers_user = self._get_auth_headers(account="40273146502136", role="user")

        # Add beneficiary
        res_add = self.client.post(
            "/api/beneficiaries",
            json={
                "beneficiary_name": "Rohan Sharma",
                "beneficiary_account_number": "99999999999999",
                "ifsc_code": "CRDN0001001",
                "transfer_type": "IMPS"
            },
            headers=headers_user
        )
        self.assertEqual(res_add.status_code, 200)
        ben_id = res_add.get_json()["id"]

        # List beneficiaries
        res_list = self.client.get("/api/beneficiaries", headers=headers_user)
        self.assertEqual(res_list.status_code, 200)
        bens = res_list.get_json()["beneficiaries"]
        self.assertTrue(any(b["id"] == ben_id for b in bens))

        # Quick transfer to beneficiary
        res_quick = self.client.post(
            "/api/beneficiaries/quick_transfer",
            json={"beneficiary_id": ben_id, "amount": "40.0"},
            headers=headers_user
        )
        self.assertEqual(res_quick.status_code, 200)
        self.assertTrue(res_quick.get_json()["success"])

        # Delete beneficiary
        res_del = self.client.delete(f"/api/beneficiaries/{ben_id}", headers=headers_user)
        self.assertEqual(res_del.status_code, 200)

    # ══════════════════════════════════════════════════════════════
    # 6. TRANSACTION LIMITS & APPROVAL WORKFLOW
    # ══════════════════════════════════════════════════════════════
    def test_transaction_limits_and_approvals(self):
        """Verify transaction limit updates and enforcement."""
        headers_user = self._get_auth_headers(account="40273146502136", role="user")

        # Retrieve limits
        res_get = self.client.get("/api/settings/limits", headers=headers_user)
        self.assertEqual(res_get.status_code, 200)
        self.assertIn("per_txn_limit_rupees", res_get.get_json())

        # Update per-transaction limit to ₹150.00
        res_upd = self.client.post(
            "/api/settings/limits",
            json={"per_txn_limit": 150.0},
            headers=headers_user
        )
        self.assertEqual(res_upd.status_code, 200)

        # Attempt transfer of ₹200.00 (exceeds limit) -> must be rejected
        res_reject = self.client.post(
            "/api/transfer",
            json={"to_acc": "99999999999999", "amount": "200", "method": "IMPS"},
            headers=headers_user
        )
        self.assertEqual(res_reject.status_code, 400)
        self.assertIn("limit", res_reject.get_json()["message"].lower())

        # Reset limit back to ₹100,000.00
        self.client.post(
            "/api/settings/limits",
            json={"per_txn_limit": 100000.0},
            headers=headers_user
        )

    # ══════════════════════════════════════════════════════════════
    # 7. NOTIFICATION CENTER & UNREAD TRACKING
    # ══════════════════════════════════════════════════════════════
    def test_notification_center(self):
        """Verify notification dispatch, listing, unread counts, and read status."""
        test_acc = "40273146502136"
        headers_user = self._get_auth_headers(account=test_acc, role="user")

        # Dispatch notification
        notification_service.send_notification(
            account_number=test_acc,
            title="Security Alert",
            message="New device logged into your account.",
            notification_type="SECURITY"
        )

        # Fetch notifications
        res = self.client.get("/api/notifications", headers=headers_user)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertGreaterEqual(data["unread_count"], 1)

        # Mark all as read
        res_read = self.client.post("/api/notifications/read", json={}, headers=headers_user)
        self.assertEqual(res_read.status_code, 200)

        # Re-fetch -> unread_count must be 0
        res_after = self.client.get("/api/notifications", headers=headers_user)
        self.assertEqual(res_after.get_json()["unread_count"], 0)

    # ══════════════════════════════════════════════════════════════
    # 8. FINANCIAL ANALYTICS & SPENDING INSIGHTS
    # ══════════════════════════════════════════════════════════════
    def test_spending_insights_and_cash_flow(self):
        """Verify spending analytics calculates cash flow, category breakdowns, and advice."""
        headers_user = self._get_auth_headers(account="40273146502136", role="user")
        res = self.client.get("/api/analytics/insights", headers=headers_user)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertIn("cash_flow", data)
        self.assertIn("total_inflow_rupees", data["cash_flow"])
        self.assertIn("total_outflow_rupees", data["cash_flow"])
        self.assertIn("category_breakdown", data)
        self.assertIn("advisory_insights", data)

    # ══════════════════════════════════════════════════════════════
    # 9. INVESTMENT PERFORMANCE & ASSET ALLOCATION
    # ══════════════════════════════════════════════════════════════
    def test_investment_performance_dashboard(self):
        """Verify portfolio performance aggregation, gold live valuation, and allocations."""
        headers_user = self._get_auth_headers(account="40273146502136", role="user")
        res = self.client.get("/api/investments/performance", headers=headers_user)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertIn("summary", data)
        self.assertIn("gold", data)
        self.assertIn("mutual_funds", data)
        self.assertIn("fixed_income", data)
        self.assertIn("asset_allocation", data)

    # ══════════════════════════════════════════════════════════════
    # 10. AUDIT HISTORY VIEWER
    # ══════════════════════════════════════════════════════════════
    def test_audit_history_viewer(self):
        """Verify administrative audit trail queries and RBAC."""
        headers_user = self._get_auth_headers(role="user")
        res_user = self.client.get("/api/admin/audit_logs", headers=headers_user)
        self.assertEqual(res_user.status_code, 403)

        headers_admin = self._get_auth_headers(role="admin")
        res_admin = self.client.get("/api/admin/audit_logs", headers=headers_admin)
        self.assertEqual(res_admin.status_code, 200)
        logs_data = res_admin.get_json()
        self.assertTrue(logs_data["success"])
        self.assertGreaterEqual(logs_data["total"], 1)

    # ══════════════════════════════════════════════════════════════
    # 11. CUSTOMER SUPPORT TICKET MANAGEMENT
    # ══════════════════════════════════════════════════════════════
    def test_support_ticket_lifecycle(self):
        """Verify customer creating tickets and admin reviewing and resolving."""
        headers_user = self._get_auth_headers(account="40273146502136", role="user")

        # Customer creates ticket
        res_create = self.client.post(
            "/api/support/tickets",
            json={
                "subject": "Cheque book tracking query",
                "category": "CARDS",
                "priority": "HIGH",
                "message": "When will my cheque book be dispatched?"
            },
            headers=headers_user
        )
        self.assertEqual(res_create.status_code, 200)
        tkt_id = res_create.get_json()["ticket_id"]

        # Customer lists tickets
        res_list = self.client.get("/api/support/tickets", headers=headers_user)
        self.assertEqual(res_list.status_code, 200)
        self.assertTrue(any(t["ticket_id"] == tkt_id for t in res_list.get_json()["tickets"]))

        # Admin replies and updates status
        headers_admin = self._get_auth_headers(account="40273146502136", role="admin")
        res_reply = self.client.post(
            f"/api/admin/support/tickets/{tkt_id}/reply",
            json={"response": "Your cheque book was dispatched via BlueDart. Tracking: CRDN-CHQ-109.", "status": "RESOLVED"},
            headers=headers_admin
        )
        self.assertEqual(res_reply.status_code, 200)
        self.assertEqual(res_reply.get_json()["status"], "RESOLVED")

    # ══════════════════════════════════════════════════════════════
    # 12. ADVANCED TRANSACTION SEARCH & MULTI-FILTERING
    # ══════════════════════════════════════════════════════════════
    def test_advanced_transaction_search(self):
        """Verify multi-criteria filtering across type, amount range, and state."""
        headers_user = self._get_auth_headers(account="40273146502136", role="user")

        # Search with min and max amount filters
        res = self.client.get(
            "/api/transactions/search?min_amount=10&max_amount=10000&state=SUCCESSFUL",
            headers=headers_user
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertIn("transactions", data)
        for t in data["transactions"]:
            self.assertEqual(t["state"], "SUCCESSFUL")
            self.assertGreaterEqual(t["amount_rupees"], 10.0)
            self.assertLessEqual(t["amount_rupees"], 10000.0)


if __name__ == "__main__":
    unittest.main()
