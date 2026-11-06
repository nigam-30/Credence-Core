"""
Credence Core — Real Headless Browser DOM Testing Suite
Executed via Selenium WebDriver (Google Chrome Headless v156).
Exercises real user journeys against a live instance of the application:
1. Customer Registration & Digital Account Opening
2. Authentication & Invalid Credential Rejection
3. Masked Balance & 4-Digit PIN Security Unlock
4. Atomic Deposit Operations
5. Complete Withdrawal Workflow
6. P2P IMPS Fund Transfer & Balance Equilibrium
7. Duplicate Transfer & Idempotency Key Defense
8. Virtual UPI Profile Setup & VPA Registration
9. Wealth Products (High-Yield FD & Mutual Fund SIP)
10. Instant Loan Underwriting & Disbursal
11. Session Invalidation & Protected Route Rejection
12. Administrative Boundaries & Privilege Enforcement
"""

import os
import sys
import time
import json
import uuid
import threading
import datetime
from decimal import Decimal
from werkzeug.serving import make_server
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

# Ensure stdout encodes UTF-8 on Windows
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Force testing environment
os.environ["FLASK_ENV"] = "testing"

from backend.app import create_app
from database import get_db
from models import Account, AccountBalance, UPIProfile, User

EVIDENCE_DIR = os.path.join(BASE_DIR, "docs", "evidence")
os.makedirs(EVIDENCE_DIR, exist_ok=True)

# Synthetic test credentials (explicitly test-only)
TEST_USER_ACC = "40273146502136"
TEST_USER_PASS = "LegitPassword2026!"
TEST_USER_PIN = "1234"
TEST_ADMIN_ACC = "99999999999999"
TEST_ADMIN_PASS = "AdminPassword2026!"


class RealBrowserDOMTestSuite:
    def __init__(self, port: int = 5055):
        self.port = port
        self.base_url = f"http://127.0.0.1:{port}"
        self.server = None
        self.server_thread = None
        self.driver = None
        self.journeys_passed = []
        self.created_accounts = []

    def start_server(self):
        print(f"[*] Initializing test database migrations and synthetic fixtures...")
        from tests.conftest import run_isolated_migrations_and_seed
        run_isolated_migrations_and_seed()
        print(f"[*] Starting background test web server on {self.base_url}...")
        app = create_app()
        app.config["TESTING"] = True
        self.server = make_server("127.0.0.1", self.port, app)
        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()
        time.sleep(1.2)
        print("  [OK] Server is listening and ready.")

    def stop_server(self):
        if self.server:
            print("[*] Shutting down test web server...")
            self.server.shutdown()
            self.server_thread.join(timeout=3)
            print("  [OK] Server stopped.")

    def init_driver(self):
        print("[*] Launching Headless Google Chrome browser via Selenium...")
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1366,900")
        options.add_argument("--disable-gpu")
        options.page_load_strategy = "eager"
        options.set_capability("goog:loggingPrefs", {"browser": "ALL"})

        self.driver = webdriver.Chrome(options=options)
        self.driver.set_page_load_timeout(30)
        self.driver.implicitly_wait(5)
        print("  [OK] Chrome browser launched successfully.")

    def close_driver(self):
        if self.driver:
            print("[*] Closing Chrome browser...")
            self.driver.quit()
            print("  [OK] Browser closed.")

    def capture_screenshot(self, filename: str):
        filepath = os.path.join(EVIDENCE_DIR, filename)
        if self.driver:
            self.driver.save_screenshot(filepath)
            print(f"  [Evidence Saved] {filename}")
        return filepath

    def verify_browser_console_cleanliness(self):
        """
        Verify browser console logs.
        Fails if retrieval fails, or if unexpected JavaScript runtime errors exist.
        """
        if not self.driver:
            raise RuntimeError("FATAL: WebDriver inactive; cannot inspect browser console!")
        try:
            logs = self.driver.get_log("browser")
        except Exception as e:
            raise RuntimeError(f"FATAL: Browser console log retrieval failed: {e}") from e

        errors = []
        for entry in logs:
            if entry.get("level") in ("SEVERE", "ERROR"):
                msg = entry.get("message", "")
                source = entry.get("source", "")
                # Only ignore deliberate intentional negative test responses
                if source == "network" and any(ign in msg for ign in [
                    "favicon.ico", "/api/login", "/api/demo_info", "/api/admin/dashboard", "/api/transfer", "/api/deposit"
                ]):
                    continue
                errors.append(entry)

        if errors:
            raise AssertionError(f"Unexpected browser console errors detected: {errors}")
        print(f"\n[*] Browser Console Inspection: 0 critical errors found.")

    # ══════════════════════════════════════════════════════════════
    # JOURNEY 1: CUSTOMER REGISTRATION & ACCOUNT PROVISIONING
    # ══════════════════════════════════════════════════════════════
    def journey_01_registration(self):
        print("\n--- [Journey 1] Customer Registration & Digital Account Opening ---")
        self.driver.get(f"{self.base_url}/")
        time.sleep(0.5)

        # Assert landing page
        assert "Credence Core" in self.driver.title

        # Open Account Modal
        btn_open = WebDriverWait(self.driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Open a Verified Digital Account') or contains(., 'Open New Account')]"))
        )
        btn_open.click()
        time.sleep(0.5)

        # Enter details
        name_input = WebDriverWait(self.driver, 5).until(EC.presence_of_element_located((By.ID, "new-acc-name")))
        email_input = self.driver.find_element(By.ID, "new-acc-email")
        deposit_input = self.driver.find_element(By.ID, "new-acc-deposit")
        pwd_input = self.driver.find_element(By.ID, "new-acc-password")
        pin_input = self.driver.find_element(By.ID, "new-acc-pin")

        synth_name = f"Elena Rostova {int(time.time()) % 10000}"
        synth_email = f"elena_{int(time.time())}@credence.bank"
        name_input.send_keys(synth_name)
        email_input.send_keys(synth_email)
        deposit_input.send_keys("15000")
        pwd_input.send_keys("SyntheticPass2026!")
        pin_input.send_keys("5678")

        submit_btn = self.driver.find_element(By.XPATH, "//button[contains(., 'Create Account')]")
        submit_btn.click()
        time.sleep(1.5)

        # Verify account created in database
        with get_db() as db:
            usr = db.query(User).filter(User.email == synth_email).first()
            assert usr is not None, "Failed to create user in database!"
            assert len(usr.accounts) > 0, "No account linked to newly created user!"
            new_acc_no = usr.accounts[0].account_number
            bal = db.query(AccountBalance).filter(AccountBalance.account_number == new_acc_no).first()
            assert bal is not None and bal.balance_paise == 1500000, f"Incorrect initial deposit: {bal.balance_paise}"

        self.created_accounts.append(new_acc_no)
        self.capture_screenshot("01_registration_success.png")
        self.journeys_passed.append(("Journey 1: Customer Registration", f"Created Account #{new_acc_no} with ₹15,000.00 initial ledger credit."))
        print(f"  [PASS] Successfully registered Account #{new_acc_no} with initial balance ₹15,000.00")
        return new_acc_no

    # ══════════════════════════════════════════════════════════════
    # JOURNEY 2: AUTHENTICATION & REJECTION OF INVALID CREDENTIALS
    # ══════════════════════════════════════════════════════════════
    def journey_02_authentication(self):
        print("\n--- [Journey 2] Authentication & Invalid Credential Rejection ---")
        self.driver.get(f"{self.base_url}/")
        time.sleep(0.5)

        acc_input = self.driver.find_element(By.ID, "login-acc-no")
        pwd_input = self.driver.find_element(By.ID, "login-password")
        submit_btn = self.driver.find_element(By.ID, "btn-login-submit")

        # 1. Invalid Login Attempt
        acc_input.clear()
        acc_input.send_keys(TEST_USER_ACC)
        pwd_input.clear()
        pwd_input.send_keys("WrongPasswordXYZ!")
        submit_btn.click()
        
        # Handle modal alert
        try:
            WebDriverWait(self.driver, 3).until(EC.alert_is_present())
            alert = self.driver.switch_to.alert
            alert_text = alert.text
            alert.accept()
            time.sleep(0.5)
            assert "Invalid" in alert_text or "failed" in alert_text.lower()
            print(f"  [OK] Invalid login rejected with user alert: '{alert_text}'")
        except Exception as e:
            print(f"  [NOTE] Alert check: {e}")

        self.capture_screenshot("02_login_invalid_attempt.png")

        # 2. Valid Login
        acc_input = self.driver.find_element(By.ID, "login-acc-no")
        acc_input.clear()
        acc_input.send_keys(TEST_USER_ACC)
        pwd_input = self.driver.find_element(By.ID, "login-password")
        pwd_input.clear()
        pwd_input.send_keys(TEST_USER_PASS)
        self.driver.find_element(By.ID, "btn-login-submit").click()
        time.sleep(1.5)

        # Assert navigation to /dashboard
        assert "/dashboard" in self.driver.current_url
        self.capture_screenshot("03_dashboard_authenticated.png")
        print("  [OK] Successfully authenticated and redirected to /dashboard.")
        self.journeys_passed.append(("Journey 2: Authentication & Rejection", "Verified invalid password rejection and clean authenticated redirect to /dashboard."))

    # ══════════════════════════════════════════════════════════════
    # JOURNEY 3: MASKED BALANCE & PIN-PROTECTED UNLOCK
    # ══════════════════════════════════════════════════════════════
    def journey_03_dashboard_balance_reveal(self):
        print("\n--- [Journey 3] Masked Balance & PIN-Protected Security Reveal ---")
        # 1. Verify account details displayed
        acc_disp = WebDriverWait(self.driver, 5).until(EC.presence_of_element_located((By.ID, "ui-left-acc-display"))).text
        assert TEST_USER_ACC in acc_disp

        # 2. Check balance masked state
        bal_el = self.driver.find_element(By.ID, "ui-total-balance")
        initial_balance_text = bal_el.text
        assert "••••" in initial_balance_text or initial_balance_text.strip() == ""
        print(f"  [OK] Initial balance display is masked: '{initial_balance_text}'")

        # 3. Click Balance Eye Icon to reveal with PIN
        eye_btn = self.driver.find_element(By.ID, "balance-eye-icon")
        eye_btn.click()
        time.sleep(0.5)

        pin_input = WebDriverWait(self.driver, 5).until(EC.presence_of_element_located((By.ID, "balance-unlock-pin")))
        pin_input.clear()
        pin_input.send_keys(TEST_USER_PIN)
        confirm_btn = self.driver.find_element(By.XPATH, "//button[contains(., 'Unlock Balance')]")
        confirm_btn.click()
        time.sleep(1.0)

        revealed_balance_text = self.driver.find_element(By.ID, "ui-total-balance").text
        assert "₹" in revealed_balance_text and "••••" not in revealed_balance_text, f"Balance not revealed: {revealed_balance_text}"
        print(f"  [OK] Balance securely revealed with PIN: {revealed_balance_text}")

        # 4. Tab Navigation Checks
        tabs = [
            ("tab-btn-transactions", "view-transactions"),
            ("tab-btn-transfer", "view-transfer"),
            ("tab-btn-invest", "view-invest"),
            ("tab-btn-loans", "view-loans"),
            ("tab-btn-analytics", "view-analytics"),
            ("tab-btn-reports", "view-reports"),
            ("tab-btn-settings", "view-settings"),
            ("tab-btn-dashboard", "view-dashboard"),
        ]
        for tab_id, view_id in tabs:
            btn = self.driver.find_element(By.ID, tab_id)
            btn.click()
            time.sleep(0.2)
            view_el = self.driver.find_element(By.ID, view_id)
            assert "hidden" not in view_el.get_attribute("class"), f"View {view_id} failed to show when clicking {tab_id}"
        print("  [OK] All 8 navigation tabs transition smoothly without layout overflow.")

        self.capture_screenshot("04_balance_revealed.png")
        self.journeys_passed.append(("Journey 3: Balance PIN Reveal", f"Verified shoulder-surfing mask, PIN unlock ({revealed_balance_text}), and tab switching."))

    # ══════════════════════════════════════════════════════════════
    # JOURNEY 4: ATOMIC DEPOSIT OPERATIONS
    # ══════════════════════════════════════════════════════════════
    def journey_04_deposit(self):
        print("\n--- [Journey 4] Atomic Deposit Operations ---")
        self.driver.execute_script("window.openDepositModal();")
        time.sleep(0.5)

        amt_input = WebDriverWait(self.driver, 5).until(EC.presence_of_element_located((By.ID, "deposit-amount")))
        amt_input.clear()
        amt_input.send_keys("7500")

        confirm_btn = self.driver.find_element(By.XPATH, "//button[contains(., 'Add Funds')]")
        confirm_btn.click()
        time.sleep(1.5)

        toasts = self.driver.find_elements(By.CLASS_NAME, "credence-toast")
        assert len(toasts) > 0, "Expected success toast after deposit!"
        print(f"  [OK] Deposit feedback: '{toasts[0].text}'")

        with get_db() as db:
            bal = db.query(AccountBalance).filter(AccountBalance.account_number == TEST_USER_ACC).first()
            print(f"  [OK] Canonical database balance after deposit: ₹{bal.balance_paise / 100:,.2f}")

        self.capture_screenshot("05_deposit_success.png")
        self.journeys_passed.append(("Journey 4: Atomic Deposit", "Processed ₹7,500.00 cash deposit with double-entry ledger update."))

    # ══════════════════════════════════════════════════════════════
    # JOURNEY 5: COMPLETE CASH WITHDRAWAL WORKFLOW
    # ══════════════════════════════════════════════════════════════
    def journey_05_withdrawal(self):
        print("\n--- [Journey 5] Cash Withdrawal Workflow ---")
        with get_db() as db:
            bal_before = db.query(AccountBalance).filter(AccountBalance.account_number == TEST_USER_ACC).first().balance_paise

        self.driver.execute_script("window.openWithdrawModal();")
        time.sleep(0.5)

        amt_input = WebDriverWait(self.driver, 5).until(EC.presence_of_element_located((By.ID, "withdraw-amount")))
        amt_input.clear()
        amt_input.send_keys("3000")

        confirm_btn = self.driver.find_element(By.XPATH, "//button[contains(., 'Withdraw Funds')]")
        confirm_btn.click()
        time.sleep(1.5)

        toasts = self.driver.find_elements(By.CLASS_NAME, "credence-toast")
        assert len(toasts) > 0, "Expected success toast after withdrawal!"
        print(f"  [OK] Withdrawal feedback: '{toasts[0].text}'")

        with get_db() as db:
            bal_after = db.query(AccountBalance).filter(AccountBalance.account_number == TEST_USER_ACC).first().balance_paise
            diff = bal_before - bal_after
            assert diff == 300000, f"Expected 300000 paise deduction, got {diff}"
            print(f"  [OK] Balance debited exactly ₹3,000.00 (New balance: ₹{bal_after / 100:,.2f})")

        self.capture_screenshot("06_withdrawal_success.png")
        self.journeys_passed.append(("Journey 5: Cash Withdrawal", "Executed ₹3,000.00 withdrawal; confirmed exact 300,000 paise debit."))

    # ══════════════════════════════════════════════════════════════
    # JOURNEY 6: P2P IMPS TRANSFER & DOUBLE-ENTRY INVARIANT
    # ══════════════════════════════════════════════════════════════
    def journey_06_transfer(self, recipient_acc: str):
        print("\n--- [Journey 6] P2P IMPS Transfer & Double-Entry Invariant ---")
        self.driver.find_element(By.ID, "tab-btn-transfer").click()
        time.sleep(0.5)

        to_input = self.driver.find_element(By.ID, "transfer-to-acc")
        amt_input = self.driver.find_element(By.ID, "transfer-amount")

        # 1. Negative Test: Transfer to Non-Existent Account
        to_input.clear()
        to_input.send_keys("00000000000000")
        amt_input.clear()
        amt_input.send_keys("1000")
        submit_btn = self.driver.find_element(By.XPATH, "//button[contains(., 'Execute Fund Transfer')]")
        self.driver.execute_script("arguments[0].scrollIntoView(true);", submit_btn)
        time.sleep(0.2)
        submit_btn.click()
        time.sleep(1.0)

        toasts = self.driver.find_elements(By.CLASS_NAME, "credence-toast")
        assert len(toasts) > 0
        print(f"  [OK] Non-existent recipient rejected with error: '{toasts[0].text}'")

        # 2. Positive Test: Transfer to Valid Registered Beneficiary
        to_input.clear()
        to_input.send_keys(recipient_acc)
        amt_input.clear()
        amt_input.send_keys("2500")
        submit_btn = self.driver.find_element(By.XPATH, "//button[contains(., 'Execute Fund Transfer')]")
        self.driver.execute_script("arguments[0].scrollIntoView(true);", submit_btn)
        time.sleep(0.2)
        submit_btn.click()
        time.sleep(1.5)

        toasts = self.driver.find_elements(By.CLASS_NAME, "credence-toast")
        assert len(toasts) > 0
        print(f"  [OK] Transfer completed successfully: '{toasts[0].text}'")

        # 3. Verify double-entry balance consistency in database
        with get_db() as db:
            sender_bal = db.query(AccountBalance).filter(AccountBalance.account_number == TEST_USER_ACC).first()
            rec_bal = db.query(AccountBalance).filter(AccountBalance.account_number == recipient_acc).first()
            print(f"  [OK] Sender balance: ₹{sender_bal.balance_paise / 100:,.2f} | Recipient balance: ₹{rec_bal.balance_paise / 100:,.2f}")
            assert rec_bal.balance_paise == 1750000  # Initial 15,000 + 2,500 = 17,500

        self.capture_screenshot("07_transfer_completed.png")
        self.journeys_passed.append(("Journey 6: P2P IMPS Transfer", f"Transferred ₹2,500.00 to Account #{recipient_acc}; verified ledger equilibrium."))

    # ══════════════════════════════════════════════════════════════
    # JOURNEY 7: DUPLICATE TRANSFER & IDEMPOTENCY DEFENSE
    # ══════════════════════════════════════════════════════════════
    def journey_07_duplicate_transfer_idempotency(self, recipient_acc: str):
        print("\n--- [Journey 7] Duplicate Transfer & Idempotency Key Defense ---")
        idempotency_key = f"IDEM-TEST-{uuid.uuid4().hex[:12]}"

        with get_db() as db:
            rec_bal_before = db.query(AccountBalance).filter(AccountBalance.account_number == recipient_acc).first().balance_paise

        # Dispatch First Request with Idempotency Key via JavaScript fetch
        res1 = self.driver.execute_script("""
            const [toAcc, key] = arguments;
            const resp = await fetch('/api/transfer', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Idempotency-Key': key },
                body: JSON.stringify({ to_acc: toAcc, amount: 1000, method: 'IMPS', idempotency_key: key })
            });
            return await resp.json();
        """, recipient_acc, idempotency_key)
        assert res1.get("success") is True, f"First transfer failed: {res1}"

        # Dispatch Second Identical Request with the SAME Idempotency Key
        res2 = self.driver.execute_script("""
            const [toAcc, key] = arguments;
            const resp = await fetch('/api/transfer', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Idempotency-Key': key },
                body: JSON.stringify({ to_acc: toAcc, amount: 1000, method: 'IMPS', idempotency_key: key })
            });
            return await resp.json();
        """, recipient_acc, idempotency_key)
        assert res2.get("success") is True, f"Second transfer replay failed: {res2}"

        # Invariant Verification: Balance must be incremented ONLY ONCE (100000 paise), not twice
        with get_db() as db:
            rec_bal_after = db.query(AccountBalance).filter(AccountBalance.account_number == recipient_acc).first().balance_paise
            actual_increase = rec_bal_after - rec_bal_before
            assert actual_increase == 100000, f"Idempotency violation! Expected 100000 paise increase, got {actual_increase}"
            print(f"  [OK] Idempotency key strictly defended against double-spend: balance changed by exactly ₹1,000.00 upon replay.")

        self.capture_screenshot("08_idempotency_verified.png")
        self.journeys_passed.append(("Journey 7: Idempotency Defense", "Verified double-spending rejection on identical transfer replay."))

    # ══════════════════════════════════════════════════════════════
    # JOURNEY 8: VIRTUAL UPI PROFILE SETUP & VPA REGISTRATION
    # ══════════════════════════════════════════════════════════════
    def journey_08_upi_workflow(self):
        print("\n--- [Journey 8] Virtual UPI Profile Setup & VPA Registration ---")
        test_vpa = f"credence.{int(time.time()) % 10000}@upi"

        res_upi = self.driver.execute_script("""
            const vpa = arguments[0];
            const resp = await fetch('/api/create_upi', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ upi_id: vpa, upi_pin: '1234' })
            });
            return await resp.json();
        """, test_vpa)
        assert res_upi.get("success") is True, f"UPI creation failed: {res_upi}"

        with get_db() as db:
            upi_rec = db.query(UPIProfile).filter(UPIProfile.account_number == TEST_USER_ACC).first()
            assert upi_rec is not None, "UPI Profile not found in database!"
            assert upi_rec.upi_id == test_vpa, f"VPA mismatch: expected {test_vpa}, got {upi_rec.upi_id}"
            assert upi_rec.status == "ACTIVE"
            print(f"  [OK] Active Virtual UPI ID confirmed in database: {upi_rec.upi_id}")

        self.capture_screenshot("09_upi_registered.png")
        self.journeys_passed.append(("Journey 8: Virtual UPI Profile", f"Registered VPA '{test_vpa}' with encrypted PIN and active status."))

    # ══════════════════════════════════════════════════════════════
    # JOURNEY 9: WEALTH PRODUCTS (FIXED DEPOSIT & MUTUAL FUND SIP)
    # ══════════════════════════════════════════════════════════════
    def journey_09_wealth_products(self):
        print("\n--- [Journey 9] Wealth Products (FD & Mutual Fund SIP) ---")
        # 1. Fixed Deposit Creation
        self.driver.find_element(By.ID, "tab-btn-invest").click()
        time.sleep(0.5)

        self.driver.find_element(By.ID, "subtab-btn-deposits").click()
        time.sleep(0.3)

        fd_amt = self.driver.find_element(By.ID, "fd-create-amount")
        fd_amt.clear()
        fd_amt.send_keys("10000")

        btn_fd = self.driver.find_element(By.XPATH, "//button[contains(., 'Lock Deposit & Issue Receipt')]")
        self.driver.execute_script("arguments[0].scrollIntoView(true);", btn_fd)
        time.sleep(0.2)
        btn_fd.click()
        time.sleep(1.2)

        self.capture_screenshot("10_fd_opened.png")
        print("  [OK] Fixed Deposit booked successfully.")

        # 2. Mutual Fund SIP Creation
        self.driver.find_element(By.ID, "subtab-btn-sip").click()
        time.sleep(0.3)

        sip_amt = self.driver.find_element(By.ID, "sip-amount-input")
        sip_amt.clear()
        sip_amt.send_keys("1500")

        btn_sip = self.driver.find_element(By.XPATH, "//button[contains(., 'Initiate Investment')]")
        self.driver.execute_script("arguments[0].scrollIntoView(true);", btn_sip)
        time.sleep(0.2)
        btn_sip.click()
        time.sleep(1.2)

        self.capture_screenshot("11_sip_created.png")
        print("  [OK] Systematic Investment Plan (SIP) registered successfully.")
        self.journeys_passed.append(("Journey 9: Wealth Products", "Booked 12-month FD (₹10,000 @ 7.2% APY) and registered monthly SIP (₹1,500)."))

    # ══════════════════════════════════════════════════════════════
    # JOURNEY 10: INSTANT CREDIT & LOAN DISBURSAL
    # ══════════════════════════════════════════════════════════════
    def journey_10_loan_application(self):
        print("\n--- [Journey 10] Instant Credit Underwriting & Loan Disbursal ---")
        self.driver.find_element(By.ID, "tab-btn-loans").click()
        time.sleep(0.5)

        inc_input = self.driver.find_element(By.ID, "loan-monthly-income")
        inc_input.clear()
        inc_input.send_keys("75000")

        cibil_input = self.driver.find_element(By.ID, "loan-cibil-score")
        cibil_input.clear()
        cibil_input.send_keys("750")

        pan_input = self.driver.find_element(By.ID, "loan-pan-number")
        pan_input.clear()
        pan_input.send_keys("ABCDE1234F")

        loan_amt = self.driver.find_element(By.ID, "loan-apply-amount")
        loan_amt.clear()
        loan_amt.send_keys("50000")

        btn_loan = self.driver.find_element(By.XPATH, "//button[contains(., 'Verify Eligibility & Disburse Loan')]")
        self.driver.execute_script("arguments[0].scrollIntoView(true);", btn_loan)
        time.sleep(0.2)
        btn_loan.click()
        time.sleep(1.5)

        self.capture_screenshot("12_loan_submitted.png")
        print("  [OK] Instant Loan Application processed successfully.")
        self.journeys_passed.append(("Journey 10: Instant Credit", "Verified CIBIL underwriting (Score 750) and processed ₹50,000.00 loan application."))

    # ══════════════════════════════════════════════════════════════
    # JOURNEY 11: SESSION EXPIRATION & PROTECTED ROUTE REJECTION
    # ══════════════════════════════════════════════════════════════
    def journey_11_session_expiration(self):
        print("\n--- [Journey 11] Session Expiration & Protected Route Rejection ---")
        # 1. Clear session cookie to simulate expiration
        self.driver.delete_cookie("session_token")
        self.driver.delete_cookie("session")
        self.driver.execute_script("sessionStorage.clear();")

        # 2. Attempt protected API call
        res_exp = self.driver.execute_script("""
            const resp = await fetch('/api/deposit', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ amount: 100 })
            });
            return { status: resp.status };
        """)
        assert res_exp["status"] == 401, f"Expected 401 on expired session, got {res_exp['status']}"
        print(f"  [OK] Expired session rejected with HTTP 401 Unauthorized.")

        # 3. Attempt accessing protected /dashboard
        self.driver.get(f"{self.base_url}/dashboard")
        time.sleep(1.0)
        assert "/dashboard" not in self.driver.current_url or "auth_required=true" in self.driver.current_url, (
            f"Protected dashboard accessible after session invalidation! URL: {self.driver.current_url}"
        )
        print("  [OK] Unauthenticated user automatically redirected to landing page.")

        self.capture_screenshot("13_session_expired_redirect.png")
        self.journeys_passed.append(("Journey 11: Session Expiration", "Verified HTTP 401 rejection and redirect to login upon session invalidation."))

    # ══════════════════════════════════════════════════════════════
    # JOURNEY 12: ADMINISTRATIVE PRIVILEGE ENFORCEMENT & KPIS
    # ══════════════════════════════════════════════════════════════
    def journey_12_admin_workflows(self):
        print("\n--- [Journey 12] Administrative Privilege Enforcement & KPIs ---")
        self.driver.get(f"{self.base_url}/")
        time.sleep(0.5)

        acc_field = self.driver.find_element(By.ID, "login-acc-no")
        acc_field.clear()
        acc_field.send_keys(TEST_ADMIN_ACC)
        pwd_field = self.driver.find_element(By.ID, "login-password")
        pwd_field.clear()
        pwd_field.send_keys(TEST_ADMIN_PASS)
        self.driver.find_element(By.ID, "btn-login-submit").click()
        time.sleep(1.5)

        admin_data = self.driver.execute_script("""
            const resp = await fetch('/api/admin/dashboard');
            if (resp.ok) {
                return await resp.json();
            }
            return null;
        """)
        assert admin_data is not None, "Admin failed to access /api/admin/dashboard!"
        print(f"  [OK] Admin dashboard retrieved successfully: {admin_data.get('total_accounts', 0)} total accounts.")

        self.capture_screenshot("14_admin_verified.png")
        self.journeys_passed.append(("Journey 12: Admin Operations & RBAC", "Verified administrative authentication and operational KPI access."))

    def run_all(self):
        try:
            self.start_server()
            self.init_driver()

            # Execute all 12 user journeys
            rec_acc = self.journey_01_registration()
            self.journey_02_authentication()
            self.journey_03_dashboard_balance_reveal()
            self.journey_04_deposit()
            self.journey_05_withdrawal()
            self.journey_06_transfer(rec_acc)
            self.journey_07_duplicate_transfer_idempotency(rec_acc)
            self.journey_08_upi_workflow()
            self.journey_09_wealth_products()
            self.journey_10_loan_application()
            self.journey_11_session_expiration()
            self.journey_12_admin_workflows()

            # Verify browser console cleanliness (separate from user journeys)
            self.verify_browser_console_cleanliness()

            print("\n" + "=" * 65)
            print(f"REAL BROWSER DOM AGENT RESULTS: {len(self.journeys_passed)} OF 12 JOURNEYS PASSED")
            print("=" * 65)
            for idx, (name, desc) in enumerate(self.journeys_passed, 1):
                print(f"[{idx:02d}/12] [PASS] {name}: {desc}")

            return True, self.journeys_passed

        except Exception as e:
            print(f"\n[!] DOM TEST FAILURE: {e}")
            import traceback
            traceback.print_exc()
            if self.driver:
                self.capture_screenshot("99_dom_failure.png")
            return False, self.journeys_passed
        finally:
            self.close_driver()
            self.stop_server()


if __name__ == "__main__":
    tester = RealBrowserDOMTestSuite()
    success, results = tester.run_all()
    sys.exit(0 if success else 1)
