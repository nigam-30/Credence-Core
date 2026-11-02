# Credence Core — Legacy Application Decommission Report
**Decommissioning of Monolithic `flask_app.py` & Migration to Canonical Factory**

> **Educational Project Notice:**
> Credence Core is an educational banking simulator and architectural demonstrator. This report describes architectural migrations within this codebase and does not represent an audit or compliance report for commercial banking software.

---

## 1. Context & Motivation

During Phases 0 through 4, the primary server file was `flask_app.py`, a 3,200-line monolithic script containing legacy JSON mutations, hardcoded demo profiles, plaintext credentials, and outdated routing mechanisms.

In Phase 5, the modular enterprise architecture was established under `backend/app/` with clean blueprints (`auth_routes`, `account_routes`, `transfer_routes`, `admin_routes`, etc.) and a canonical factory `backend.app:create_app()`. However, `flask_app.py` remained in the repository root for compatibility, introducing architectural confusion and residual security attack surfaces.

Phase 6.3 definitively resolves this legacy technical debt.

---

## 2. Inventory of Deprecated vs Migrated Routes

| Legacy Route in `flask_app.py` | Migrated Canonical Endpoint | Security & Invariant Benefit |
| :--- | :--- | :--- |
| `POST /login` (plaintext JSON matching) | `POST /api/auth/login` | Uses Argon2id password hashing, database session tracking, brute-force rate limits, and HttpOnly cookies. |
| `POST /transfer` (unvalidated mutation) | `POST /api/transfers` | Atomic double-entry ledger execution via `ledger_service`, idempotency checking, and frozen-account enforcement. |
| `POST /deposit` (direct balance update) | `POST /api/transfers/deposit` | Enforces double-entry pairing with General Ledger `GL_CASH_VAULT`. |
| `GET /api/user_info` (leaked demo hashes) | `GET /api/accounts/profile` | Strips all password and PIN hashes; validates session against active database token. |
| `POST /api/admin/set_role` | `POST /api/admin/users/<id>/role` | Strictly checks `User.role == 'admin'` in database; client-supplied role parameters are rejected. |
| Direct JSON file persistence (`bank_data.json`) | Relational SQLAlchemy (`models.py`) | Foreign key constraints, transaction atomicity, and ledger reconciliation invariants. |

---

## 3. Description of the New Thin Compatibility Layer

`flask_app.py` has been refactored from a 3,200-line monolith into a 115-line thin compatibility layer:

```python
"""
Credence Core — Legacy Compatibility Shim
DEPRECATION NOTICE:
This module is maintained strictly for backward compatibility with legacy scripts,
existing deployment configs, and integration test imports.
The canonical production application factory is `backend.app:create_app()`.
"""

import warnings
from backend.app import create_app
from backend.app.core.database import get_db

warnings.warn(
    "flask_app is deprecated and retained strictly as a backward-compatibility shim. "
    "Use backend.app:create_app() directly.",
    DeprecationWarning,
    stacklevel=2
)

# Canonical Flask application instance
app = create_app()

class LegacyBankShim:
    """Provides backward-compatibility method signatures for legacy scripts."""
    def get_report(self):
        # Queries canonical relational database for system health and ledger state
        ...
```

### Key Technical Guardrails:
1. **Emits `DeprecationWarning`:** Whenever imported, developers are explicitly warned that canonical usage requires `backend.app:create_app()`.
2. **Zero Independent Business Logic:** It contains no financial mutation logic, no independent route declarations, and no direct file I/O.
3. **Delegates to Canonical Factory:** `app = create_app()` ensures that all middleware, security headers, CORS policies, CSRF protections, and blueprints configured in the canonical factory are uniformly applied.

---

## 4. Verification of Security Flaw Elimination

| Historical Vulnerability | Legacy Behavior | Phase 6.3 State |
| :--- | :--- | :--- |
| **Hardcoded Demo Credentials** | Monolith initialized default demo user `40273146502136` with hardcoded PIN `1234`. | **Eliminated.** Zero credentials exist in source. Demo accounts are initialized via migration scripts with Argon2id hashes. |
| **Unauthenticated File Mutations** | Routes wrote directly to `user_profiles.json` without verifying session state. | **Eliminated.** All writes execute through authenticated SQLAlchemy sessions backed by relational ACID constraints. |
| **Bypass of Security Middleware** | Legacy routes missed security headers (CSP, HSTS, X-Content-Type-Options). | **Eliminated.** Because the shim exposes `create_app()`, all requests pass through enterprise security header decorators. |

---

## 5. Recommended Timeline for Complete Removal

1. **Phase 6.3 (Current):** Thin compatibility shim active; all deployment scripts (Dockerfile, Procfile, Render) migrated to `backend.app:create_app()`.
2. **Next Release (v2.1):** Update external integration test imports to point directly to `backend.app`.
3. **Final Cleanup (v3.0):** Complete physical deletion of `flask_app.py` from repository root.
