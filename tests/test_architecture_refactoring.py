"""
Credence Core — Phase 4: Architecture Refactoring Test Suite
Validates modular package layout, thin controllers, service/repository decoupling,
centralized validation, error handlers, OpenAPI documentation, and C++ harness decoupling.
"""

import unittest
import json
from decimal import Decimal
from flask import Flask

from backend.app import create_app
from backend.app.core.config import Config
from backend.app.core.database import get_db
from backend.app.schemas.validators import (
    validate_account_number,
    validate_amount,
    validate_pan,
    validate_upi_id,
    validate_pin,
    validate_password,
    ValidationError
)
from backend.app.repositories import (
    user_repository,
    account_repository,
    transaction_repository,
    investment_repository,
    card_repository,
    loan_repository
)
from backend.app.services.transfers import transfer_service
from backend.app.services.ledger import ledger_service
from backend.app.services.payments import payment_service
from backend.app.services.accounts import account_service
from backend.app.services.fraud import fraud_service
from backend.app.utils.currency import rupees_to_paise, paise_to_rupees, format_rupees
from backend.app.utils.cpp_bench import cpp_harness
import security


class CredenceArchitectureRefactoringTestSuite(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        cls.client = cls.app.test_client()

    def setUp(self):
        security.FAILED_ATTEMPTS_STORE.clear()

    def _get_auth_headers(self, account="40273146502136", role="user"):
        """Establish session and retrieve CSRF token."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = str(account)
            sess["role"] = role
            sess["auth_time"] = 9999999999.0
            sess["csrf_token"] = security.generate_csrf_token()
            token = sess["csrf_token"]
        return {"X-CSRF-Token": token}

    # ══════════════════════════════════════════════════════════════
    # 1. MODULAR PACKAGE & BLUEPRINT INITIALIZATION
    # ══════════════════════════════════════════════════════════════
    def test_modular_app_initialization_and_blueprints(self):
        """Verify create_app registers all required domain Blueprints."""
        self.assertIsInstance(self.app, Flask)
        expected_blueprints = [
            "auth_bp",
            "account_bp",
            "transfer_bp",
            "payment_bp",
            "card_bp",
            "investment_bp",
            "loan_bp",
            "upi_bp",
            "ledger_bp",
            "statement_bp",
            "settings_bp",
            "docs_bp",
            "frontend_bp"
        ]
        registered_bps = list(self.app.blueprints.keys())
        for bp in expected_blueprints:
            self.assertIn(bp, registered_bps, f"Blueprint {bp} was not registered!")

    # ══════════════════════════════════════════════════════════════
    # 2. OPENAPI 3.0 DOCUMENTATION & SPECIFICATION
    # ══════════════════════════════════════════════════════════════
    def test_openapi_specification_endpoint(self):
        """Verify /api/openapi.json returns valid OpenAPI 3.0 schema."""
        res = self.client.get("/api/openapi.json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.content_type, "application/json")
        data = res.get_json()
        self.assertTrue(data.get("openapi", "").startswith("3."))
        self.assertIn("info", data)
        self.assertEqual(data["info"]["title"], "Credence Core Banking API")
        self.assertIn("paths", data)
        self.assertIn("/api/login", data["paths"])
        self.assertIn("/api/transfer", data["paths"])
        self.assertIn("/api/deposit", data["paths"])
        self.assertIn("/api/pay_bill", data["paths"])
        self.assertIn("/api/ledger/reverse", data["paths"])

    def test_swagger_ui_documentation_endpoint(self):
        """Verify /api/docs serves the interactive Swagger UI interface."""
        res = self.client.get("/api/docs")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"swagger-ui", res.data)
        self.assertIn(b"/api/openapi.json", res.data)

    # ══════════════════════════════════════════════════════════════
    # 3. CENTRALIZED VALIDATION
    # ══════════════════════════════════════════════════════════════
    def test_centralized_validators(self):
        """Verify schemas.validators enforces strict financial and credential rules."""
        # Account number
        self.assertEqual(validate_account_number("40273146502136"), "40273146502136")
        with self.assertRaises(ValidationError):
            validate_account_number("invalid-acc")
        with self.assertRaises(ValidationError):
            validate_account_number("123")

        # Amount to paise
        self.assertEqual(rupees_to_paise(validate_amount("100.50")), 10050)
        self.assertEqual(rupees_to_paise(validate_amount(50)), 5000)
        with self.assertRaises(ValidationError):
            validate_amount("-10")
        with self.assertRaises(ValidationError):
            validate_amount("0")
        with self.assertRaises(ValidationError):
            validate_amount("abc")
        with self.assertRaises(ValidationError):
            validate_amount(float("inf"))

        # PAN
        self.assertEqual(validate_pan("abcde1234f"), "ABCDE1234F")
        with self.assertRaises(ValidationError):
            validate_pan("invalid-pan")

        # UPI ID
        self.assertEqual(validate_upi_id("john@credence"), "john@credence")
        with self.assertRaises(ValidationError):
            validate_upi_id("invalid-upi")

        # PIN
        self.assertEqual(validate_pin("1234"), "1234")
        self.assertEqual(validate_pin("123456", allow_6_digit=True), "123456")
        with self.assertRaises(ValidationError):
            validate_pin("12a4")
        with self.assertRaises(ValidationError):
            validate_pin("12")

    # ══════════════════════════════════════════════════════════════
    # 4. REPOSITORIES DATA ACCESS ENCAPSULATION
    # ══════════════════════════════════════════════════════════════
    def test_repository_encapsulation(self):
        """Verify repositories query domain entities without leaking SQL into controllers."""
        with get_db() as db:
            acc = account_repository.get_by_number(db, "40273146502136")
            self.assertIsNotNone(acc)
            self.assertEqual(acc.account_number, "40273146502136")

            # Balance record via repository
            bal = account_repository.get_balance_record(db, "40273146502136")
            self.assertIsNotNone(bal)
            self.assertGreaterEqual(bal.balance_paise, 0)

            # User repository
            user = user_repository.get_by_account_number(db, "40273146502136")
            self.assertIsNotNone(user)
            self.assertTrue(len(user.name) > 0)

    # ══════════════════════════════════════════════════════════════
    # 5. SERVICE LAYER ISOLATION & BUSINESS LOGIC
    # ══════════════════════════════════════════════════════════════
    def test_service_layer_financial_execution(self):
        """Verify service layer handles financial logic cleanly and idempotently."""
        import uuid
        idem_key = f"TEST-SVC-{uuid.uuid4().hex[:8]}"

        # Deposit via TransferService
        res = transfer_service.process_deposit(
            account_number="40273146502136",
            amount=50.0,
            actor="40273146502136",
            ip="127.0.0.1",
            idempotency_key=idem_key
        )
        self.assertTrue(res["success"])
        self.assertTrue(res["reference_id"].startswith("TXN-"))

        # Idempotent replay must return original result without double crediting
        replay_res = transfer_service.process_deposit(
            account_number="40273146502136",
            amount=50.0,
            actor="40273146502136",
            ip="127.0.0.1",
            idempotency_key=idem_key
        )
        self.assertTrue(replay_res["success"])
        self.assertEqual(replay_res["reference_id"], res["reference_id"])

    # ══════════════════════════════════════════════════════════════
    # 6. CENTRALIZED EXCEPTION HANDLING
    # ══════════════════════════════════════════════════════════════
    def test_centralized_error_handling(self):
        """Verify invalid API requests return uniform JSON format without stack traces."""
        headers = self._get_auth_headers()
        # Negative amount transfer
        res = self.client.post(
            "/api/transfer",
            json={"to_acc": "99999999999999", "amount": "-500"},
            headers=headers
        )
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data["success"])
        self.assertIn("message", data)
        self.assertNotIn("Traceback", res.get_data(as_text=True))

    # ══════════════════════════════════════════════════════════════
    # 7. C++ BENCHMARK HARNESS DECOUPLING
    # ══════════════════════════════════════════════════════════════
    def test_cpp_engine_benchmark_harness(self):
        """Verify C++ engine is isolated as an independent benchmark harness."""
        if cpp_harness.is_available:
            bench = cpp_harness.benchmark_throughput(iterations=3)
            self.assertTrue(bench["available"])
            self.assertEqual(bench["iterations"], 3)
            self.assertIn("transactions_per_second", bench)
            self.assertIn("avg_latency_ms", bench)
        else:
            self.assertFalse(cpp_harness.is_available)

    def test_privileged_api_execute_role_restriction(self):
        """Verify /api/execute is strictly guarded by admin role."""
        # User session (forbidden)
        headers_user = self._get_auth_headers(account="40273146502136", role="user")
        res_user = self.client.post("/api/execute", json={"choice": "99"}, headers=headers_user)
        self.assertEqual(res_user.status_code, 403)

        # Admin session (allowed)
        headers_admin = self._get_auth_headers(account="40273146502136", role="admin")
        res_admin = self.client.post("/api/execute", json={"choice": "99"}, headers=headers_admin)
        self.assertEqual(res_admin.status_code, 200)
        data = res_admin.get_json()
        self.assertTrue(data["success"])


if __name__ == "__main__":
    unittest.main()
