# Credence Core — Dependency & Supply Chain Audit
**Pinned vs Unpinned Dependency Analysis, Lockfile Verification & Vulnerability Posture**

> **Educational Project Notice:**
> Credence Core is an educational banking simulator and architectural demonstrator. This audit verifies software dependencies within the simulated environment.

---

## 1. Dependency Analysis: Unpinned vs Pinned Dependencies

Historically, `requirements.txt` contained unpinned dependencies (e.g. `flask`, `gunicorn`, `cryptography`), which exposed the system to build non-determinism, unexpected upstream breaking changes, and supply-chain vulnerabilities.

In Phase 6.3, two complementary dependency files were generated:
1. `requirements.txt`: Strictly pinned with exact semantic version qualifiers (`==`).
2. `requirements.lock`: Fully resolved, reproducible lockfile detailing every top-level package and all transitive dependencies with their exact installed versions.

---

## 2. Inventory of Pinned Dependencies

| Package | Pinned Version | Layer / Role | Security & Functional Justification |
| :--- | :---: | :--- | :--- |
| **Flask** | `3.1.0` | Core Web Framework | WSGI application layer, routing, and request context handling. |
| **Werkzeug** | `3.1.3` | WSGI Utility Layer | Secure cookie parsing, HTTP status codes, and proxy fix middleware. |
| **SQLAlchemy** | `2.0.36` | ORM & Relational Layer | Provides parameterized SQL statements, query builder, and relational row-level locking. |
| **psycopg2-binary** | `2.9.10` | Database Driver | PostgreSQL database connection driver for production cluster environments. |
| **argon2-cffi** | `23.1.0` | Cryptographic Authentication | Memory-hard password hashing engine resilient against GPU/ASIC brute-force attacks. |
| **cryptography** | `44.0.0` | Core Cryptography | AES-256-GCM authenticated encryption for MFA secrets and token management. |
| **pyotp** | `2.9.0` | Multi-Factor Authentication | RFC 6238 TOTP algorithm implementation for authenticator application compatibility. |
| **redis** | `5.2.1` | Distributed Caching | Connection pooling and distributed rate-limiting client. |
| **gunicorn** | `23.0.0` | Production WSGI Server | Multi-process worker management with access log formatting. |
| **pytest** | `9.0.2` | Test Harness | Multi-module automated test execution and regression suite. |

---

## 3. Transitive Dependency Audit & Vulnerabilities

A thorough examination of transitive dependencies was conducted:
- `cffi` (1.17.1) & `pycparser` (2.22): Required by `argon2-cffi` and `cryptography`. Verified free of known high-severity CVEs.
- `itsdangerous` (2.2.0): Used by Flask for signing cryptographically tamper-resistant session payloads.
- `jinja2` (3.1.5) & `markupsafe` (3.0.2): Template rendering engine with strict auto-escaping enabled to prevent Cross-Site Scripting (XSS).

No dependencies in `requirements.txt` or `requirements.lock` contain unresolved critical-severity CVEs in the active environment.

---

## 4. Security Posture of the Final Lockfile

1. **Deterministic Builds:** Containers built from `Dockerfile` install strictly from `requirements.txt` and `requirements.lock`, ensuring identical dependency graphs across local workstations, staging servers, and production clusters.
2. **Minimal Surface:** Extraneous development tools (e.g. documentation generators, linters) are separated from production runtime images.
3. **Supply-Chain Integrity:** Reproducible installs prevent opportunistic dependency hijacking or malicious patch releases from automatically entering deployment pipelines.
