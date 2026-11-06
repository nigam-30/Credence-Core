# CREDENCE CORE BANKING SYSTEM — PRODUCTION DEPLOYMENT RUNBOOK

**Target Version:** v1.0.0 (Release Candidate)  
**System Architecture:** Python Flask WSGI | SQLAlchemy ORM | PostgreSQL 16 / Redis 7  
**Platform Classification:** Demonstration, Educational & Staging Reference Platform  

> [!IMPORTANT]
> **REGULATORY DISCLOSURE & STATUTORY STATUS:**  
> Credence Core is an advanced demonstration, educational, and architectural reference platform. It is **NOT** an authorized banking institution, scheduled commercial bank, or licensed payment gateway. It does **NOT** hold authorization from the Reserve Bank of India (RBI), PCI Security Standards Council (PCI-DSS), or any national statutory financial regulator.  
> **Do not make unsubstantiated regulatory claims.** Commercial production deployment handling real fiat currency requires integration with banking partner switches, certified HSMs, PCI-DSS Level 1 third-party validation, and central bank licensing.
>
> **DEPLOYMENT READINESS VERDICT:**  
> **READY FOR STAGING, ISOLATED CLOUD PILOTS, AND HARDENED DEMO ENVIRONMENTS.**

---

## 1. External Service & Architecture Prerequisites

Credence Core requires external services to operate securely in high-concurrency environments:

| Component | Minimum Version | Production Specification | Provisioning Notes |
| :--- | :--- | :--- | :--- |
| **Primary Relational DB** | PostgreSQL 15+ (16 recommended) | Dedicated RDS/Cloud SQL/Render Postgres | Connection pooling, automated daily snapshots, WAL archiving |
| **Cache & Distributed Lock** | Redis 7.0+ | Standalone or Cluster with AOF persistence | Required for token revocation, rate limiting, and idempotency locks |
| **Compute / Application Tier** | Python 3.11–3.13 | Docker Engine 24+ / Linux Host | Non-root execution (`appuser:1000`), gunicorn multi-worker |
| **Persistent Storage** | Durable Volume | 10 GB+ mount for logs, statements, and backups | Backed by network storage (EBS/Persistent Disk) |

---

## 2. Environment Variables & Secret Configuration

Production startup **fails closed** if any critical secret is omitted or insecure:

| Variable | Type / Constraints | Description | Default / Example |
| :--- | :--- | :--- | :--- |
| `FLASK_ENV` | `production` (strict) | Enforces fail-closed security, disables debug/demo endpoints | `production` |
| `SECRET_KEY` | String (>=32 characters) | HMAC signing for secure cookies & session state | `openssl rand -hex 32` |
| `MFA_ENCRYPTION_KEY` | String (32 bytes base64) | AES-256-GCM symmetric key for user TOTP/MFA secrets | `openssl rand -base64 32` |
| `DATABASE_URL` | PostgreSQL URI | Primary ACID relational database URI | `postgresql://user:pass@host:5432/credence_bank` |
| `REDIS_URL` | Redis URI | Distributed cache, rate limiter & session store URI | `redis://:pass@host:6379/0` |
| `DATA_DIR` | Absolute Path | Writable directory for local statements & artifacts | `/var/data` |
| `LOG_DIR` | Absolute Path | Writable directory for structured audit & security logs | `/var/logs` |
| `PORT` | Integer | HTTP listener port | `5000` |
| `WEB_CONCURRENCY` | Integer | Gunicorn worker process count | `4` |
| `GUNICORN_THREADS` | Integer | Gunicorn threads per worker | `2` |

---

## 3. Deployment Environments & Runbooks

### 3.1 Cloud Deployment on Render (render.yaml Blueprint)

> [!WARNING]
> Render does **NOT** automatically provision Redis or background queue infrastructure unless explicitly declared or connected.

1. **Database:** Render provisions `credence-core-postgres` automatically through `render.yaml`.
2. **Redis:** A managed Redis instance (e.g. Render Redis, Upstash, or Redis Cloud) must be provisioned, and its connection string entered into `REDIS_URL` in the Render Environment Dashboard.
3. **Automated Migration Hook:** `render.yaml` executes `preDeployCommand: "alembic upgrade head"` prior to container launch, guaranteeing zero schema drift.
4. **Health Check Probing:** Render probes `healthCheckPath: /health/live`.

### 3.2 Docker Compose Multi-Container Orchestration

For self-hosted Linux servers or local staging clusters:

```bash
# 1. Clone repository and verify release tag
git clone <repository_url> /opt/credence-core
cd /opt/credence-core

# 2. Configure environment with strong random secrets
cat <<EOF > .env
FLASK_ENV=production
SECRET_KEY=$(openssl rand -hex 32)
MFA_ENCRYPTION_KEY=$(openssl rand -base64 32)
POSTGRES_USER=credence_admin
POSTGRES_PASSWORD=$(openssl rand -hex 24)
POSTGRES_DB=credence_bank
PORT=5000
WEB_CONCURRENCY=4
GUNICORN_THREADS=2
EOF
chmod 600 .env

# 3. Build and launch hardened containers
docker compose build --no-cache
docker compose up -d

# 4. Execute database schema migration
docker compose exec web alembic upgrade head

# 5. Verify service status and health probes
docker compose ps
curl -I http://127.0.0.1:5000/health/ready
```

---

## 4. Health Check Probing Specification

Credence Core implements dual Kubernetes/Docker-compatible health probes:

- **Liveness Probe (`GET /health/live`):**  
  Returns HTTP 200 `{"status": "alive"}` if the WSGI process and event loop are responsive. Use for container restart policies.
- **Readiness Probe (`GET /health/ready`):**  
  Returns HTTP 200 `{"status": "ready", "database": "connected", "redis": "connected"}` only when the primary PostgreSQL database and Redis cache are actively reachable. Returns HTTP 503 if downstream dependencies fail. Use for load balancer ingress routing.
- **Summary Probe (`GET /health` or `GET /api/health`):**  
  Comprehensive operational metric payload including memory and uptime.

---

## 5. Zero-Data-Loss Migration & Disaster Recovery

### 5.1 Database Schema Migrations
```bash
# Apply pending migrations deterministically
alembic upgrade head

# Check current revision
alembic current
```

### 5.2 Automated Backup Execution
```bash
# Snapshot database and verify SHA-256 integrity
python scripts/db_backup.py
```
Backups are archived in the configured persistent volume directory with timestamp and SHA-256 checksums.

### 5.3 Disaster Recovery Restoration
```bash
# 1. Gracefully stop application traffic
systemctl stop credence-core

# 2. Restore database snapshot
python scripts/db_restore.py --snapshot /var/backups/credence/credence_core_backup_<timestamp>.tar.gz

# 3. Verify ledger reconciliation
python -c "from backend.app.services.ledger.ledger_service import reconcile_all_accounts; print(reconcile_all_accounts())"

# 4. Resume traffic
systemctl start credence-core
```
