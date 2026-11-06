# Credence Core — Institutional Digital Banking & Wealth Terminal

[![Core Engine](https://img.shields.io/badge/CORE%20ENGINE-C%2B%2B14%2F20-00599C?style=for-the-badge&logo=c%2B%2B&logoColor=white)](https://github.com/nigam-30/Credence-Core)
[![Backend](https://img.shields.io/badge/BACKEND-PYTHON%20FLASK-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://github.com/nigam-30/Credence-Core)
[![Database](https://img.shields.io/badge/DATABASE-POSTGRESQL%20%7C%20ALEMBIC-336791?style=for-the-badge&logo=postgresql&logoColor=white)](https://github.com/nigam-30/Credence-Core)
[![Cache](https://img.shields.io/badge/CACHE-REDIS%207-DC382D?style=for-the-badge&logo=redis&logoColor=white)](https://github.com/nigam-30/Credence-Core)
[![UI Framework](https://img.shields.io/badge/UI-TAILWIND%20CSS-06B6D4?style=for-the-badge&logo=tailwindcss&logoColor=white)](https://github.com/nigam-30/Credence-Core)
[![Security](https://img.shields.io/badge/SECURITY-ARGON2ID%20%26%20MFA-22C55E?style=for-the-badge&logo=shield&logoColor=white)](https://github.com/nigam-30/Credence-Core)
[![Tests](https://img.shields.io/badge/TESTS-138%20PASSING%20(100%25)-success?style=for-the-badge&logo=pytest&logoColor=white)](https://github.com/nigam-30/Credence-Core)
[![Deployment](https://img.shields.io/badge/DEPLOYMENT-MULTI--STAGE%20DOCKER-46E3B7?style=for-the-badge&logo=docker&logoColor=white)](https://github.com/nigam-30/Credence-Core)

> **⚠️ EDUCATIONAL SIMULATION DISCLAIMER**  
> **Credence Core is an academic and educational simulation platform engineered solely to demonstrate core banking architectures, double-entry financial ledgers, ACID transaction atomicity, and institutional security controls.**  
> - **Do not enter real banking credentials, real debit/credit card numbers, actual government IDs (PAN/Aadhaar/SSN), or live personal sensitive data.**
> - Use only fictional test credentials and synthetic demo data.
> - Credence Core is **not a regulated bank, depository institution, or licensed payment operator**, and does not interface with central clearing switches (e.g., SWIFT, Fedwire, NPCI).

---

## 1. Project Overview

**Credence Core** is an enterprise-grade digital banking and wealth terminal simulation engineered with strict financial invariants, cryptographic security, and multi-cloud container portability.

The platform simulates modern retail banking, wealth management, fixed-income instruments, retail lending, and general ledger operations. Built on a modular layered architecture, Credence Core features a high-performance C++ ledger engine coupled with a Python WSGI backend, PostgreSQL transactional storage, Redis caching and distributed lock coordination, and a responsive frontend interface.

---

## 2. Key Features & Banking Workflows

### 2.1 Core Banking & Account Management
* **Automated Customer Onboarding:** Instant creation of customer profiles with cryptographically verified 14-digit account numbers and balanced initial ledger deposits.
* **Masked Balance & PIN Unlocking:** Account balances are masked by default (`••••••`) and securely unlocked via server-verified PIN verification without client-side state tampering.
* **Multi-Currency Precision:** Fixed-precision integer storage (paise / cents) to prevent floating-point rounding errors across all balances and ledger entries.

### 2.2 Financial Ledger & Payment Rails
* **Double-Entry Equilibrium:** Every transaction generates equal and offsetting debit and credit legs; total debits strictly equal total credits ($\sum \text{Debits} = \sum \text{Credits}$).
* **ACID Overdraft Protection:** Atomic balance checks with database-level row locking (`SELECT FOR UPDATE`) to eliminate race conditions during concurrent transfers or ATM withdrawals.
* **Idempotency Deduplication:** Deterministic idempotency key handling prevents double-execution on network retries.
* **Unified Payment Rails:** Simulated instant payment workflows supporting IMPS, NEFT, RTGS, and UPI Virtual Payment Address (VPA) registration (`{account}@credence`).

### 2.3 Wealth, Investments & Lending
* **High-Yield Fixed Deposits (FD):** Term deposit origination with annual yield calculations and premature liquidation workflows.
* **Systematic Investment Plans (SIP):** Automated mutual fund SIP subscriptions with custom monthly debits and portfolio tracking.
* **Digital Gold Trading:** Spot gold purchasing and liquidation with real-time gram weight and valuation tracking.
* **Retail Loan Origination:** Automated credit assessment, CIBIL score validation, and loan installment tracking.

### 2.4 Enterprise Security & Observability
* **Argon2id & PBKDF2 Password Hashing:** Cryptographic password storage resistant to GPU/ASIC cracking.
* **Double-Submit CSRF Defense:** Cookie-to-header token validation on all mutating HTTP methods (`POST`, `PUT`, `DELETE`, `PATCH`).
* **Session Lifecycle & Database Rotation:** Session tokens are hashed with SHA-256 and verified against database records on every request, with sliding expiration and server-side revocation.
* **Server-Side RBAC & BOLA/IDOR Defenses:** Context-bound authorization preventing cross-account access and privilege escalation.
* **Standardized Observability:** Sanitized liveness (`/health/live`) and readiness (`/health/ready`) health checks without exposing internal system internals.

---

## 3. Technology Stack

* **Core Ledger Engine:** C++14/20 high-performance engine for microsecond ledger operations.
* **Web & API Backend:** Python 3.11 / 3.13, Flask, Gunicorn WSGI.
* **Database & ORM:** PostgreSQL 15+ (Production) / SQLite with Golden In-Memory Snapshot Isolation (Testing), SQLAlchemy 2.0, Alembic Migrations.
* **Cache & Rate Limiting:** Redis 7.0+ (Distributed locks, brute-force lockout counters, sliding-window IP rate limiting).
* **Frontend:** Semantic HTML5, Tailwind CSS, Vanilla JavaScript (zero external node_modules build dependencies).
* **Testing & Quality Assurance:** Pytest 9.0+, Selenium WebDriver 4.52+ with Headless Google Chrome, Faker.
* **Containerization:** Multi-stage OCI-compliant Dockerfile executing as non-root user `appuser` (UID 10001).

---

## 4. Project Architecture & Repository Structure

```
bank_system_clean/
├── Dockerfile                   # Multi-stage production OCI container specification
├── docker-compose.yml           # Production Docker Compose (Web, PostgreSQL, Redis)
├── gunicorn_config.py           # Gunicorn WSGI configuration with dynamic $PORT binding
├── requirements.lock            # Fully resolved, reproducible dependency lockfile
├── requirements.txt             # Primary Python dependency specifications
├── alembic.ini                  # Alembic database migration configuration
├── alembic/                     # Database migration revisions
│   ├── env.py                   # Migration environment runner
│   └── versions/                # Versioned schema migration scripts
├── backend/                     # Modular backend package
│   └── app/
│       ├── __init__.py          # Flask application factory (create_app)
│       ├── api/                 # Blueprint controllers (auth, accounts, transfers, etc.)
│       ├── core/                # Configuration, security utilities, database setup
│       ├── middleware/          # CSRF, authentication, error handling, rate limiting
│       ├── models/              # Domain models (User, Account, LedgerEntry, etc.)
│       ├── repositories/        # Database access layer and query abstractions
│       └── services/            # Business logic (ledger, auth, transfers, investments)
├── docs/                        # Architecture documentation, runbooks, and test reports
│   ├── FINAL_RELEASE_REPORT.md  # Official release freeze audit and signatures
│   ├── FINAL_TEST_RESULTS.md    # Complete test logs and 15 DOM journey results
│   ├── FINAL_HOSTING_COMPATIBILITY_MATRIX.md  # 14-platform deployment matrix
│   ├── FINAL_DEPLOYMENT_GUIDE.md# Operational runbook and deployment guide
│   ├── FINAL_RELEASE_MANIFEST.sha256 # Cryptographic release checksum manifest
│   └── screenshots/             # 15 High-resolution DOM agent test screenshots
├── scripts/                     # Operational scripts (packaging, validation, backup)
│   ├── package_release.py       # Deterministic release packaging tool
│   ├── validate_release_package.py # Packaging hygiene and checksum gate
│   ├── db_backup.py             # Database backup utility
│   └── db_restore.py            # Database restore utility
├── tests/                       # Complete automated regression test suite
│   ├── conftest.py              # Golden in-memory database isolation fixture
│   ├── test_database_isolation.py # PostgreSQL host security & per-test isolation
│   ├── test_dom_agent_journeys.py # 15 Real headless Chrome DOM browser journeys
│   ├── test_financial_integrity.py# Double-entry balance invariant & overdraft tests
│   └── qa/                      # Penetration, load, concurrency, and API tests
├── code.html                    # Public landing page & login portal
├── code(1).html                 # Authenticated customer banking dashboard
├── app.js                       # Frontend client-side controller & fetch interceptor
├── wsgi.py                      # Application entrypoint for WSGI servers
└── LICENSE                      # MIT License and Educational Disclaimer
```

---

## 5. Prerequisites & Dependencies

Before running or deploying Credence Core, ensure the following tools are installed:

* **Python:** Version 3.11 or 3.13
* **Git:** Version 2.40+
* **Container Engine (Optional but Recommended):** Docker Engine 24.0+ and Docker Compose v2+
* **Primary Database:** PostgreSQL 15+ (Production) or local SQLite (Testing only)
* **Distributed Cache:** Redis 7.0+
* **Browser Test Prerequisite (Optional):** Google Chrome and ChromeDriver (managed automatically via Selenium)

---

## 6. Installation & Local Development Setup

### Step 1: Clone Repository
```bash
git clone https://github.com/nigam-30/Credence-Core.git
cd Credence-Core
```

### Step 2: Create and Activate Virtual Environment
```bash
# On Linux / macOS:
python3 -m venv venv
source venv/bin/activate

# On Windows (PowerShell):
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### Step 3: Install Locked Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.lock
```

### Step 4: Environment Variable Configuration
Copy the provided `.env.example` file to create your local `.env`:
```bash
cp .env.example .env
```

Review and adjust the configuration parameters:

| Variable | Description | Default / Example Value |
|---|---|---|
| `FLASK_ENV` | Application environment (`production` or `development`) | `development` |
| `PORT` | HTTP port for server binding | `5000` |
| `WORKERS` | Number of Gunicorn worker processes | `4` |
| `DATABASE_URL` | PostgreSQL or test SQLite connection string | `postgresql://credence_user:password@localhost:5432/credence_core` |
| `REDIS_URL` | Redis server connection string | `redis://localhost:6379/0` |
| `SECRET_KEY` | High-entropy secret for cryptographic signing | `Generate using: python -c "import secrets; print(secrets.token_hex(32))"` |
| `SESSION_SECRET` | Secret key for Flask session cookie encryption | `Generate using: python -c "import secrets; print(secrets.token_hex(32))"` |
| `SESSION_COOKIE_SECURE`| Enforce HTTPS-only transmission for session cookies | `false` (Local) / `true` (Production) |

### Step 5: Execute Database Migrations
Initialize the database schema to the latest Alembic revision:
```bash
python -m alembic upgrade head
```

### Step 6: Start Local Development Server
```bash
python wsgi.py
```
The application will be accessible at `http://127.0.0.1:5000`.

---

## 7. Docker Deployment Instructions

### 7.1 Multi-Stage Production Build
Credence Core utilizes a multi-stage Docker build that isolates compiler toolchains in the builder stage and produces a hardened, minimal runtime image running as non-root user `appuser`:

```bash
docker build -t credence-core:v1.0.0 .
```

### 7.2 Run Database Migrations in Container
```bash
docker run --rm \
  -e DATABASE_URL="postgresql://credence_user:SecretDbPass2026@postgres-host:5432/credence_core" \
  credence-core:v1.0.0 \
  python -m alembic upgrade head
```

### 7.3 Run Standalone Container
```bash
docker run -d \
  --name credence-core \
  --restart always \
  -p 5000:5000 \
  -e FLASK_ENV=production \
  -e PORT=5000 \
  -e WORKERS=4 \
  -e DATABASE_URL="postgresql://credence_user:SecretDbPass2026@postgres-host:5432/credence_core" \
  -e REDIS_URL="redis://:SecretRedisPass2026@redis-host:6379/0" \
  -e SECRET_KEY="your-high-entropy-production-secret-key" \
  -e SESSION_SECRET="your-high-entropy-session-secret-key" \
  -e SESSION_COOKIE_SECURE="true" \
  credence-core:v1.0.0
```

### 7.4 Production Deployment via Docker Compose
To deploy the entire production stack (Web Application, PostgreSQL 15, and Redis 7) with health checks and persistent volumes:

```bash
docker compose up -d
```

---

## 8. Health Check Endpoints

Standardized health endpoints provide zero-leakage observability for container orchestrators (Kubernetes, AWS ECS, Google Cloud Run):

### Liveness Probe (`/health/live`)
Confirms that the WSGI process and HTTP listener are operational:
```bash
curl -i http://localhost:5000/health/live
```
```http
HTTP/1.1 200 OK
Content-Type: application/json

{"status": "alive"}
```

### Readiness Probe (`/health/ready`)
Verifies external dependencies (PostgreSQL and Redis) without exposing internal paths or connection credentials:
```bash
curl -i http://localhost:5000/health/ready
```
```http
HTTP/1.1 200 OK
Content-Type: application/json

{"database": "connected", "redis": "connected", "status": "ready"}
```

---

## 9. Automated Testing Suite

Credence Core includes an exhaustive test suite covering unit tests, integration contracts, financial invariants, database isolation, and real headless Chrome DOM browser automation.

### Run All 138 Automated Tests
```bash
python -m pytest -v
```

### Run Real DOM Browser Agent Journeys (Selenium + Chrome)
Executes 15 real user journeys with DOM element interaction and screenshot capture:
```bash
python -m pytest tests/test_dom_agent_journeys.py -v
```

### Run Database Isolation & Host Security Suite
Validates PostgreSQL host allowlists, port boundaries, and per-test snapshot rollback:
```bash
python -m pytest tests/test_database_isolation.py -v
```

### Run Financial Integrity & Ledger Invariant Tests
Validates double-entry balance equilibrium and concurrent overdraft prevention:
```bash
python -m pytest tests/test_financial_integrity.py -v
```

---

## 10. Visual Interface & Screenshots

Real DOM agent browser automation validates and captures high-resolution visual evidence across all key user journeys:

| Journey | Interface Workflow | Screenshot Reference |
|---|---|---|
| **01** | Verified Customer Registration Modal | [`docs/screenshots/01_customer_registration.png`](docs/screenshots/01_customer_registration.png) |
| **02** | Authenticated Dashboard Overview | [`docs/screenshots/02_valid_login_dashboard.png`](docs/screenshots/02_valid_login_dashboard.png) |
| **04** | PIN-Protected Clear Balance Reveal | [`docs/screenshots/04_balance_reveal.png`](docs/screenshots/04_balance_reveal.png) |
| **05** | Instant Deposit & Ledger Credit | [`docs/screenshots/05_deposit_success.png`](docs/screenshots/05_deposit_success.png) |
| **07** | Account-to-Account Transfer Execution | [`docs/screenshots/07_transfer_success.png`](docs/screenshots/07_transfer_success.png) |
| **11** | Fixed Deposit & Mutual Fund SIP Panel | [`docs/screenshots/11_fixed_deposit_and_sip.png`](docs/screenshots/11_fixed_deposit_and_sip.png) |
| **12** | Retail Loan Origination Application | [`docs/screenshots/12_loan_application.png`](docs/screenshots/12_loan_application.png) |
| **15** | Mobile Viewport Responsive Layout (375x812) | [`docs/screenshots/15_responsive_mobile_dashboard.png`](docs/screenshots/15_responsive_mobile_dashboard.png) |

---

## 11. Known Limitations & Regulatory Disclaimer

1. **Academic Simulation Only:** Credence Core is designed exclusively for software architecture demonstration, financial systems research, and security engineering benchmarks. It does not possess a banking license, regulatory charter, or authorization from any monetary authority (e.g., RBI, FDIC, ECB).
2. **Mock Payment Networks:** External payment rails (IMPS, UPI, NEFT) are simulated within the canonical double-entry ledger and do not connect to external financial switches.
3. **Serverless Limitations:** The core banking engine requires stateful connection pooling and continuous memory context; serverless environments (e.g., Vercel / AWS Lambda) are unsupported for the core ledger. Use containerized deployments (Docker, ECS, Cloud Run) as specified in [`docs/FINAL_HOSTING_COMPATIBILITY_MATRIX.md`](docs/FINAL_HOSTING_COMPATIBILITY_MATRIX.md).

---

## 12. License & Governance

This project is licensed under the terms of the **MIT License**. See the [`LICENSE`](LICENSE) file for complete details.

Copyright (c) 2026 Credence Core Contributors. All rights reserved.
