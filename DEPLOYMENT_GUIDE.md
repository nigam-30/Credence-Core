# Credence Core — Deployment & Infrastructure Guide (Phase 6.1)

**Role:** Principal DevOps & Financial Systems Architect  
**Version:** 6.1.0 (Remediated Architecture & Hardened Security)  
**Target Environments:** Local Developer Workstation, Hardened Docker Compose, Managed Cloud Blueprint (Render.com), Kubernetes / Cloud VMs  

---

## 1. Architectural Overview & Single Source of Truth

In Phase 6.1, Credence Core eliminated the dual-ledger architecture. PostgreSQL is now the single, canonical financial source of truth for both customer account balances and double-entry ledger journals. SQLite is strictly confined to isolated development and testing environments; automatic fallback to SQLite in production has been eradicated.

> [!CAUTION]
> **Production Database Fast-Fail:** In `production` mode (`FLASK_ENV=production`), application startup will immediately terminate with `SystemExit(1)` if `DATABASE_URL` points to SQLite or if the PostgreSQL database is unreachable.

### System Topology
```mermaid
flowchart TD
    CLIENT["Client Browser / Mobile PWA"] -->|HTTPS 443 / TLS 1.3| LB["Trusted Reverse Proxy (Render / Nginx / Cloudflare)"]
    LB -->|Reverse Proxy / HTTP 5000<br/>ProxyFix Header Normalization| APP["Credence Core App (Gunicorn Non-Root Container UID 10001)"]
    APP -->|TCP 5432 / SQLAlchemy Pool| PG[("Single Canonical DB: PostgreSQL 16<br/>(Accounts, Balances, Ledger, Audit, Sessions)")]
    APP -->|TCP 6379| REDIS[("Redis 7 Cache<br/>(Distributed Rate Limiting & Account Lockouts)")]
    APP -->|Write-Ahead Mount| LOGS[("Structured Audit & Security Logs (/app/logs)")]

    subgraph Persistent Production Storage
        PG
        REDIS
        LOGS
    end
```

---

## 2. Infrastructure Configuration & Deployment Modes

### 2.1 Production-Grade Gunicorn (`gunicorn_config.py`)
Credence Core leverages Gunicorn with multi-threaded asynchronous workers (`gthread`) behind reverse proxies:
- **Worker Scaling:** Configurable via `WEB_CONCURRENCY`, defaulting to $(2 \times \text{CPUs}) + 1$.
- **Thread Multiplier:** 2–4 worker threads per process (`GUNICORN_THREADS=2`).
- **Worker Recycling:** `max_requests = 1000` with `max_requests_jitter = 50` to eliminate memory leaks.
- **Request Constraints:** Strict limits on request line length (4096 bytes) and header fields (100 headers, max 8KB).
- **Structured JSON Access Logs:** Emits single-line JSON records formatted with `remote_ip`, `duration_us`, `status`, and `uri` directly to `stdout`.

### 2.2 Hardened Multi-Stage Docker Build (`Dockerfile`)
- **Stage 1 (`builder`):** `python:3.11-slim` with GCC toolchain and C++ core compilation (`-O3 -std=c++17`).
- **Stage 2 (`runtime`):** Minimal runtime stripped of build compilers.
- **Non-Root Execution:** Dedicated system group `appgroup` (GID 10001) and user `appuser` (UID 10001).
- **Persistent Volumes:** `/app/data` (transient artifacts) and `/app/logs` (persistent audit trails).

---

## 3. Secret Management & Environment Security

### 3.1 Strict Production Startup Validation
The application factory enforces strict cryptographic rules in `production`:
1. `SECRET_KEY` must be set and $\ge 32$ characters in length.
2. `SECRET_KEY` must **not** match known insecure or sample keys (e.g., `dev_secret_key_fixed_for_testing`, `production_secret_key_change_me_immediately_in_real_env!`).
3. `DATABASE_URL` credentials are masked in all application logging (`postgresql://credence_user:***@db:5432/credence_core`).
4. Known default production passwords (such as `CredenceSecurePass2026!`) have been removed from configuration templates and Docker Compose files.

### 3.2 Required Environment Variables Matrix

| Variable | Required in Prod | Default / Example | Security Requirement |
| :--- | :--- | :--- | :--- |
| `FLASK_ENV` | **Yes** | `production` | Enables strict secret checks, HTTPS cookies, and PostgreSQL enforcement. |
| `SECRET_KEY` | **Yes** | *None* (Must supply) | Cryptographically random string $\ge 32$ characters (`openssl rand -hex 32`). |
| `DATABASE_URL` | **Yes** | *None* | Must be a PostgreSQL URI (`postgresql://user:pass@host:5432/dbname`). |
| `POSTGRES_USER` | **Yes** (Docker) | `credence_user` | Non-default production database username. |
| `POSTGRES_PASSWORD`| **Yes** (Docker) | *Mandatory Env Var* | Strong password (`openssl rand -base64 24`). Docker Compose throws error if missing. |
| `POSTGRES_DB` | **Yes** (Docker) | `credence_core` | Database catalog name. |
| `REDIS_URL` | Optional (Prod) | `redis://localhost:6379/0` | Connection string for distributed rate limiting & lockout tracking. |
| `DATA_DIR` | Yes | `/app/data` | Persistent container volume mount. |
| `LOG_DIR` | Yes | `/app/logs` | Persistent container volume mount for audit logs. |
| `PORT` | Optional | `5000` | Port listened to by Gunicorn. |
| `SESSION_COOKIE_SECURE` | Yes | `true` | Enforces HTTPS-only transmission. |

---

## 4. Deployment Procedures

### 4.1 Controlled Deployment Step (Database Migrations)
Database schema migrations must execute via the controlled pre-deployment runner before launching web worker processes:
```bash
python scripts/run_migrations.py
```
This script executes:
1. PostgreSQL connectivity check with retry backoff.
2. Schema materialization and schema migration (including MFA and session tables).
3. Mathematical double-entry ledger reconciliation verification.

### 4.2 Docker Compose Production Deployment
1. Create `.env` file with unique secrets:
   ```bash
   export POSTGRES_PASSWORD=$(openssl rand -base64 24)
   export SECRET_KEY=$(openssl rand -hex 32)
   ```
2. Start the cluster:
   ```bash
   docker compose up -d --build
   ```
   Docker Compose will validate `${POSTGRES_PASSWORD:?Error: POSTGRES_PASSWORD must be set in environment}` before creating containers.
3. Verify running services:
   ```bash
   docker compose ps
   # Services: db (PostgreSQL 16), redis (Redis 7), web (Credence Core)
   ```

### 4.3 Cloud Blueprint Deployment (Render.com)
The platform includes an automated `render.yaml` infrastructure-as-code blueprint:
- **Web Service:** `credence-core-web` running Docker environment.
- **Database Service:** Managed PostgreSQL `credence-postgres` (PostgreSQL 16).
- **Pre-Deploy Command:** `python scripts/run_migrations.py`.
- **Serverless Notice:** Deprecated `vercel.json` has been removed; serverless deployment cannot satisfy ACID durability or persistent background auditing requirements.

### 4.4 Reverse Proxy & Trusted Proxy Configuration
Credence Core utilizes Werkzeug's `ProxyFix` middleware configured for 1 trusted reverse proxy layer (`x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1`). Client IP addresses are correctly resolved from the `X-Forwarded-For` header for distributed rate limiting and security audit logs.

---

## 5. Health Probes & Monitoring

- **Liveness Probe (`GET /health/live`):** Returns HTTP 200 `{"status": "UP"}`.
- **Readiness Probe (`GET /health/ready`):** Validates primary PostgreSQL connectivity (`SELECT 1`), C++ binary execution, and disk permissions. Returns HTTP 200 `{"status": "READY"}` or HTTP 503 `{"status": "NOT_READY"}`.
- **Prometheus Metrics (`GET /api/metrics`):** Emits throughput, status codes, latency percentiles, and database pool statistics.

---

## 6. Implementation & Verification Status

| Deployment Requirement | Status | Verification Evidence |
| :--- | :--- | :--- |
| **Eliminate SQLite fallback in production** | **Implemented & Tested** | `ProductionConfig.validate_database()` exits if SQLite detected. Tested in `tests/test_phase6_1_remediation.py`. |
| **Strict production SECRET_KEY validation** | **Implemented & Tested** | Fast-fail on weak (<32 char) or default keys. Tested in `tests/test_phase6_1_remediation.py`. |
| **Mandatory PostgreSQL password in Docker** | **Implemented & Tested** | Enforced in `docker-compose.yml` via `${POSTGRES_PASSWORD:?Error...}`. |
| **Mask credentials in logs** | **Implemented & Tested** | `mask_database_url()` strips user/password before emitting connection strings. |
| **Distributed Rate Limiting via Redis** | **Implemented & Tested** | Redis sliding-window implementation in `security.py` with in-memory thread-safe fallback. |
| **Render Blueprint with Pre-Deploy Migration** | **Implemented** | Configured in `render.yaml` referencing `scripts/run_migrations.py`. |
| **Trusted Reverse Proxy Handling** | **Implemented** | Configured via `ProxyFix` in `backend/app/__init__.py`. |
| **Removal of serverless config (vercel.json)** | **Implemented** | Removed via Git. |

### Remaining Risks & Operational Notice
> [!NOTE]
> - **Production SSL Termination:** TLS certificates must be terminated at the edge reverse proxy (e.g. AWS ALB, Cloudflare, or Nginx).
> - **Database Backups:** Production PostgreSQL instances should configure automated WAL archiving (e.g., pgBackRest or AWS RDS Automated Snapshots) in addition to logical snapshots.
> - **Educational Notice:** Credence Core is an educational and architectural simulation platform. It is not certified for PCI-DSS compliance, RBI compliance, or live Core Banking Systems (CBS).
