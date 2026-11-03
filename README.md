# Credence Core — Institutional Digital Banking & Wealth Terminal

[![Core Engine](https://img.shields.io/badge/CORE%20ENGINE-C%2B%2B14%2F20-00599C?style=for-the-badge&logo=c%2B%2B&logoColor=white)](https://github.com/nigam-30/Credence-Core)
[![Backend](https://img.shields.io/badge/BACKEND-PYTHON%20FLASK-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://github.com/nigam-30/Credence-Core)
[![Database](https://img.shields.io/badge/DATABASE-POSTGRESQL%20%7C%20ALEMBIC-336791?style=for-the-badge&logo=postgresql&logoColor=white)](https://github.com/nigam-30/Credence-Core)
[![Cache](https://img.shields.io/badge/CACHE-REDIS-DC382D?style=for-the-badge&logo=redis&logoColor=white)](https://github.com/nigam-30/Credence-Core)
[![UI Framework](https://img.shields.io/badge/UI-TAILWIND%20CSS-06B6D4?style=for-the-badge&logo=tailwindcss&logoColor=white)](https://github.com/nigam-30/Credence-Core)
[![Security](https://img.shields.io/badge/SECURITY-ARGON2ID%20%26%20MFA-22C55E?style=for-the-badge&logo=shield&logoColor=white)](https://github.com/nigam-30/Credence-Core)
[![Tests](https://img.shields.io/badge/TESTS-93%20PASSING-success?style=for-the-badge&logo=pytest&logoColor=white)](https://github.com/nigam-30/Credence-Core)
[![Deployment](https://img.shields.io/badge/DEPLOYMENT-RENDER%20%7C%20DOCKER-46E3B7?style=for-the-badge&logo=docker&logoColor=white)](https://github.com/nigam-30/Credence-Core)

> **⚠️ EDUCATIONAL SIMULATOR DISCLAIMER**  
> **Credence Core is an academic and educational simulation platform engineered solely to demonstrate core banking architectures, double-entry financial ledgers, and institutional security controls.**  
> - **Do not enter real banking credentials, passwords, real card numbers, or real identity information.**
> - Use only fictional test credentials and synthetic demo data.
> - Credence Core is **not a regulated bank, depository institution, or licensed payment operator**, and does not interface with central clearing switches (e.g., SWIFT, Fedwire, NPCI).

---

## 1. Project Overview

**Credence Core** is an enterprise-grade banking simulation terminal combining a high-performance C++ algorithmic computation engine with a modular Python/Flask backend and an ultra-responsive web terminal powered by Tailwind CSS.

Engineered with architectural discipline across Phases 0 through 6.4, Credence Core guarantees zero mathematical discrepancies via immutable double-entry bookkeeping, strict integer subunit (paise) arithmetic, Argon2id credential protection, TOTP multi-factor authentication, row-level concurrency locking, and full containerization.

---

## 2. Key Features

- **Double-Entry Financial Integrity Engine**:
  - Immutable general ledger tracking every credit and debit pair.
  - Integer subunit (paise) arithmetic via `Decimal` with banker's rounding (`ROUND_HALF_EVEN`), eliminating floating-point errors.
  - Pessimistic row locking (`SELECT FOR UPDATE`) prevents concurrent overdrafts and race conditions.
  - Payload-fingerprinted idempotency keys ensure at-most-once financial execution.
- **Retail & Corporate Banking**:
  - Multi-account management (Savings, Current, Central Clearing).
  - Instant peer-to-peer transfers, deposits, withdrawals, and scheduled bill payments.
  - Simulated UPI payments with virtual payment addresses (`user@credence`).
  - Virtual Debit Cards with CVV masking, freeze/unfreeze controls, and dynamic spend limits.
- **Wealth & Investment Suite**:
  - Fixed Deposits (FD) with compound interest accrual and premature liquidation penalty logic.
  - Systematic Investment Plans (SIP) and mutual fund portfolios.
  - Digital 24K Gold accumulation vault with real-time mark-to-market valuation.
  - Initial Public Offering (IPO) application processing with ASBA escrow hold simulation.
- **Institutional Security & Governance**:
  - Argon2id password and PIN hashing with zero plaintext storage.
  - Two-Factor Authentication (TOTP) with encrypted secrets (`AES-256-GCM`).
  - Bound CSRF synchronizer tokens and strict Content-Security-Policy (CSP).
  - Redis-backed distributed rate limiting, brute-force throttling, and automated lockouts.
  - Role-Based Access Control (RBAC) and strict BOLA/IDOR object-level authorization.
- **Reporting & Compliance**:
  - Certified PDF account statement generation using ReportLab.
  - Comprehensive immutable audit trail logging all security and financial events.
  - OpenAPI 3.0 interactive Swagger UI documentation at `/api/docs`.
- **C++ Computational Engine Harness**:
  - Decoupled, benchmarkable high-throughput C++ simulation engine for microsecond transaction stress verification.

---

## 3. Architecture & Repository Structure

```
Credence-Core/
├── backend/
│   └── app/
│       ├── api/             # Modular Blueprint controllers (auth, accounts, transfers, etc.)
│       ├── core/            # Configuration, database engine, Redis, logging, MFA
│       ├── middleware/      # CSRF, CORS, security headers, rate limiters, error handlers
│       ├── models/          # Domain model exports
│       ├── repositories/    # SQLAlchemy repository data access layers
│       ├── schemas/         # Input validation schemas and regex rules
│       ├── services/        # Decoupled business logic services
│       └── utils/           # Currency conversions, PDF generator, C++ benchmark harness
├── alembic/                 # Database migrations (18 relational modules)
│   └── versions/
├── docs/                    # Centralized project documentation
│   ├── architecture/        # Architecture diagrams, API inventory, data flow
│   ├── database/            # Database schema, ledger integrity, migration guide
│   ├── deployment/          # Production deployment guide (Render, Docker)
│   ├── security/            # Security policy, MFA, fraud detection, privacy
│   ├── testing/             # Test strategy, regression suite documentation
│   └── development/         # Contributing guide and standards
├── scripts/                 # Operations, migrations, backups, and local runner
├── tests/                   # Automated pytest regression suite (93 tests)
│   ├── fixtures/            # Sanitized synthetic test fixtures
│   └── qa/                  # E2E regression, security penetration, concurrency stress
├── .github/workflows/       # Automated CI/CD pipeline (lint, test, build)
├── database.py              # Root database engine & connection pool
├── ledger.py                # Double-entry Financial Integrity Engine
├── models.py                # 18 relational banking domain models
├── security.py              # Security core (Argon2id, CSRF, session manager)
├── flask_app.py             # Backward-compatibility application wrapper
├── gunicorn_config.py       # Production WSGI server configuration
├── Dockerfile               # Multi-stage production container build
├── docker-compose.yml       # Production Compose (Flask + PostgreSQL + Redis)
├── docker-compose.dev.yml   # Development Compose
├── render.yaml              # Render.com Infrastructure-as-Code specification
├── requirements.txt         # Pinned runtime dependencies
├── requirements.lock        # Reproducible dependency lockfile
├── requirements-dev.txt     # Test and lint tooling dependencies
├── code.html                # Responsive landing and login interface
├── code(1).html             # Consolidated banking and wealth dashboard
├── app.js                   # Client-side banking application logic
├── CMakeLists.txt           # C++ engine build configuration
├── LICENSE                  # MIT License with educational disclaimer
└── SECURITY.md              # Vulnerability reporting and security controls
```

---

## 4. Technology Stack

| Layer | Technologies |
| ----- | ------------ |
| **Backend Framework** | Python 3.11+, Flask 3.1, Werkzeug 3.1, Gunicorn 26.2 |
| **Database & ORM** | PostgreSQL 14+, SQLAlchemy 2.0, Alembic 1.18 |
| **Caching & Rate Limiting** | Redis 7.3 (with memory fallback) |
| **Cryptography & Security** | Argon2-cffi 25.1, Cryptography 46.0 (AES-GCM), Bcrypt 5.0 |
| **Reporting & Export** | ReportLab 4.4, BeautifulSoup4 4.14 |
| **High-Performance Engine** | C++14/C++20, MinGW-w64 / GCC |
| **Frontend UI** | HTML5, Modern JavaScript (ES6+), Tailwind CSS |
| **Container & CI/CD** | Docker, Docker Compose, GitHub Actions |

---

## 5. Installation & Local Development

### 5.1 Prerequisites
- Python 3.10+ (tested through Python 3.13)
- C++ Compiler (`g++` supporting C++14+)
- Optional: PostgreSQL 14+ and Redis 6+ (SQLite and memory fallbacks operate seamlessly in development mode)

### 5.2 Setup Steps

```bash
# 1. Clone repository
git clone https://github.com/nigam-30/Credence-Core.git
cd Credence-Core

# 2. Set up virtual environment
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your local settings if needed

# 5. Compile C++ high-performance engine (optional for benchmarks)
g++ -std=c++14 -Wall -Wextra main.cpp account.cpp credit.cpp debit.cpp fd.cpp loan.cpp report.cpp upi.cpp utils.cpp cheque.cpp globals.cpp -o bank_system

# 6. Apply database migrations
python scripts/run_migrations.py

# 7. Start local development server
gunicorn --config gunicorn_config.py "backend.app:create_app()"
```

Open your browser at `http://127.0.0.1:5000/`.

---

## 6. Automated Testing Suite

Credence Core includes a comprehensive regression test suite comprising 93 tests across 11 test modules:

```bash
# Run all tests
python -m pytest -v

# Run QA integration & stress tests only
python -m pytest tests/qa/ -v
```

### Test Coverage Areas
1. **Financial Integrity & Double-Entry Ledger**: Mathematical debit/credit balance, idempotency replay prevention, overdraft blocks.
2. **Database Migrations & Relational Schema**: 18 banking tables, foreign keys, check constraints, ACID rollbacks.
3. **Authentication & Session Security**: Argon2id hashing, session rotation, CSRF validation, brute-force lockouts.
4. **MFA Lifecycle**: Enrollment, TOTP verification, rate limits, secure recovery.
5. **Advanced Banking**: Loans, Fixed Deposits, SIP mutual funds, gold investments, disputes.
6. **Concurrency Stress & Race Conditions**: Multi-threaded transfers preventing negative balances.
7. **Disaster Recovery**: Automated database backup and restore validation.

---

## 7. Production Deployment

### Docker Deployment
```bash
# Build and run with PostgreSQL and Redis
docker-compose up --build -d

# Verify container health
curl -f http://localhost:5000/health/live
```

### Render.com Deployment
Credence Core includes native `render.yaml` Infrastructure-as-Code support:
1. Connect repository to Render.com.
2. Select **Blueprint** deployment.
3. Configure required environment variables:
   - `SECRET_KEY` (minimum 32 cryptographically random characters)
   - `MFA_ENCRYPTION_KEY` (minimum 32 cryptographically random characters, distinct from `SECRET_KEY`)
   - `DATABASE_URL` (PostgreSQL connection URI)
4. Deploy with automatic healthchecks at `/health/live`.

For complete deployment specifications, refer to [docs/deployment/DEPLOYMENT_GUIDE.md](docs/deployment/DEPLOYMENT_GUIDE.md).

---

## 8. Documentation Index

- **[docs/architecture/ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md)**: Architectural design principles and system decomposition.
- **[docs/architecture/API_INVENTORY.md](docs/architecture/API_INVENTORY.md)**: Complete catalog of REST API endpoints.
- **[docs/architecture/DATA_FLOW.md](docs/architecture/DATA_FLOW.md)**: End-to-end data lifecycle and financial state transitions.
- **[docs/database/DATABASE_SCHEMA.md](docs/database/DATABASE_SCHEMA.md)**: Relational schema, indices, and constraints.
- **[docs/database/FINANCIAL_INTEGRITY.md](docs/database/FINANCIAL_INTEGRITY.md)**: Double-entry accounting principles and reconciliation.
- **[docs/security/API_SECURITY_MATRIX.md](docs/security/API_SECURITY_MATRIX.md)**: Endpoint authorization and security controls matrix.
- **[docs/security/MFA_RELIABILITY.md](docs/security/MFA_RELIABILITY.md)**: Two-factor authentication architecture and error handling.
- **[docs/deployment/DEPLOYMENT_GUIDE.md](docs/deployment/DEPLOYMENT_GUIDE.md)**: Production deployment instructions for Docker and cloud platforms.
- **[docs/testing/QA_TEST_STRATEGY.md](docs/testing/QA_TEST_STRATEGY.md)**: Quality engineering and automated testing strategy.

---

## 9. Governance & License

- **License**: [MIT License](LICENSE) with Educational Simulator Disclaimer.
- **Security Policy**: [SECURITY.md](SECURITY.md).
- **Contributing Guidelines**: [CONTRIBUTING.md](CONTRIBUTING.md).
