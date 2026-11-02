# CREDENCE CORE — APPLICATION SECURITY AUDIT & VULNERABILITY REGISTER

**Document Classification:** Confidential Application Security Audit  
**Project:** Credence Core — Institutional Digital Banking & Wealth Terminal  
**Audit Phase:** Phase 0 (Stabilization & Forensic Analysis)  
**Date:** 2026-10-31  
**Lead Auditor:** Senior Application Security Engineer  
**Compliance Standards:** OWASP Top 10 (2021), OWASP API Security Top 10 (2023), CWE/SANS Top 25  
**Active Git Branch:** `stabilization/phase-0`  

> [!IMPORTANT]
> **Mandatory Security Rule Adherence:** In accordance with the security audit charter, sensitive credentials, demo passwords, and PINs have been redacted and are identified solely by parameter keys, structural patterns, and exact line references.

---

## 1. Vulnerability Summary Matrix

| ID | Title | Severity | OWASP / CWE Mapping | Primary File & Line Reference |
| :--- | :--- | :--- | :--- | :--- |
| **SEC-01** | Global Broken Object Level Authorization (BOLA/IDOR) | **CRITICAL** | API1:2023 / CWE-639 | `flask_app.py:947-1005`, `1238-1274`, `2719-2775` |
| **SEC-02** | Complete Absence of Session Tokens & Empty Password Bypass | **CRITICAL** | API2:2023 / CWE-287, CWE-384 | `flask_app.py:832-860`, `app.js:2903-2919` |
| **SEC-03** | Unrestricted Remote Execution via Menu Gateway (`/api/execute`) | **CRITICAL** | API5:2023 / CWE-285 | `flask_app.py:3073-3080`, `app.js:2764-2769` |
| **SEC-04** | Plaintext Storage of Passwords, PINs, Full PANs & CVVs | **HIGH** | API3:2023 / CWE-312 | `user_profiles.json:7, 9, 10, 11, 15` |
| **SEC-05** | Direct Financial Secret Leakage via Account Details API | **HIGH** | API3:2023 / CWE-200 | `flask_app.py:977-998` |
| **SEC-06** | Hardcoded Demo Credentials in Client HTML Script | **HIGH** | CWE-798 | `code.html:Script 4 (lines 364-372)` |
| **SEC-07** | Predictable PRNG Seeding Affecting Global Process State | **MEDIUM** | CWE-330, CWE-338 | `flask_app.py:964, 985`, `utils.cpp:32, 41, 45` |
| **SEC-08** | Wildcard Cross-Origin Resource Sharing (CORS) Configuration | **MEDIUM** | CWE-942 | `flask_app.py:737-741` |
| **SEC-09** | Console Information Disclosure of CVV and Card Secrets in C++ | **MEDIUM** | CWE-532 | `utils.cpp:84-85`, `debit.cpp:45`, `credit.cpp:65` |
| **SEC-10** | Missing File-Locking & Data Race in Multi-Worker Environments | **MEDIUM** | CWE-362 | `flask_app.py:48-55, 76-83, 1208-1236` |
| **SEC-11** | Dynamic Memory Leaks via Uncollected Linked-List Transactions | **LOW** | CWE-401 | `utils.cpp:9-12`, `bank.h:25-29` |

---

## 2. In-Depth Vulnerability Analysis

---

### SEC-01: Global Broken Object Level Authorization (BOLA / IDOR)
- **Severity:** **CRITICAL**
- **CWE:** CWE-639: Authorization Bypass Through User-Controlled Key
- **OWASP:** API1:2023 Broken Object Level Authorization
- **Locations:** 
  - `flask_app.py:947-1005` (`get_account`)
  - `flask_app.py:1238-1274` (`transfer_api`)
  - `flask_app.py:1276-1362` (`pay_bill`)
  - `flask_app.py:1406-1448` (`create_fd`)
  - `flask_app.py:1449-1488` (`withdraw_fd`)
  - `flask_app.py:2367-2434` (`create_sip`)
  - `flask_app.py:2599-2657` (`gold_buy`)
  - `flask_app.py:2659-2717` (`gold_sell`)
  - `flask_app.py:2719-2775` (`apply_loan`)
  - `flask_app.py:2776-2818` (`repay_loan`)
  - `flask_app.py:2868-2925` (`get_statement_pdf`)
  - `flask_app.py:3026-3045` (`update_password`)
- **Vulnerability Details:**
  Every endpoint across the application relies solely on the client-supplied account number (either in the URL path or JSON request body). The server contains **zero identity validation** to verify that the requesting user owns or has access rights to the account.
- **Exploitation Scenario:**
  An attacker knowing or enumerating a 14-digit account number (or 9-digit CIF) can:
  1. Liquidate the victim's Fixed Deposits into primary balance via `POST /api/withdraw_fd`.
  2. Transfer all funds out of the victim's account to an external or escrow account via `POST /api/transfer`.
  3. Draw loans up to ₹500,000 against the victim's account via `POST /api/apply_loan`.
  4. Overwrite the victim's netbanking password via `POST /api/settings/password`.
  5. Download the complete certified bank statement PDF of any customer via `GET /api/statement_pdf/<target_acc_no>`.
- **Regression Risk of Fix:** High. Remediation requires introducing an authenticated session state (HMAC session cookie or JWT bearer token) that frontend fetch calls must pass.

---

### SEC-02: Complete Absence of Session Tokens & Empty Password Authentication Bypass
- **Severity:** **CRITICAL**
- **CWE:** CWE-287: Improper Authentication, CWE-384: Session Fixation
- **OWASP:** API2:2023 Broken Authentication
- **Locations:**
  - `flask_app.py:832-860` (`login`)
  - `app.js:2903-2919`
- **Vulnerability Details:**
  1. **Authentication Bypass on Empty Password:** In `flask_app.py:846`:
     ```python
     nb_pass_on_file = bank.user_details_db.get(str(accNo), {}).get("nb_pass")
     if nb_pass_on_file and password and password != nb_pass_on_file:
         return jsonify({"success": False, "message": "Invalid Netbanking Password!"})
     ```
     If an attacker submits `{"account": "40273146502136", "password": ""}`, the condition `and password` evaluates to `False`. The check is bypassed entirely, granting successful login without requiring a password.
  2. **No Cryptographic Session Established:** Upon successful login, the server returns a bare JSON payload without issuing an `HttpOnly` cookie or cryptographic token. The client simply executes `sessionStorage.setItem('current_account', acc)`. Anyone can open browser developer tools and write `sessionStorage.setItem('current_account', '<VICTIM_ACCOUNT>')` to gain complete administrative access to that customer's dashboard.
- **Remediation:** Enforce mandatory password presence, verify hashed passwords using Argon2 or PBKDF2, and issue a signed, encrypted HTTP-only session cookie.

---

### SEC-03: Unrestricted Remote Execution via Menu Gateway (`/api/execute`)
- **Severity:** **CRITICAL**
- **CWE:** CWE-285: Improper Authorization
- **OWASP:** API5:2023 Broken Function Level Authorization
- **Locations:**
  - `flask_app.py:3073-3080` (`execute_command`)
  - `app.js:2764-2769` (`window.openDepositModal`)
- **Vulnerability Details:**
  The `/api/execute` endpoint takes arbitrary menu choices (`1` through `14`) and an unvalidated array of parameters, executing them directly against the core banking engine. 
  Furthermore, the frontend's deposit modal misuses this endpoint:
  ```javascript
  const res = await fetch('/api/execute', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ choice: 1, inputs: [currentAcc, amount] })
  });
  ```
  Choice 1 in `BankBackend.execute` corresponds to **Account Creation**, not fund deposit. Every time an authenticated user attempts to deposit funds, the system spawns an unregistered phantom account rather than crediting the user's balance.
- **Remediation:** Remove `/api/execute` from external routing entirely or restrict it to authenticated system maintenance roles. Implement a dedicated, validated `POST /api/deposit` endpoint.

---

### SEC-04: Plaintext Storage of Passwords, PINs, Full PANs & CVVs
- **Severity:** **HIGH**
- **CWE:** CWE-312: Cleartext Storage of Sensitive Information
- **OWASP:** API3:2023 Broken Object Property Level Authorization
- **Locations:**
  - `user_profiles.json` (lines 7, 9, 10, 11, 15)
  - `flask_app.py:3043` (`update_password`)
- **Vulnerability Details:**
  User authentication and card secrets are stored in cleartext JSON on the host filesystem:
  - `"nb_pass"`: Netbanking passwords stored in plaintext.
  - `"pin"`: ATM / card PINs stored in plaintext.
  - `"card_number"`: Full 16-digit Primary Account Numbers stored unmasked.
  - `"cvv"`: Card Verification Values stored permanently on disk (violating PCI-DSS Requirement 3.2, which strictly prohibits post-authorization CVV storage).
  - `"pan"`: Permanent Account Numbers (tax IDs) stored unencrypted.
- **Remediation:** Hash passwords using `werkzeug.security.generate_password_hash` or `bcrypt`. Hash PINs using SHA-256 with user-specific salts. Mask card numbers (`**** **** **** 1234`). Purge CVV storage from the persistence schema.

---

### SEC-05: Direct Financial Secret Leakage via Account Details API
- **Severity:** **HIGH**
- **CWE:** CWE-200: Exposure of Sensitive Information to an Unauthorized Actor
- **OWASP:** API3:2023 Broken Object Property Level Authorization
- **Locations:**
  - `flask_app.py:977-998` (`get_account`)
- **Vulnerability Details:**
  When `/api/account/<acc_no>` is requested, the endpoint returns:
  ```python
  acc["card_number"] = details.get("card_number")
  acc["cvv"] = details.get("cvv")
  acc["cc_number"] = details.get("cc_number", "")
  acc["cc_cvv"] = details.get("cc_cvv", "")
  acc["cc_expiry"] = details.get("cc_expiry", "")
  ```
  Any anonymous internet user can query `/api/account/<acc_no>` and harvest active debit and credit card numbers, complete CVVs, expiration dates, home addresses, and emails.
- **Remediation:** Mask card numbers to the last 4 digits in API responses. Remove `cvv` and `cc_cvv` completely from the serialized response payload.

---

### SEC-06: Hardcoded Demo Credentials in Client HTML Script
- **Severity:** **HIGH**
- **CWE:** CWE-798: Use of Hard-coded Credentials
- **Locations:**
  - `code.html:Script 4 (lines 364-372)`
- **Vulnerability Details:**
  The landing page contains an inline JavaScript function:
  ```javascript
  function handleQuickDemoLogin() {
      const accInput = document.getElementById('login-acc-no');
      const passInput = document.getElementById('login-password');
      if (accInput) accInput.value = '40273146502136';
      if (passInput) passInput.value = '<REDACTED_DEMO_PASSWORD>';
      ...
  }
  ```
  Exposing default credentials directly in production markup enables automated credential stuffing and unauthorized account access.
- **Remediation:** Remove embedded credential strings. If a demo autofill is required, implement a server-side demo session exchange or mock sandbox token that does not expose production credentials in client markup.

---

### SEC-07: Predictable PRNG Seeding Affecting Global Process State
- **Severity:** **MEDIUM**
- **CWE:** CWE-330: Use of Insufficiently Random Values, CWE-338: Use of Cryptographically Weak PRNG
- **Locations:**
  - `flask_app.py:964, 985` (`get_account`)
  - `utils.cpp:32, 41, 45` (`generateDebitCard`)
- **Vulnerability Details:**
  In `flask_app.py:964`:
  ```python
  import random
  random.seed(int(acc_no))
  details["card_number"] = f"4{random.randint(100,999)} {random.randint(1000,9999)}..."
  details["cvv"] = str(random.randint(100, 999))
  ...
  random.seed()
  ```
  Calling `random.seed(int(acc_no))` re-seeds the global process-wide PRNG of Python. In a multi-threaded web application, concurrent threads executing requests simultaneously will experience altered pseudo-random sequences. Furthermore, because the account number is public, the card number and CVV are mathematically deterministic and trivially computable by any party knowing the account number.
- **Remediation:** Use Python's `secrets` module (`secrets.randbelow`, `secrets.token_hex`) which relies on OS-level cryptographic entropy (`/dev/urandom` / `BCryptGenRandom`).

---

### SEC-08: Wildcard Cross-Origin Resource Sharing (CORS) Configuration
- **Severity:** **MEDIUM**
- **CWE:** CWE-942: Permissive Cross-domain Policy with Untrusted Domains
- **Locations:**
  - `flask_app.py:737-741` (`add_cors_headers`)
- **Vulnerability Details:**
  The server unconditionally attaches `Access-Control-Allow-Origin: *` to every HTTP response. If combined with ambient credentials or intranet deployment, external malicious websites can forge cross-origin requests against local banking instances.
- **Remediation:** Restrict allowed origins to designated domain origins and configure explicit origin whitelists.

---

### SEC-09: Console Information Disclosure of Financial Secrets in C++
- **Severity:** **MEDIUM**
- **CWE:** CWE-532: Insertion of Sensitive Information into Log File / Console
- **Locations:**
  - `utils.cpp:84-85` (`showTestInfo`)
  - `debit.cpp:45` (`debitPayment`)
  - `credit.cpp:65` (`applyCreditCard`)
- **Vulnerability Details:**
  The native C++ routines print system and customer card details, expiration dates, PINs, CVVs, and PANs directly to `stdout`. Any server monitoring tool or terminal capture will record these secrets in plaintext logs.
- **Remediation:** Strip CVV and PIN printing from all output routines. Redact card numbers to display only the last 4 digits.

---

### SEC-10: Missing File-Locking & Data Race in Multi-Worker Environments
- **Severity:** **MEDIUM**
- **CWE:** CWE-362: Concurrent Execution using Shared Resource with Improper Synchronization ('Race Condition')
- **Locations:**
  - `flask_app.py:48-55` (`save_profiles`)
  - `flask_app.py:76-83` (`save_investments`)
  - `flask_app.py:1208-1236` (`save_transaction`)
- **Vulnerability Details:**
  The application uses `threading.Lock()` (`bank.lock`) to serialize in-memory modifications within a single Python process. However, production deployments (`render.yaml:6`, `Procfile:1`) launch Gunicorn with multiple worker processes. Processes do not share `threading.Lock()`. When multiple workers write to `user_profiles.json` or `bank_data.json`, file clobbering occurs, leading to silent state loss and corrupted transaction records.
- **Remediation:** Introduce inter-process file locking (e.g. `portalocker` or SQLite file-level locking) or transition persistence to an embedded ACID database (e.g., SQLite3 / PostgreSQL).

---

### SEC-11: Dynamic Memory Leaks via Uncollected Linked-List Transactions
- **Severity:** **LOW**
- **CWE:** CWE-401: Missing Release of Memory after Effective Lifetime
- **Locations:**
  - `utils.cpp:9-12` (`addTransaction`)
  - `bank.h:25-29` (`struct Transaction`)
- **Vulnerability Details:**
  `addTransaction()` allocates heap memory via `new Transaction{type, amount, acc.history}`. There is no corresponding `delete` anywhere in the codebase, nor is there a destructor on `Account`. Over prolonged runtime, this leaks memory for every transaction executed.
- **Remediation:** Replace raw pointers with modern C++ containers (`std::vector<Transaction>`) or smart pointers (`std::unique_ptr<Transaction>`).
