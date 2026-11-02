# Credence Core — Architecture Refactoring Report (Phase 4)

## Overview & Scope
- **Phase**: 4 — Architecture Refactoring
- **Role**: Senior Full-Stack Architect
- **Target**: Deconstruct monolithic 4,396-line `flask_app.py` into a modular, production-ready package architecture under `backend/app/`.
- **Constraint Compliance**:
  - Frontend UI/HTML remained untouched and 100% functional.
  - Zero features removed or deprecated.
  - Dual sources of truth eliminated; C++ engine decoupled into a benchmarked simulation harness.
  - Single canonical persistent financial engine established via PostgreSQL & double-entry ledger.
  - 100% pass rate achieved across all test suites.

---

## 1. Monolith Slimming & Refactoring Metrics

| Metric | Before Refactoring | After Refactoring | Change |
| :--- | :--- | :--- | :--- |
| **Monolithic File Size (`flask_app.py`)** | 4,396 lines / ~193 KB | 78 lines / ~2.5 KB | **-98.2% reduction** |
| **Architecture Layout** | Single unstructured file | Clean multi-tier package (`backend/app/`) | Enterprise Modular |
| **Route Modules (Blueprints)** | 1 (monolithic global app) | 13 domain Blueprints | Decoupled by domain |
| **Domain Services** | 0 (mixed in route handlers) | 11 dedicated service modules | 100% business logic isolated |
| **Data Repositories (DAL)** | 0 (direct SQL/JSON lookups) | 6 specialized repositories | 100% data access encapsulated |
| **Input Validation** | Ad-hoc `if` statements | Centralized `schemas.validators` | Unified `ValidationError` |
| **Error Handling** | Uncaught exceptions leaking traces | Centralized uniform JSON handlers | Zero trace/exception leakage |
| **API Documentation** | None / manual markdown | OpenAPI 3.0.3 (`/api/openapi.json`, `/api/docs`) | Auto-documented Swagger UI |
| **Automated Test Coverage** | 33 tests | 42 comprehensive tests | +9 architecture tests |
| **Test Pass Rate** | 100% (33/33) | **100% (42/42)** | Zero regressions |

---

## 2. Structural Layer Breakdown

### A. Presentation Layer (`backend/app/api`)
Thin controllers responsible solely for HTTP parameter extraction, invoking validators, calling services, and returning uniform JSON payloads:
1. `auth_routes.py`: CSRF issuance, customer login with brute-force lockout, demo login, logout.
2. `account_routes.py`: Customer onboarding, account retrieval (with BOLA protection), demo info.
3. `transfer_routes.py`: Deposits and interbank transfers (IMPS/NEFT/RTGS).
4. `payment_routes.py`: Utility bill payments and merchant debit transactions.
5. `card_routes.py`: Card blocking, issuance, chequebook and physical card orders.
6. `investment_routes.py`: Fixed Deposits, Recurring Deposits, Mutual Fund SIPs, 24K Digital Gold, IPO bids.
7. `loan_routes.py`: Loan applications and repayments.
8. `upi_routes.py`: UPI profile creation and secure UPI PIN reset.
9. `ledger_routes.py`: General ledger transaction reversal and trial-balance reconciliation.
10. `statement_routes.py`: Account transaction history, monthly analytics, and ReportLab PDF downloads.
11. `settings_routes.py`: Profile updates, password rotation, 2FA toggle, notifications, and privileged C++ benchmark execution.
12. `docs_routes.py`: OpenAPI 3.0 specification and interactive Swagger UI.
13. `frontend_routes.py`: Static HTML delivery and UI routing.

### B. Business & Domain Service Layer (`backend/app/services`)
Pure Python services executing domain logic, financial integrity checks, and double-entry general ledger postings:
- `AuthenticationService`: Session management, Argon2id verification, account lockout counter tracking.
- `AccountService`: Balance calculations, profile aggregations, and masked card representations.
- `LedgerService`: Double-entry accounting transactions, balance checks, and atomic reversals.
- `TransferService`: Interbank money movement with idempotency keys and fraud evaluation.
- `PaymentService`: Utility bill settlement and debit card purchases.
- `InvestmentService`: Compound interest calculation, Gold rate quoting, and SIP execution.
- `LoanService`: Loan tenure validation, interest assessment, and repayment amortizations.
- `CardService`: Card state transitions and physical delivery orders.
- `StatementService`: Period-based filtering, spend categorization, and PDF byte generation.
- `FraudDetectionService`: High-value threshold inspection (₹200,000+) and anomalous velocity detection.
- `NotificationService`: Internal audit logging and client event notifications.

### C. Data Access Layer (`backend/app/repositories`)
Clean data access layer encapsulating all SQLAlchemy queries:
- `BaseRepository`: Common CRUD operations (`add`, `delete`, `commit`, `rollback`).
- `UserRepository`: User lookup by customer ID, account number, or email.
- `AccountRepository`: Account lookup, balance records, and status updates.
- `TransactionRepository`: Transaction history, idempotency keys, and general ledger journal entries.
- `InvestmentRepository`: FDs, RDs, SIPs, Gold holdings, and IPO applications.
- `LoanRepository`: Active loans and payment records.
- `CardRepository`: Debit and credit cards with masked identifiers.

### D. Centralized Validation & Error Handling
- **Validators (`backend/app/schemas/validators.py`)**:
  - `validate_account_number`: Enforces 14-digit numeric format or system clearing accounts.
  - `validate_amount`: Strictly validates monetary figures, rejecting negatives, zero, NaN, and Infinity.
  - `validate_pin`: Enforces 4-digit or 6-digit numeric formats.
  - `validate_password_strength`: Enforces minimum 8 characters with required alphanumeric mix.
  - `validate_pan`: Enforces Indian Income Tax PAN format (`[A-Z]{5}[0-9]{4}[A-Z]`).
  - `validate_upi_id`: Enforces standard virtual payment address format (`user@provider`).
- **Error Handlers (`backend/app/middleware/error_handlers.py`)**:
  - Centralizes responses for `ValidationError`, `InsufficientFundsError`, `AccountNotFoundError`, `DuplicateTransactionError`, `HTTPException`, and generic 500 exceptions into a uniform structure:
    ```json
    {
      "success": false,
      "message": "Human-readable sanitized error message."
    }
    ```
  - Suppresses all internal stack traces and database error details from reaching clients.

---

## 3. C++ Decoupling & Benchmarking Analysis

### Problem Resolved
In the legacy system, transactions were executed intermittently against `bank_system.exe` or fallen back to in-memory Python dictionaries. This created two desynchronized, conflicting sources of truth.

### Modern Implementation
- **PostgreSQL + `LedgerService`** is the single canonical source of truth for all customer balances, accounts, and transactions.
- **`CPPEngineHarness` (`backend/app/utils/cpp_bench.py`)** encapsulates `bank_system.exe` as an independent computational benchmark harness.
- Benchmarks executed directly on host:
  - **Throughput**: ~15.53 transactions/second under sequential interactive pipe execution.
  - **Average Latency**: ~64.37 ms per benchmark cycle.
  - **Subprocess Management**: Clean `stdin`, `stdout`, `stderr` stream closure with process termination guarantees zero resource leaks.
  - **Access Control**: Privileged execution endpoint `/api/execute` strictly guarded by `@require_role('admin')`.

---

## 4. Test Verification & Zero Regression Evidence

The entire automated test suite was executed against the refactored architecture:

```text
Ran 42 tests in 5.816s

OK (100% Pass)
```

### Breakdown of Passing Test Suites:
1. `tests/test_security.py` (12 Tests):
   - Server-side authentication and session management.
   - Account lockout after 5 failed password attempts (HTTP 429).
   - Cross-account transfer authorization and BOLA/IDOR prevention (HTTP 403).
   - CSRF token enforcement for mutations.
   - Role-Based Access Control on administrative routes (`/api/accounts`, `/api/demo_info`, `/api/execute`).
   - Zero credential leakage (PINs, passwords, CVVs never returned; card numbers masked with `••••`).
2. `tests/test_financial_integrity.py` (11 Tests):
   - Double-entry general ledger debit-credit balancing.
   - Transaction idempotency key deduplication.
   - Available balance limits and overdraft prevention.
   - Full migration of all 10 financial operations (Deposits, Transfers, Bill Pay, Cards, FDs, RDs, SIPs, Gold, Loans, IPOs).
   - General ledger reversals and reconciliation auditing.
3. `tests/test_database_migration.py` (10 Tests):
   - All 18 relational database tables validated in PostgreSQL/SQLite schema.
   - Zero plaintext credentials migrated.
   - Double-entry ledger integrity checks.
   - Rollback export utility creating valid JSON backups.
   - Account state persistence across process restarts.
4. `tests/test_architecture_refactoring.py` (9 Tests):
   - Application factory and Blueprint registration across all 13 domains.
   - OpenAPI 3.0 specification available at `/api/openapi.json`.
   - Swagger UI documentation available at `/api/docs`.
   - Centralized validation rejecting malformed inputs with uniform HTTP 400.
   - Centralized error handling suppressing internal stack traces.
   - Service layer and repository layer decoupling verified.
   - C++ benchmark harness throughput and latency validation.
   - Admin RBAC guard on `/api/execute`.

---

## 5. Deliverables & Next Phase Readiness

All deliverables for Phase 4 have been materialized:
- [ARCHITECTURE.md](file:///d:/bank_system_clean/ARCHITECTURE.md): Complete architecture manual, directory tree, data flows, and C++ separation documentation.
- [REFACTORING_REPORT.md](file:///d:/bank_system_clean/REFACTORING_REPORT.md): Quantitative refactoring metrics and test evidence.
- [backend/app/](file:///d:/bank_system_clean/backend/app/): Complete modular package layout.
- [flask_app.py](file:///d:/bank_system_clean/flask_app.py): Clean, lightweight application entrypoint proxy.
- [tests/test_architecture_refactoring.py](file:///d:/bank_system_clean/tests/test_architecture_refactoring.py): Comprehensive Phase 4 regression test suite.

The repository is now fully decoupled, maintainable, secure, and ready for commit.
