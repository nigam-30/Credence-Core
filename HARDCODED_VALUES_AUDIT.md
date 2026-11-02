# HARDCODED VALUES AUDIT & ELIMINATION REPORT

> **SIMULATOR NOTICE:** Credence Core is an educational banking system simulator.

---

## 1. AUDIT TAXONOMY & CLASSIFICATION

Every identified constant across the codebase has been inspected and classified under the following categories:
- **Class A: Security-Sensitive** (Secrets, keys, PINs, passwords, session tokens) — *Must never be hardcoded or leaked.*
- **Class B: Financial / Business Policy** (Limits, interest rates, fees, commodity prices) — *Must be centralized, versioned, and auditable.*
- **Class C: Environment-Specific Configuration** (Hosts, ports, URLs, database paths) — *Must be injected via environment variables.*
- **Class D: Legitimate Technical Constant** (HTTP status codes, hash lengths, timeouts, fixed protocol enums) — *Preserved.*
- **Class E: Test Fixture** (Automated testing fixtures, test accounts) — *Allowed strictly within `tests/`.*

---

## 2. AUDIT INVENTORY & REMEDIATION MATRIX

| # | File Path | Line Range | Identified Value / Pattern | Class | Severity | Remediation Action Taken |
|---|---|---|---|---|---|---|
| 1 | `app.js` | 134-142 | `expectedPin || 1234` | Class A | Critical | Completely removed client-side PIN comparison. Migrated to backend Argon2id verification (`/api/account/verify_pin`). |
| 2 | `backend/app/core/mfa.py` | 24-28 | `"credence_fallback_secret_key_prod_32chars"` | Class A | High | Removed fallback key. Enforced `MFA_ENCRYPTION_KEY` validation requiring 256-bit entropy. Fails startup in production. |
| 3 | `backend/app/core/config.py` | 38-41 | `"40273146502136"` hardcoded demo account | Class A / C | High | Removed default demo account in production profile. Production requires explicit `CONFIGURED_DEMO_ACCOUNTS`. |
| 4 | `security.py` | 512-515 | `acc_no in ["99999999999999", "999999"]` admin role | Class A | Critical | Removed magic account-number-based admin check. Role resolved strictly from database user record. |
| 5 | `backend/app/api/investment_routes.py` | 23-37 | Scattered gold/silver rates & interest rates | Class B | Medium | Centralized into `FinancialPolicy` (`backend/app/core/financial_policy.py`). |
| 6 | `account.cpp` | 148-152 | Default PIN override bug during account setup | Class A | High | Fixed logic in `account.cpp` so customer-chosen PIN is preserved. |
| 7 | `credit.cpp` | 24-30 | Hardcoded card number prefix / cleartext CVV | Class A | Medium | Masked CVV output and randomized 16-digit card generation. |
| 8 | `flask_app.py` | 86 | `SECRET_KEY = None` | Class A / C | High | Replaced with `app = create_app()` using unified configuration factory. |
| 9 | `transfer_routes.py` | 107-113 | Unrestricted recipient targets (GL accounts) | Class B / A | High | Blocked direct transfers to `SYSTEM_GL_ACCOUNTS` and `GL_*` addresses. |
| 10 | `backend/app/core/mfa.py` | 95-105 | Unversioned encryption cipher payload | Class A / D | Medium | Implemented version prefixing (`v1:...`, `v2:...`) and re-encryption utility. |

---

## 3. FINANCIAL POLICY CENTRALIZATION

All business policies and financial constants are now centralized in [`backend/app/core/financial_policy.py`](file:///D:/bank_system_clean/backend/app/core/financial_policy.py):
* **Policy Version:** `2026.2.0`
* **Default Daily Limit:** ₹5,00,000.00 (`50,000,000 paise`)
* **Default Per-Transaction Limit:** ₹1,00,000.00 (`10,000,000 paise`)
* **Default Savings Interest Rate:** `3.50%`
* **FD Rates:** `5.75%` (6mo), `6.50%` (12mo), `7.00%` (24mo), `7.25%` (36mo), `7.50%` (60mo)
* **Commodity Pricing:** Live rate overrides via `LIVE_GOLD_RATE_PER_GRAM_PAISE` and `LIVE_SILVER_RATE_PER_KG_PAISE` with auditable fallbacks.
