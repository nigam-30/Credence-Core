# CREDENCE CORE — API INVENTORY & CONTRACT MATRIX

**Document Classification:** Technical Architecture & API Contract Specification  
**Project:** Credence Core — Institutional Digital Banking & Wealth Terminal  
**Audit Phase:** Phase 0 (Stabilization & Forensic Analysis)  
**Date:** 2026-10-31  
**Active Git Branch:** `stabilization/phase-0`  

---

## 1. Overview & Protocol Summary

The Credence Core backend exposes **50 HTTP route endpoints** in `flask_app.py`, spanning web view dispatchers, core banking operations, card/service dispatching, wealth management (SIP/IPO/RD/Gold), loan management, statement generation, and system settings.

### Global Contract Deficits:
- **Zero Authentication Enforcement:** Endpoints accept bare account numbers without session tokens, cookies, or authorization headers.
- **Inconsistent Error Signatures:** Some endpoints return `{"success": False, "message": "..."}`, others return `{"success": False, "result": "..."}`, and `get_account` returns `{"error": "Not found"}, 404`.
- **CORS Handling:** Managed globally in `flask_app.py:737-741` adding `Access-Control-Allow-Origin: *`, `Access-Control-Allow-Methods: *`, and `Access-Control-Allow-Headers: *`.

---

## 2. Comprehensive Endpoint Catalog

### 2.1 Authentication & Profile APIs

#### `POST /api/login`
- **Location:** `flask_app.py:832-860`
- **Callers:** `code.html:Script 4 (line 386)` and `app.js:2904`
- **Request Payload:**
  ```json
  {
    "account": "40273146502136",
    "password": "<PASSWORD>"
  }
  ```
- **Response Payload (Success):**
  ```json
  {
    "success": true,
    "message": "Logged in",
    "account": {
      "account_number": "40273146502136",
      "name": "Ben Tennyson",
      "balance": "25500.00",
      "loan_amount": "6000.00",
      "fixed_deposit": "3000.00"
    }
  }
  ```
- **Response Payload (Failure):** `{"success": false, "message": "Invalid Netbanking Password!"}`
- **Security Defect:** Empty password bypass (`if nb_pass_on_file and password and password != nb_pass_on_file:`). Supplying an empty password bypasses validation completely.
- **State Changes:** None on server; client stores account in `sessionStorage.setItem('current_account', acc)`.

#### `POST /api/create_account`
- **Location:** `flask_app.py:862-945`
- **Callers:** `app.js:2823`
- **Request Payload:**
  ```json
  {
    "name": "Full Name",
    "deposit": 10000.0,
    "pin": "1234",
    "email": "user@example.com",
    "dob": "1995-05-15",
    "pan": "ABCDE1234F",
    "employment_type": "Salaried",
    "account_type": "Savings Account",
    "address": "Postal Address",
    "want_debit": "y",
    "want_upi": "username@credence",
    "nb_pass": "<PASSWORD>"
  }
  ```
- **Response Payload:** `{"success": true, "message": "...", "account_number": "...", "customer_id": "...", "account_type": "..."}`
- **State Changes:** Generates unique 14-digit account number and 9-digit CIF. Persists profile to `user_profiles.json` and in-memory ledger. Creates initial deposit entry in `bank_data.json`.

#### `GET /api/account/<acc_no>`
- **Location:** `flask_app.py:947-1005`
- **Callers:** `app.js:408, 413` (`syncAccountData`)
- **Request Params:** `acc_no` (URL path)
- **Response Payload:** Complete account object including `balance`, `loan_amount`, `fixed_deposit`, `customer_id`, `card_number`, `cvv`, `expiry`, `cc_number`, `cc_cvv`, `cc_expiry`, `cc_limit`, `history`, `blocked_cards`.
- **Security Defect:** Extreme BOLA / IDOR. Leaks unmasked CVVs, PAN, full card numbers, PII, and financial history to unauthenticated GET requests.

---

### 2.2 Core Banking & Transfer APIs

#### `POST /api/transfer`
- **Location:** `flask_app.py:1238-1274`
- **Callers:** `app.js:2257` (`handleSendMoney`)
- **Request Payload:**
  ```json
  {
    "from_acc": "40273146502136",
    "to_acc": "99999999999999",
    "amount": "250",
    "method": "IMPS"
  }
  ```
- **Response Payload (Success):** `{"success": true, "result": "..."}`
- **State Changes:** Invokes `bank.execute("3", [from_acc, to_acc, amount])`. Deducts sender balance, credits receiver balance, appends debit transaction to sender and credit transaction to receiver in `bank_data.json`.

#### `POST /api/pay_bill`
- **Location:** `flask_app.py:1276-1362`
- **Callers:** `app.js:2310` (`handleBillPay`)
- **Request Payload:**
  ```json
  {
    "account": "40273146502136",
    "biller": "Electricity Bill",
    "company": "Adani Power",
    "amount": "750",
    "method": "Account Balance",
    "remarks": "Monthly Bill"
  }
  ```
- **Response Payload:** `{"success": true, "message": "Payment successful via Account Balance.", "result": "..."}`
- **State Changes:** Deducts amount from customer account, transfers to system escrow account `99999999999999`, logs transaction receipt.

#### `POST /api/debit_payment`
- **Location:** `flask_app.py:1364-1405`
- **Callers:** Orphaned / None in frontend.
- **Request Payload:** `{"account": "...", "pin": "...", "amount": "...", "merchant": "..."}`
- **Defect & Failure Status:** **BROKEN.** Line 1392 executes `bank.execute("2", [accNo, amount])`. Choice 2 is `checkBalance`, which does not deduct balance and does not return "success", causing this endpoint to fail unconditionally with "System declined payment".

---

### 2.3 Fixed Deposit (FD) APIs

#### `POST /api/create_fd`
- **Location:** `flask_app.py:1406-1448`
- **Callers:** `app.js:1615` (`handleCreateFD`)
- **Request Payload:** `{"account": "40273146502136", "amount": "3000", "tenure": "12"}`
- **Response Payload:** `{"success": true, "result": "...", "message": "Fixed Deposit booked successfully!"}`
- **State Changes:** Executes `bank.execute("7", [accNo, amount, tenure])`. Balance decreases, `fixedDeposit` increases, writes transaction to `bank_data.json` and updates profile in `user_profiles.json`.

#### `POST /api/withdraw_fd`
- **Location:** `flask_app.py:1449-1488`
- **Callers:** `app.js:1645` (`handleWithdrawFD`)
- **Request Payload:** `{"account": "40273146502136"}`
- **Response Payload:** `{"success": true, "result": "...", "message": "Fixed Deposit liquidated and credited to primary balance!"}`
- **State Changes:** Executes `bank.execute("8", [accNo])`. Moves all `fixedDeposit` back into balance, clears tenure from profile, logs credit transaction.

---

### 2.4 Wealth & Capital Markets Hub (SIP, IPO, RD, Gold)

#### `GET /api/investments/<acc_no>`
- **Location:** `flask_app.py:2308-2365`
- **Callers:** `app.js:859, 1734, 1917`
- **Request Params:** `acc_no` (URL path)
- **Response Payload:**
  ```json
  {
    "sips": [...],
    "ipos": [...],
    "rds": [...],
    "gold": {
      "grams": 0.1968,
      "avg_buy_price": 7620.5,
      "total_invested": 1500.0,
      "current_rate": 7620.5,
      "current_value": 1499.71,
      "returns_pct": -0.02
    },
    "portfolio_summary": { ... },
    "market_funds": [...],
    "market_ipos": [...]
  }
  ```

#### `POST /api/invest/sip`
- **Location:** `flask_app.py:2367-2434`
- **Callers:** `app.js:831, 1681` (`handleCreateSIP`)
- **Request Payload:** `{"account": "...", "fund_id": "MF-NIFTY50", "amount": 1000.0, "sip_day": 5}`
- **State Changes:** Executes `bank.execute("3", [acc_no, "99999999999999", amount])`. Credits system account, creates active SIP record in `user_investments.json`, logs transaction.

#### `POST /api/invest/sip_action`
- **Location:** `flask_app.py:2436-2480`
- **Callers:** `app.js:1713` (`handleSIPAction`)
- **Request Payload:** `{"account": "...", "sip_id": "SIP-5723", "action": "stop" | "withdraw"}`
- **State Changes:** When action is "withdraw", liquidates accumulated value back into primary balance via system transfer.

#### `POST /api/invest/ipo_bid`
- **Location:** `flask_app.py:2482-2538`
- **Callers:** `app.js:2021`
- **Request Payload:** `{"account": "...", "ipo_id": "IPO-SWIGGY", "lots": 2, "upi_id": "..."}`
- **State Changes:** Deducts lien amount via system transfer `execute("3", ...)`, registers application in `user_investments.json`.

#### `POST /api/invest/create_rd`
- **Location:** `flask_app.py:2540-2597`
- **Callers:** `app.js:2074` (`handleCreateRD`)
- **Request Payload:** `{"account": "...", "amount": 2000, "tenure_months": 12}`
- **State Changes:** Deducts initial instalment, schedules RD in `user_investments.json`.

#### `POST /api/invest/gold_buy`
- **Location:** `flask_app.py:2599-2657`
- **Callers:** `app.js:2174` (`handleGoldBuy`)
- **Request Payload:** `{"account": "...", "amount": 500.0, "grams": 0.0656}`
- **State Changes:** Transfers amount to system escrow, updates `gold.grams` and `gold.total_invested` in `user_investments.json`.

#### `POST /api/invest/gold_sell`
- **Location:** `flask_app.py:2659-2717`
- **Callers:** `app.js:2219` (`handleGoldSell`)
- **Request Payload:** `{"account": "...", "grams": 0.05}`
- **State Changes:** Transfers payout from system account `99999999999999` to user account, decrements gold grams in `user_investments.json`.

---

### 2.5 Lending Hub APIs

#### `POST /api/apply_loan`
- **Location:** `flask_app.py:2719-2774`
- **Callers:** `app.js:1493` (`handleApplyLoan`)
- **Request Payload:** `{"account": "...", "amount": "5000", "tenure": "12", "purpose": "Personal"}`
- **Response Payload:** `{"success": true, "message": "Loan approved and credited!", "result": "..."}`
- **State Changes:** Executes `bank.execute("4", [accNo, amount])`. Increases both `balance` and `loanAmount`, logs disbursal in `bank_data.json`, records loan details in `user_profiles.json`.

#### `POST /api/repay_loan`
- **Location:** `flask_app.py:2776-2818`
- **Callers:** `app.js:1583` (`handleRepayLoan`)
- **Request Payload:** `{"account": "...", "amount": "2000"}`
- **Response Payload:** `{"success": true, "message": "Loan repayment processed successfully!", "result": "..."}`
- **State Changes:** Executes `bank.execute("5", [accNo, str(actual_repay)])`. Decreases `balance` and `loanAmount`, logs repayment in `bank_data.json`.

#### `GET /api/loans/<acc_no>`
- **Location:** `flask_app.py:2820-2866`
- **Callers:** `app.js:720`
- **Response Payload:** Returns active loan status, total outstanding, monthly EMI, interest rate (9.5%), and tenure.

---

### 2.6 Cards & Services Dispatch Ledger

#### `POST /api/block_card`
- **Location:** `flask_app.py:1007-1035`
- **Callers:** `app.js:2374` (`handleBlockCard`)
- **Request Payload:** `{"account": "...", "card_number": "..."}`
- **State Changes:** Appends card number to `blocked_cards` list in `user_profiles.json`.

#### `POST /api/issue_card`
- **Location:** `flask_app.py:1037-1064`
- **Callers:** `app.js:2411` (`handleReissueCard`)
- **Request Payload:** `{"account": "...", "card_type": "Visa Platinum"}`
- **State Changes:** Generates replacement card details, stores in `user_profiles.json`.

#### `POST /api/services/order_chequebook`
- **Location:** `flask_app.py:1066-1110`
- **Callers:** `app.js:2481`
- **Request Payload:** `{"account": "...", "leaves": "25", "address": "..."}`
- **State Changes:** Generates CTS-2010 cheque range and SpeedPost tracking ID, records dispatch order in `user_profiles.json`.

#### `POST /api/services/order_physical_card`
- **Location:** `flask_app.py:1112-1173`
- **Callers:** `app.js:2568`
- **Request Payload:** `{"account": "...", "card_tier": "Obsidian Visa Platinum", "custom_pin": "1234", "delivery_address": "..."}`
- **State Changes:** Generates physical card dispatch with BlueDart tracking number, persists order in `user_profiles.json`.

---

### 2.7 Reports & Certified PDF Generation

#### `GET /api/statement/<acc_no>` and `GET /api/statement_pdf/<acc_no>`
- **Location:** `flask_app.py:2868-2925`
- **Callers:** `app.js:2720, 2736` (`downloadStatementPDF`)
- **Response:** Binary PDF stream (`Content-Type: application/pdf`, `Content-Disposition: attachment; filename=Credence_Bank_Statement_<acc_no>.pdf`).
- **Generation Engine:** ReportLab (`SimpleDocTemplate`, `Table`, `Paragraph`). Aggregates transactions from `bank_data.json`.

---

### 2.8 Settings & Execution Command APIs

#### `POST /api/settings/password`
- **Location:** `flask_app.py:3026-3045`
- **Callers:** `app.js:2668` (`handleUpdatePassword`)
- **Request Payload:** `{"account_number": "...", "old_password": "...", "new_password": "..."}`
- **Defect:** Stores password in plaintext. If account previously had no `nb_pass`, old password check is skipped entirely.

#### `POST /api/settings/2fa`
- **Location:** `flask_app.py:3047-3058`
- **Callers:** `app.js:2639` (`handleToggle2FA`)
- **State Changes:** Toggles `2fa_enabled` boolean in `user_profiles.json`.

#### `POST /api/update_profile`
- **Location:** `flask_app.py:3001-3024`
- **Callers:** `app.js:2693` (`handleUpdateProfile`)
- **Request Payload:** `{"account_number": "...", "email": "...", "dob": "YYYY-MM-DD"}`
- **State Changes:** Updates email and date of birth in `user_profiles.json`.

#### `POST /api/execute`
- **Location:** `flask_app.py:3073-3080`
- **Callers:** `app.js:2764` (`window.openDepositModal`)
- **Request Payload:** `{"choice": 1, "inputs": ["<ACC>", "<AMOUNT>"]}`
- **Critical Flaw:** Unauthenticated gateway to internal ledger choices. Used by the frontend modal to "deposit funds", which mistakenly executes Choice 1 (Create Account) and creates duplicate phantom accounts.

---

## 3. Orphaned, Uncalled, or Defective Endpoints Summary

| Endpoint | Method | Operational Status | Underlying Issue |
| :--- | :--- | :--- | :--- |
| `/api/debit_payment` | POST | **Defective / Broken** | Calls choice 2 (`checkBalance`), fails unconditionally. Not called by frontend. |
| `/api/execute` | POST | **Defective / Misused** | Misrouted by frontend to choice 1 for deposits; exposes unauthenticated menu execution. |
| `/api/reset_upi_pin` | POST | **Orphaned** | Defined in backend (lines 3185–3197); no calling UI elements in `app.js` or HTML. |
| `/api/accounts` | GET | **Orphaned** | Returns all account numbers (lines 1175–1188); not called by frontend. |
| `/api/demo_info` | GET | **Orphaned** | Returns system test credentials (lines 1190–1206); unused by frontend. |
| `/api/invest/market_data` | GET | **Orphaned** | Static fund catalog endpoint (lines 2286–2296); frontend uses embedded `window.currentMarketIpos`. |
| `/api/invest/live_gold_rate`| GET | **Orphaned** | Standalone rate endpoint (lines 2298–2306); rate is bundled into `/api/investments/<acc_no>`. |
| `/api/settings/notifications`| POST| **Orphaned** | Toggles notification preferences (lines 3060–3071); unused by frontend. |
