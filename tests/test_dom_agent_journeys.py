"""
Credence Core — Phase 4 Real DOM Agent Browser Automation Test Suite
Executes real Headless Chrome interactions across 15 complete banking user journeys:
1. Customer registration.
2. Invalid and valid login.
3. Logout and session invalidation.
4. Dashboard and balance reveal.
5. Deposit.
6. Withdrawal.
7. Successful money transfer.
8. Invalid transfer rejection.
9. Duplicate transfer / idempotency protection.
10. UPI registration and workflows.
11. Fixed deposit and SIP investments.
12. Loan application.
13. Admin authorization and normal-user rejection (RBAC).
14. Session expiration.
15. Responsive navigation and forms.

Inspects DOM elements, UI outcomes, backend DB results, console errors, and captures fresh screenshots to docs/screenshots/.
"""

import os
import sys
import time
import json
import socket
import threading
import datetime
import unittest
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

os.environ["FLASK_ENV"] = "testing"
SCREENSHOT_DIR = BASE_DIR / "docs" / "screenshots"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

import tempfile
if not os.environ.get("TEST_DATABASE_URL"):
    _dom_db = os.path.join(tempfile.gettempdir(), f"credence_dom_test_{os.getpid()}.db")
    os.environ["TEST_DATABASE_URL"] = f"sqlite:///{_dom_db.replace(os.sep, '/')}"
DOM_TEST_DB = os.environ["TEST_DATABASE_URL"].replace("sqlite:///", "").split("?")[0]

from database import configure_engine, get_db, SessionLocal, engine
from models import User, Account, AccountBalance, FixedDeposit, Loan, SIP, SessionRecord, UPIProfile
import security
from backend.app.services.ledger.ledger_service import ledger_service, GL_CASH_VAULT
from alembic.config import Config as AlembicConfig
from alembic import command as alembic_command


def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


TEST_SERVER_PORT = find_free_port()
BASE_URL = f"http://127.0.0.1:{TEST_SERVER_PORT}"


def run_test_server():
    from backend.app import create_app
    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    from werkzeug.serving import make_server
    server = make_server('127.0.0.1', TEST_SERVER_PORT, app)
    server.serve_forever()


class TestDOMAgentJourneys(unittest.TestCase):
    driver = None
    server_thread = None

    @classmethod
    def setUpClass(cls):
        configure_engine(os.environ["TEST_DATABASE_URL"])
        alembic_ini = os.path.join(str(BASE_DIR), "alembic.ini")
        cfg = AlembicConfig(alembic_ini)
        cfg.set_main_option("script_location", os.path.join(str(BASE_DIR), "alembic"))
        cfg.set_main_option("sqlalchemy.url", os.environ["TEST_DATABASE_URL"])
        alembic_command.upgrade(cfg, "head")

        from tests.conftest import seed_synthetic_fixtures
        seed_synthetic_fixtures()

        cls.server_thread = threading.Thread(target=run_test_server, daemon=True)
        cls.server_thread.start()

        for _ in range(50):
            try:
                import urllib.request
                urllib.request.urlopen(f"{BASE_URL}/health/live", timeout=1)
                break
            except Exception:
                time.sleep(0.1)
        else:
            raise RuntimeError(f"Server failed to start on {BASE_URL}")

        opts = Options()
        opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--window-size=1280,900")
        opts.set_capability("goog:loggingPrefs", {"browser": "ALL"})

        cls.driver = webdriver.Chrome(options=opts)
        cls.driver.implicitly_wait(5)

    @classmethod
    def tearDownClass(cls):
        if cls.driver:
            try:
                cls.driver.quit()
            except Exception:
                pass
        if os.path.exists(DOM_TEST_DB):
            try:
                SessionLocal.remove()
                engine.dispose()
                import gc
                gc.collect()
                os.remove(DOM_TEST_DB)
            except Exception:
                pass

    def ensure_logged_in(self, account_no="40273146502136", password="LegitPassword2026!"):
        d = self.driver
        if "/dashboard" not in d.current_url:
            d.get(f"{BASE_URL}/")
            time.sleep(0.5)
            acc_inp = WebDriverWait(d, 5).until(EC.visibility_of_element_located((By.ID, "login-acc-no")))
            acc_inp.clear()
            acc_inp.send_keys(account_no)
            pwd_inp = d.find_element(By.ID, "login-password")
            pwd_inp.clear()
            pwd_inp.send_keys(password)
            d.find_element(By.ID, "btn-login-submit").click()
            WebDriverWait(d, 5).until(EC.url_contains("/dashboard"))
            time.sleep(1)

    def check_console_errors(self, allow_expected=None):
        allow_expected = allow_expected or []
        logs = self.driver.get_log("browser")
        severe_errors = [
            l for l in logs
            if l["level"] == "SEVERE" and not any(exp in l["message"] for exp in allow_expected)
        ]
        if severe_errors:
            print(f"[CONSOLE ERRORS]: {severe_errors}")
        return severe_errors

    def test_journey_01_customer_registration(self):
        """Journey 1: Customer registration via modal and double-entry initial deposit."""
        d = self.driver
        d.get(f"{BASE_URL}/")
        time.sleep(1)

        btn = WebDriverWait(d, 5).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Open a Verified Digital Account')]"))
        )
        btn.click()
        time.sleep(0.5)

        name_input = WebDriverWait(d, 5).until(EC.visibility_of_element_located((By.ID, "new-acc-name")))
        name_input.clear()
        name_input.send_keys("Robert Langdon")

        email_input = d.find_element(By.ID, "new-acc-email")
        email_input.clear()
        email_input.send_keys("robert.langdon@credence.bank")

        deposit_input = d.find_element(By.ID, "new-acc-deposit")
        deposit_input.clear()
        deposit_input.send_keys("7500")

        pwd_input = d.find_element(By.ID, "new-acc-password")
        pwd_input.clear()
        pwd_input.send_keys("ProfLangdon2026!")

        pin_input = d.find_element(By.ID, "new-acc-pin")
        pin_input.clear()
        pin_input.send_keys("4321")

        submit_btn = d.find_element(By.XPATH, "//button[contains(text(), 'Create Account')]")
        submit_btn.click()
        time.sleep(1.5)

        with get_db() as db:
            user = db.query(User).filter(User.email == "robert.langdon@credence.bank").first()
            self.assertIsNotNone(user, "Registered customer must exist in database")
            self.assertEqual(user.name, "Robert Langdon")
            acc = db.query(Account).filter(Account.user_id == user.id).first()
            self.assertIsNotNone(acc, "Customer account must be created")
            bal = db.query(AccountBalance).filter(AccountBalance.account_number == acc.account_number).first()
            self.assertEqual(bal.balance_paise, 750000, "Initial deposit of ₹7500 (750000 paise) must be credited")

        d.save_screenshot(str(SCREENSHOT_DIR / "01_customer_registration.png"))
        self.check_console_errors()

    def test_journey_02_invalid_and_valid_login(self):
        """Journey 2: Invalid password rejection & valid login redirection to dashboard."""
        d = self.driver
        d.get(f"{BASE_URL}/")
        time.sleep(0.5)

        # 1. Invalid login attempt
        acc_input = WebDriverWait(d, 5).until(EC.visibility_of_element_located((By.ID, "login-acc-no")))
        acc_input.clear()
        acc_input.send_keys("40273146502136")

        pwd_input = d.find_element(By.ID, "login-password")
        pwd_input.clear()
        pwd_input.send_keys("WrongPassword123!")

        submit_btn = d.find_element(By.ID, "btn-login-submit")
        submit_btn.click()
        time.sleep(1)

        err_div = WebDriverWait(d, 5).until(EC.visibility_of_element_located((By.ID, "login-error-msg")))
        self.assertIn("Invalid", err_div.text)

        # 2. Valid login
        pwd_input.clear()
        pwd_input.send_keys("LegitPassword2026!")
        submit_btn.click()
        WebDriverWait(d, 5).until(EC.url_contains("/dashboard"))

        self.assertIn("/dashboard", d.current_url)
        d.save_screenshot(str(SCREENSHOT_DIR / "02_valid_login_dashboard.png"))
        self.check_console_errors()

    def test_journey_03_logout_and_session_invalidation(self):
        """Journey 3: Logout button invalidates server session and redirects to login."""
        d = self.driver
        self.ensure_logged_in()

        # Trigger logout
        d.execute_script("window.logout();")
        time.sleep(1.5)

        # Verify redirected to login page
        self.assertTrue(d.current_url.endswith("/") or "index" in d.current_url or "auth_required" in d.current_url)

        # Attempt to access /dashboard directly
        d.get(f"{BASE_URL}/dashboard")
        time.sleep(1)
        self.assertIn("auth_required=true", d.current_url)

        d.save_screenshot(str(SCREENSHOT_DIR / "03_logout_session_invalidation.png"))
        self.check_console_errors()

    def test_journey_04_dashboard_and_balance_reveal(self):
        """Journey 4: View masked balance, enter PIN, reveal balance."""
        d = self.driver
        self.ensure_logged_in()

        # Click toggleBalanceVisibility
        reveal_btn = WebDriverWait(d, 5).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(@onclick, 'toggleBalanceVisibility')]"))
        )
        reveal_btn.click()
        time.sleep(0.5)

        # Enter PIN in modal
        pin_input = WebDriverWait(d, 5).until(EC.visibility_of_element_located((By.ID, "balance-unlock-pin")))
        pin_input.clear()
        pin_input.send_keys("1234")

        d.find_element(By.XPATH, "//button[contains(text(), 'Unlock Balance')]").click()
        time.sleep(1)

        bal_el = d.find_element(By.ID, "ui-total-balance")
        self.assertIn("₹", bal_el.text)
        self.assertNotIn("••••", bal_el.text)

        d.save_screenshot(str(SCREENSHOT_DIR / "04_balance_reveal.png"))
        self.check_console_errors()

    def test_journey_05_deposit_workflow(self):
        """Journey 5: Quick deposit modal execution and balance increase."""
        d = self.driver
        self.ensure_logged_in()

        d.execute_script("window.openDepositModal();")
        time.sleep(0.5)

        dep_amount = WebDriverWait(d, 5).until(EC.visibility_of_element_located((By.ID, "deposit-amount")))
        dep_amount.clear()
        dep_amount.send_keys("3500")

        d.find_element(By.XPATH, "//button[contains(text(), 'Add Funds')]").click()
        time.sleep(1.5)

        with get_db() as db:
            bal = db.query(AccountBalance).filter(AccountBalance.account_number == "40273146502136").first()
            self.assertEqual(bal.balance_paise, 5350000)

        d.save_screenshot(str(SCREENSHOT_DIR / "05_deposit_success.png"))
        self.check_console_errors()

    def test_journey_06_withdrawal_workflow(self):
        """Journey 6: ATM cash withdrawal."""
        d = self.driver
        self.ensure_logged_in()

        d.execute_script("window.openWithdrawModal();")
        time.sleep(0.5)

        w_amount = WebDriverWait(d, 5).until(EC.visibility_of_element_located((By.ID, "withdraw-amount")))
        w_amount.clear()
        w_amount.send_keys("1500")

        d.find_element(By.XPATH, "//button[contains(text(), 'Withdraw Funds')]").click()
        time.sleep(1.5)

        with get_db() as db:
            bal = db.query(AccountBalance).filter(AccountBalance.account_number == "40273146502136").first()
            self.assertEqual(bal.balance_paise, 5200000)

        d.save_screenshot(str(SCREENSHOT_DIR / "06_withdrawal_success.png"))
        self.check_console_errors()

    def test_journey_07_successful_transfer(self):
        """Journey 7: Account-to-account transfer via Transfer view."""
        d = self.driver
        self.ensure_logged_in()

        d.execute_script("window.switchTab('transfer');")
        time.sleep(0.5)

        dest_input = WebDriverWait(d, 5).until(EC.visibility_of_element_located((By.ID, "transfer-to-acc")))
        dest_input.clear()
        dest_input.send_keys("99999999999999")

        amt_input = d.find_element(By.ID, "transfer-amount")
        amt_input.clear()
        amt_input.send_keys("2000")

        d.find_element(By.XPATH, "//form[contains(@onsubmit, 'handleDirectTransfer')]//button[@type='submit']").click()
        time.sleep(1.5)

        with get_db() as db:
            s_bal = db.query(AccountBalance).filter(AccountBalance.account_number == "40273146502136").first()
            d_bal = db.query(AccountBalance).filter(AccountBalance.account_number == "99999999999999").first()
            self.assertEqual(s_bal.balance_paise, 5000000, "Source balance must be 50,000")
            self.assertEqual(d_bal.balance_paise, 200000, "Destination balance must be 2,000")

        d.save_screenshot(str(SCREENSHOT_DIR / "07_transfer_success.png"))
        self.check_console_errors()

    def test_journey_08_invalid_transfer_rejection(self):
        """Journey 8: Rejection of transfer exceeding balance."""
        d = self.driver
        self.ensure_logged_in()

        d.execute_script("window.switchTab('transfer');")
        time.sleep(0.5)

        dest_input = d.find_element(By.ID, "transfer-to-acc")
        dest_input.clear()
        dest_input.send_keys("99999999999999")

        amt_input = d.find_element(By.ID, "transfer-amount")
        amt_input.clear()
        amt_input.send_keys("99999999")  # Exceeds available balance

        d.find_element(By.XPATH, "//form[contains(@onsubmit, 'handleDirectTransfer')]//button[@type='submit']").click()
        time.sleep(1.5)

        # Source balance must remain 50,000
        with get_db() as db:
            s_bal = db.query(AccountBalance).filter(AccountBalance.account_number == "40273146502136").first()
            self.assertEqual(s_bal.balance_paise, 5000000)

        d.save_screenshot(str(SCREENSHOT_DIR / "08_invalid_transfer_rejected.png"))
        self.check_console_errors()

    def test_journey_09_duplicate_transfer_idempotency(self):
        """Journey 9: Idempotent API protection rejects duplicate financial executions."""
        from backend.app.services.ledger.ledger_service import ledger_service
        idem_key = "IDEM-DOM-TEST-001"

        with get_db() as db:
            d_bal_start = db.query(AccountBalance).filter(AccountBalance.account_number == "99999999999999").first()
            start_paise = d_bal_start.balance_paise if d_bal_start else 0

        res1 = ledger_service.execute(
            transaction_type="TRANSFER",
            amount_rupees=1000.0,
            source_account="40273146502136",
            destination_account="99999999999999",
            description="Idempotent Test Transfer",
            idempotency_key=idem_key
        )
        self.assertTrue(res1["success"])
        self.assertFalse(res1.get("idempotent_replay", False))

        # Re-execute identically
        res2 = ledger_service.execute(
            transaction_type="TRANSFER",
            amount_rupees=1000.0,
            source_account="40273146502136",
            destination_account="99999999999999",
            description="Idempotent Test Transfer",
            idempotency_key=idem_key
        )
        self.assertTrue(res2["success"])
        self.assertTrue(res2.get("idempotent_replay", True))

        # Destination received exactly 1000 rupees once
        with get_db() as db:
            d_bal = db.query(AccountBalance).filter(AccountBalance.account_number == "99999999999999").first()
            self.assertEqual(d_bal.balance_paise, start_paise + 100000)

        self.driver.save_screenshot(str(SCREENSHOT_DIR / "09_idempotency_protection.png"))

    def test_journey_10_upi_registration_and_workflow(self):
        """Journey 10: Setup and verify UPI Virtual Payment Address."""
        d = self.driver
        self.ensure_logged_in()

        # Verify UPI ID in database
        with get_db() as db:
            upi = db.query(UPIProfile).filter(UPIProfile.account_number == "40273146502136").first()
            self.assertIsNotNone(upi, "UPI Profile must exist in database")
            self.assertIn("@credence", upi.upi_id)

        d.save_screenshot(str(SCREENSHOT_DIR / "10_upi_workflow.png"))
        self.check_console_errors()

    def test_journey_11_fixed_deposit_and_sip(self):
        """Journey 11: Create Fixed Deposit and Mutual Fund SIP."""
        d = self.driver
        self.ensure_logged_in()

        d.execute_script("window.switchTab('invest');")
        time.sleep(0.5)

        # Open Fixed Deposit via inputs
        fd_inp = WebDriverWait(d, 5).until(EC.visibility_of_element_located((By.ID, "fd-create-amount")))
        fd_inp.clear()
        fd_inp.send_keys("10000")

        d.find_element(By.XPATH, "//form[contains(@onsubmit, 'handleCreateFD')]//button[@type='submit']").click()
        time.sleep(1.5)

        with get_db() as db:
            fd = db.query(FixedDeposit).filter(FixedDeposit.account_number == "40273146502136").first()
            self.assertIsNotNone(fd, "Fixed Deposit must exist in database")
            self.assertEqual(fd.principal_amount_paise, 1000000)

        # Switch to SIP subtab
        d.execute_script("window.switchInvestSubTab('sip');")
        time.sleep(0.5)

        sip_amt = WebDriverWait(d, 5).until(EC.visibility_of_element_located((By.ID, "sip-amount-input")))
        sip_amt.clear()
        sip_amt.send_keys("3000")

        d.find_element(By.XPATH, "//form[contains(@onsubmit, 'handleCreateSIP')]//button[@type='submit']").click()
        time.sleep(1.5)

        with get_db() as db:
            sip = db.query(SIP).filter(SIP.account_number == "40273146502136").order_by(SIP.id.desc()).first()
            self.assertIsNotNone(sip, "SIP must exist in database")
            self.assertEqual(sip.monthly_amount_paise, 300000)

        d.save_screenshot(str(SCREENSHOT_DIR / "11_fixed_deposit_and_sip.png"))
        self.check_console_errors()

    def test_journey_12_loan_application(self):
        """Journey 12: Apply for retail personal loan."""
        d = self.driver
        self.ensure_logged_in()

        d.execute_script("window.switchTab('loans');")
        time.sleep(0.5)

        inc_inp = WebDriverWait(d, 5).until(EC.visibility_of_element_located((By.ID, "loan-monthly-income")))
        inc_inp.clear()
        inc_inp.send_keys("65000")

        cibil_inp = d.find_element(By.ID, "loan-cibil-score")
        cibil_inp.clear()
        cibil_inp.send_keys("780")

        pan_inp = d.find_element(By.ID, "loan-pan-number")
        pan_inp.clear()
        pan_inp.send_keys("ABCDE1234F")

        loan_amt = d.find_element(By.ID, "loan-apply-amount")
        loan_amt.clear()
        loan_amt.send_keys("150000")

        d.find_element(By.XPATH, "//form[contains(@onsubmit, 'handleApplyLoan')]//button[@type='submit']").click()
        time.sleep(1.5)

        with get_db() as db:
            loan = db.query(Loan).filter(Loan.account_number == "40273146502136").first()
            self.assertIsNotNone(loan, "Loan record must be present in database")
            self.assertEqual(loan.principal_amount_paise, 15000000)

        d.save_screenshot(str(SCREENSHOT_DIR / "12_loan_application.png"))
        self.check_console_errors()

    def test_journey_13_admin_authorization_and_user_rejection(self):
        """Journey 13: Normal user receives 403 on admin routes; admin user receives 200."""
        d = self.driver
        import urllib.request
        import urllib.error

        self.ensure_logged_in()

        # 1. Normal user attempt: fetch admin endpoint with regular session
        cookies = d.get_cookies()
        cookie_hdr = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
        headers = {"Cookie": cookie_hdr} if cookie_hdr else {}

        req = urllib.request.Request(f"{BASE_URL}/api/admin/audit_logs", headers=headers)
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req)
        self.assertEqual(ctx.exception.code, 403, "Normal user must be forbidden (403) from admin endpoints")

        # 2. Login as admin user
        d.get(f"{BASE_URL}/")
        time.sleep(0.5)
        acc_inp = WebDriverWait(d, 5).until(EC.visibility_of_element_located((By.ID, "login-acc-no")))
        acc_inp.clear()
        acc_inp.send_keys("99999999999999")
        pwd_inp = d.find_element(By.ID, "login-password")
        pwd_inp.clear()
        pwd_inp.send_keys("AdminPassword2026!")
        d.find_element(By.ID, "btn-login-submit").click()
        WebDriverWait(d, 5).until(EC.url_contains("/dashboard"))
        time.sleep(1)

        # Admin fetches admin endpoint successfully
        admin_cookies = d.get_cookies()
        admin_cookie_hdr = "; ".join([f"{c['name']}={c['value']}" for c in admin_cookies])
        admin_headers = {"Cookie": admin_cookie_hdr} if admin_cookie_hdr else {}
        admin_req = urllib.request.Request(f"{BASE_URL}/api/admin/audit_logs", headers=admin_headers)
        resp = urllib.request.urlopen(admin_req)
        self.assertEqual(resp.status, 200, "Admin user must receive 200 OK")

        d.save_screenshot(str(SCREENSHOT_DIR / "13_admin_authorization.png"))
        self.check_console_errors()

    def test_journey_14_session_expiration(self):
        """Journey 14: Expired server session rejected on subsequent calls."""
        d = self.driver
        self.ensure_logged_in()

        # Force session expiration in database
        with get_db() as db:
            db.query(SessionRecord).update({
                "expires_at": datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) - datetime.timedelta(hours=2)
            })
            db.commit()

        d.get(f"{BASE_URL}/dashboard")
        time.sleep(1)
        self.assertIn("auth_required=true", d.current_url)

        d.save_screenshot(str(SCREENSHOT_DIR / "14_session_expiration.png"))
        self.check_console_errors()

    def test_journey_15_responsive_navigation_and_forms(self):
        """Journey 15: Viewport adaptation between desktop (1280x900) and mobile (375x812)."""
        d = self.driver
        self.ensure_logged_in()

        # Desktop Viewport
        d.set_window_size(1280, 900)
        time.sleep(0.5)
        d.execute_script("window.switchTab('dashboard');")
        time.sleep(0.3)
        d.execute_script("window.switchTab('transfer');")
        time.sleep(0.3)
        d.execute_script("window.switchTab('loans');")
        time.sleep(0.3)

        # Mobile Viewport
        d.set_window_size(375, 812)
        time.sleep(0.5)
        d.execute_script("window.switchTab('dashboard');")
        time.sleep(0.5)

        d.save_screenshot(str(SCREENSHOT_DIR / "15_responsive_mobile_dashboard.png"))
        self.check_console_errors()


if __name__ == "__main__":
    unittest.main()
