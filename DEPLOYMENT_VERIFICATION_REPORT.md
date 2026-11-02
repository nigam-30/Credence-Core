# Credence Core — Deployment Verification Report
**Multi-Target Deployment Consistency: Docker, Docker Compose, Render & Procfile**

> **Educational Project Notice:**
> Credence Core is an educational banking simulator and architectural demonstrator. This report verifies deployment topologies and container configurations for engineering assessment.

---

## 1. Unified Canonical Application Factory

Across all supported deployment targets, `backend.app:create_app()` has been established as the single canonical WSGI application factory. All legacy references to standalone development servers or ad-hoc scripts have been removed.

---

## 2. Target-by-Target Verification

### A. Docker Container (`Dockerfile`)
- **Base Image:** `python:3.11-slim` with multi-stage build dependencies (`g++`, `build-essential`, `curl`).
- **Non-Root Execution:**
  - Dedicated system group and user created: `groupadd -g 1000 appgroup && useradd -u 1000 -g appgroup -m appuser`.
  - Directory ownership set: `chown -R appuser:appgroup /app`.
  - Process runs as `USER appuser` (UID 1000), eliminating root privilege escalation risks inside the container.
- **Healthcheck Probe:**
  ```dockerfile
  HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:5000/health/live || exit 1
  ```
- **Entrypoint:** `CMD ["gunicorn", "--config", "gunicorn_config.py", "backend.app:create_app()"]`.

### B. Docker Compose (`docker-compose.yml`)
- **Topology:** 3-tier micro-topology:
  1. `db`: PostgreSQL 16 Alpine with healthcheck (`pg_isready`).
  2. `redis`: Redis 7 Alpine with healthcheck (`redis-cli ping`).
  3. `web`: Credence Core web application depending on `db` and `redis` healthy states.
- **Environment Invariants:** Enforces mandatory provision of `POSTGRES_PASSWORD`, `SECRET_KEY`, and `MFA_ENCRYPTION_KEY` using Docker Compose required syntax (`:?Error: ...`).
- **Network Isolation:** Internal private bridge network `credence_internal_net`.

### C. PaaS & Render (`Procfile` & `render.yaml`)
- **`Procfile`:**
  ```procfile
  web: gunicorn --config gunicorn_config.py "backend.app:create_app()"
  ```
- **`render.yaml`:**
  ```yaml
  services:
    - type: web
      name: credence-core
      env: python
      buildCommand: "pip install -r requirements.txt && g++ main.cpp account.cpp credit.cpp debit.cpp fd.cpp loan.cpp report.cpp upi.cpp utils.cpp cheque.cpp globals.cpp -o bank_system"
      startCommand: "gunicorn --config gunicorn_config.py 'backend.app:create_app()'"
      healthCheckPath: /health/live
      envVars:
        - key: PYTHON_VERSION
          value: 3.11.0
  ```

---

## 3. Environment Variable Validation & Fail-Fast Guarantees

In `backend/app/core/config.py`:
- `SECRET_KEY`: Must be defined and contain >= 32 characters of entropy in production mode.
- `MFA_ENCRYPTION_KEY`: Must decode to 32 bytes (256 bits). Absence in production raises `RuntimeError` immediately during application factory bootstrap, terminating execution before accepting incoming traffic.
- `DATABASE_URL`: Must be an explicit PostgreSQL or tested SQLite URI.
- `SESSION_COOKIE_SECURE`: Enforces `True` when running under HTTPS or production mode.
