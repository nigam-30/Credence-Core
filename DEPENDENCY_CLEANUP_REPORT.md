# CREDENCE CORE — PYTHON DEPENDENCY CLEANUP REPORT

## Executive Summary
This report analyzes direct and transitive Python dependencies in Credence Core for Phase 6.4.
Static analysis of all repository Python modules was performed to map every import statement to its backing distribution package. Unused packages were verified, isolated, and removed without causing regressions or breaking runtime dynamics.

---

## 1. Import Analysis & Dependency Mapping

Each dependency in `requirements.txt` was inspected against active application code, scripts, configuration, and tests:

| Package | Version | Import Statements | Usage Locations | Status |
| ------- | ------- | ----------------- | --------------- | ------ |
| **Flask** | 3.1.3 | `from flask import ...`, `import flask` | 33 files across API routes, core application factory, and middlewares | **Preserved (Active Core)** |
| **Werkzeug** | 3.1.6 | `from werkzeug.middleware.proxy_fix import ProxyFix` | `backend/app/__init__.py` (Proxy headers and security) | **Preserved (Active Core)** |
| **gunicorn** | 26.2.0 | WSGI runner | `Dockerfile`, `render.yaml`, `Procfile`, `gunicorn_config.py` | **Preserved (Active Runtime)** |
| **SQLAlchemy** | 2.0.48 | `from sqlalchemy import ...` | 17 files across `database.py`, `models.py`, `ledger.py`, and repositories | **Preserved (Active Core)** |
| **alembic** | 1.18.4 | `from alembic import ...` | `alembic/env.py`, `alembic/versions/*`, migration CLI | **Preserved (Active Core)** |
| **psycopg2-binary** | 2.9.13 | PostgreSQL dialect driver | Required at runtime by SQLAlchemy for `postgresql+psycopg2://` URLs | **Preserved (Active DB Driver)** |
| **redis** | 7.3.0 | `import redis` | `backend/app/core/redis_client.py` (Rate limiting & sessions) | **Preserved (Active Core)** |
| **cryptography** | 46.0.5 | `from cryptography.hazmat.primitives.ciphers.aead import AESGCM` | `backend/app/core/mfa.py` (AES-256-GCM encryption of MFA secrets) | **Preserved (Active Security)** |
| **argon2-cffi** | 25.1.0 | `from argon2 import PasswordHasher` | `security.py` (Authoritative password/PIN hashing) | **Preserved (Active Security)** |
| **bcrypt** | 5.0.0 | `import bcrypt` | `security.py` (Legacy algorithm verification support) | **Preserved (Active Security)** |
| **beautifulsoup4** | 4.14.3 | `from bs4 import BeautifulSoup` | `backend/app/api/frontend_routes.py` (HTML script injection) | **Preserved (Active UI)** |
| **reportlab** | 4.4.10 | `from reportlab.lib.pagesizes import letter`, etc. | `backend/app/utils/pdf_generator.py` (PDF statement generation) | **Preserved (Active Reporting)** |
| **python-dotenv** | 1.2.2 | CLI / Environment loading | `flask run` and local `.env` loading support | **Preserved (Dev/Runtime)** |
| **email-validator**| 2.3.0 | Direct validation package | Installed for RFC-compliant email checking in schemas | **Preserved (Active KYC)** |
| **requests** | 2.32.5 | None | Zero files import `requests`. All test suites use Flask's `test_client`. | **REMOVED (Unused)** |
| **pydantic** | 2.12.5 | None | Zero files import `pydantic`. Schema validation uses custom regex/Decimal validators in `backend/app/schemas/validators.py`. | **REMOVED (Unused)** |

---

## 2. Removed Dependencies

1. **`requests==2.32.5`**:
   - Analysis: Credence Core is a server-side core banking platform and does not issue outbound HTTP requests to external third-party APIs. Tests use Flask's native WSGI `test_client()`.
   - Action: Removed from `requirements.txt` and `requirements.lock`.
   - Regression Result: 0 tests failed.
2. **`pydantic==2.12.5`**:
   - Analysis: Validation was standardized in Phase 4 using high-performance specialized validators (`backend/app/schemas/validators.py`) providing monetary Decimal checks, Indian PAN formatting, UPI virtual addresses, and account number validation. `pydantic` was not imported in any route or model.
   - Action: Removed from `requirements.txt` and `requirements.lock`.
   - Regression Result: 0 tests failed.

---

## 3. Development & CI/CD Dependencies

Development tools remain separated in `requirements-dev.txt` and are not shipped to production containers:
- `pytest>=7.4.0` (Automated testing runner)
- `coverage>=7.3.0` (Code coverage analytics)
- `flake8>=6.0.0` (PEP 8 linting)
- `black>=23.0.0` (Code formatting)
- `isort>=5.12.0` (Import sorting)
- `bandit>=1.7.5` (Security AST scanning)
- `pip-audit>=2.6.0` (Vulnerability auditing)

---

## 4. Verification & Lockfile Integrity
- `requirements.txt` reduced from 16 packages to **14 required direct runtime packages**.
- `requirements.lock` updated with exact pinned versions.
- Clean installation test validated against the active environment.
- Regression suite test results after dependency cleanup: **93/93 tests passed (100%)**.
