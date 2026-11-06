# CREDENCE CORE BANKING SYSTEM — FINAL DEPLOYMENT GUIDE
**Release Version:** v1.0.0-Release  
**Classification:** Operational Runbook & Production Deployment Guide  

---

## 1. System Requirements & Prerequisites

### 1.1 Infrastructure Requirements
* **Container Runtime:** Docker Engine 24.0+ / Podman 4.5+
* **Primary Database:** PostgreSQL 15 or 16 (Managed AWS RDS, Google Cloud SQL, Azure Database, or standalone)
* **Distributed Cache & Locks:** Redis 7.0+ (AWS ElastiCache, Memorystore, or standalone)
* **Compute Minimums:** 2 vCPU, 2 GB RAM (Production baseline: 4 vCPU, 8 GB RAM per instance)

### 1.2 Required Environment Variables

```ini
# Core Environment
FLASK_ENV=production
DEBUG=false
PORT=5000
WORKERS=4

# Cryptographic Keys (Must be high-entropy, >= 64 characters)
SECRET_KEY=9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d3e2f1a0b9c8d7e6f5a4b3c2d1e0f9a8b
SESSION_SECRET=1f2e3d4c5b6a7f8e9d0c1b2a3f4e5d6c7b8a9f0e1d2c3b4a5f6e7d8c9b0a1f2e

# Database Configuration (PostgreSQL is required in production)
DATABASE_URL=postgresql://credence_user:StrongPassword2026!@postgres-host:5432/credence_core

# Redis Configuration (For multi-worker rate limiting and distributed locks)
REDIS_URL=redis://:RedisPassword2026!@redis-host:6379/0

# Security & Cookies
SESSION_COOKIE_SECURE=true
SESSION_COOKIE_HTTPONLY=true
SESSION_COOKIE_SAMESITE=Lax
PERMANENT_SESSION_LIFETIME=1800
MAX_LOGIN_ATTEMPTS=5
LOCKOUT_DURATION_SECONDS=900
```

---

## 2. Standard Container Deployment (Docker CLI)

### 2.1 Building the OCI Image
From the repository root:
```bash
docker build -t credence-core:v1.0.0 .
```

### 2.2 Executing Database Migrations
Always run schema migrations before cutting traffic over to new container instances:
```bash
docker run --rm \
  -e DATABASE_URL="postgresql://credence_user:StrongPassword2026!@postgres-host:5432/credence_core" \
  credence-core:v1.0.0 \
  python -m alembic upgrade head
```

### 2.3 Running the Application Container
```bash
docker run -d \
  --name credence-core \
  --restart always \
  -p 5000:5000 \
  --env-file /etc/credence/production.env \
  credence-core:v1.0.0
```

---

## 3. Production Deployment with Docker Compose

For standalone VPS, dedicated hardware, or development staging:

```yaml
version: '3.8'

services:
  web:
    image: credence-core:v1.0.0
    restart: always
    ports:
      - "5000:5000"
    environment:
      - FLASK_ENV=production
      - PORT=5000
      - WORKERS=4
      - DATABASE_URL=postgresql://credence_user:SecretDbPass2026@postgres:5432/credence_core
      - REDIS_URL=redis://:SecretRedisPass2026@redis:6379/0
      - SECRET_KEY=${SECRET_KEY}
      - SESSION_SECRET=${SESSION_SECRET}
      - SESSION_COOKIE_SECURE=true
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://127.0.0.1:5000/health/live"]
      interval: 15s
      timeout: 5s
      retries: 3
      start_period: 10s

  postgres:
    image: postgres:15-alpine
    restart: always
    environment:
      POSTGRES_DB: credence_core
      POSTGRES_USER: credence_user
      POSTGRES_PASSWORD: SecretDbPass2026
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U credence_user -d credence_core"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    restart: always
    command: redis-server --requirepass SecretRedisPass2026
    volumes:
      - redisdata:/data
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "SecretRedisPass2026", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  pgdata:
  redisdata:
```

### 3.1 Compose Startup Workflow
```bash
# 1. Start database and cache services
docker compose -f docker-compose.prod.yml up -d postgres redis

# 2. Run database migrations
docker compose -f docker-compose.prod.yml run --rm web python -m alembic upgrade head

# 3. Bring up full stack
docker compose -f docker-compose.prod.yml up -d
```

---

## 4. Health Verification & Smoke Testing

### 4.1 Liveness Probe
Verifies that the Gunicorn master process and workers are alive:
```bash
curl -i http://localhost:5000/health/live
```
**Expected Response:**
```http
HTTP/1.1 200 OK
Content-Type: application/json

{"status": "alive"}
```

### 4.2 Readiness Probe
Verifies database connectivity, Redis connection, and encryption configuration:
```bash
curl -i http://localhost:5000/health/ready
```
**Expected Response:**
```http
HTTP/1.1 200 OK
Content-Type: application/json

{"database": "connected", "redis": "connected", "status": "ready"}
```

---

## 5. Zero-Downtime Rolling Update Procedure

When upgrading to future versions:
1. **Build & Tag New Container:**
   ```bash
   docker build -t credence-core:v1.0.1 .
   ```
2. **Apply Backward-Compatible Schema Migrations:**
   ```bash
   docker run --rm --env-file /etc/credence/production.env credence-core:v1.0.1 python -m alembic upgrade head
   ```
3. **Trigger Rolling Deployment:**
   Deploy new instances in target group / replica set before retiring old instances.
4. **Verify Health:**
   Ensure new replicas report `HTTP 200` on `/health/ready` before diverting user traffic.
