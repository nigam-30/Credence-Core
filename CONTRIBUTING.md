# Contributing to Credence Core

Thank you for your interest in contributing to **Credence Core**!

This guide outlines our development workflow, engineering standards, coding conventions, and pull request verification criteria.

---

## 1. Code of Conduct
We are committed to providing a welcoming, inclusive, and professional environment for all contributors. Please treat everyone with respect and empathy.

---

## 2. Development Setup

### 2.1 Prerequisites
- **Python**: 3.10+ (tested through 3.13)
- **C++ Compiler**: GCC 6.3+ / Clang 11+ / MSVC 2019+ supporting C++14/C++20
- **PostgreSQL**: 14+ (optional for local dev; SQLite fallback is available in `development` mode)
- **Redis**: 6+ (optional for local dev; memory fallback is available)
- **Git**

### 2.2 Local Environment Setup
```bash
# 1. Clone the repository
git clone https://github.com/your-org/credence-core.git
cd credence-core

# 2. Create and activate a virtual environment
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# 3. Install production and development dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 4. Copy environment configuration
cp .env.example .env
```

---

## 3. Architecture & Coding Standards

1. **Financial Integrity**:
   - Never use standard Python `float` or JavaScript `Number` for financial calculations.
   - Always calculate balances and transaction amounts in integer subunit **paise** using `Decimal` and banker's rounding (`ROUND_HALF_EVEN`).
   - Every financial operation must create balanced double-entry `ledger_entries` (debit = credit).

2. **Security by Design**:
   - Zero plaintext credentials or fallback passwords.
   - All password and PIN verifications must go through `backend/app/core/security.py` using Argon2id.
   - Use CSRF synchronizer tokens for all mutating browser requests.
   - Parameterize all database queries via SQLAlchemy models and repositories; never concatenate SQL strings.

3. **C++ High-Performance Engine**:
   - C++ code must compile warning-free with strict compiler flags:
     ```bash
     g++ -std=c++14 -Wall -Wextra main.cpp account.cpp credit.cpp debit.cpp fd.cpp loan.cpp report.cpp upi.cpp utils.cpp cheque.cpp globals.cpp -o bank_system
     ```
   - Ensure dynamic memory allocations are freed and ownership is explicitly handled.

---

## 4. Testing & Verification

All contributions must pass the complete regression suite:
```bash
# Run full automated test suite
python -m pytest -v

# Run with coverage report
python -m pytest --cov=backend --cov-report=term-missing
```

Ensure all tests pass with **0 failures and 0 regressions**.

---

## 5. Submitting Changes

1. Create a feature/fix branch from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```
2. Make your changes adhering to PEP 8 standards and project architecture.
3. Run the regression test suite and verify clean execution.
4. Commit your changes with descriptive, conventional commit messages:
   ```bash
   git commit -m "feat(ledger): add real-time audit event for dispute settlement"
   ```
5. Open a Pull Request against `main`. Provide a clear description of changes, motivation, and test verification output.
