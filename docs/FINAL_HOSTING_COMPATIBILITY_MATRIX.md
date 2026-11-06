# CREDENCE CORE BANKING SYSTEM — FINAL HOSTING COMPATIBILITY MATRIX
**Document Version:** 1.0.0  
**Status:** Certified Architecture & Deployment Specifications  
**Standard Runtime:** OCI Linux Container (Python 3.11/3.13 Gunicorn WSGI, PostgreSQL 15+, Redis 7+)  

---

## 1. Cloud Platform Compatibility Matrix

The application core has been standardized to eliminate provider lock-in, hardcoded ports, fixed file paths, and local persistence assumptions. Below is the compatibility matrix across all 14 evaluated platforms:

| # | Platform | Deployment Method | Supported | Required Services | Port Configuration | Storage Configuration | Health Check Path | Migration Method |
|:---:|---|---|:---:|---|---|---|---|---|
| **1** | **Render** | Blueprint / Docker | **YES** | Managed PG + Redis | Automatic `$PORT` bind (`0.0.0.0:${PORT}`) | Stateless container disk | `/health/live` & `/health/ready` | Pre-deploy command: `alembic upgrade head` |
| **2** | **Railway** | Docker Deployment | **YES** | Railway PG + Redis plugins | Automatic `$PORT` bind (`0.0.0.0:${PORT}`) | Stateless container disk | `/health/live` | Deploy release command: `alembic upgrade head` |
| **3** | **Fly.io** | Fly Docker Image | **YES** | Fly Postgres + Upstash Redis | `fly.toml` internal port 5000 / dynamic `$PORT` | Ephemeral root; external database | `/health/live` | `[deploy]` release_command = `alembic upgrade head` |
| **4** | **AWS ECS / Fargate** | OCI Container via ECR | **YES** | AWS RDS Aurora PG + ElastiCache Redis | Container port 5000 (Target Group mapping) | Ephemeral Fargate task storage | `/health/live` | Init container / ECS task running Alembic |
| **5** | **AWS App Runner** | OCI Container via ECR | **YES** | AWS RDS PostgreSQL + ElastiCache Redis | Configured port 5000 (`$PORT` supported) | Stateless container instance | `/health/live` | Pre-deploy script or CI/CD pipeline step |
| **6** | **AWS EC2** | Docker Compose | **YES** | Containerized or RDS PG + Redis | Mapped host port `80`/`443` -> `5000` | EBS volume for persistent DB/Redis containers | `/health/live` | `docker compose run --rm web alembic upgrade head` |
| **7** | **Google Cloud Run** | OCI Container via Artifact Registry | **YES** | Cloud SQL for PostgreSQL + Memorystore Redis | Automatically injected `$PORT` (typically 8080) | In-memory ephemeral filesystem | `/health/live` & `/health/ready` | Cloud Run Jobs: `python -m alembic upgrade head` |
| **8** | **Google Kubernetes Engine (GKE)** | Kubernetes Manifests / Helm | **YES** | Cloud SQL / StatefulSet PG + Redis | Deployment `containerPort: 5000` via Service | Ephemeral pod storage; PV/PVC for stateful backends | Liveness: `/health/live`, Readiness: `/health/ready` | K8s Job with `restartPolicy: OnFailure` |
| **9** | **Azure Container Apps** | OCI Container via ACR | **YES** | Azure Database for PG + Azure Cache for Redis | Target port 5000 (`$PORT` supported) | Ephemeral container replica storage | HTTP probe: `/health/live` | Azure Container App Job for schema migration |
| **10** | **Azure App Service for Containers** | Linux Custom Container | **YES** | Azure Database for PG + Azure Cache for Redis | `WEBSITES_PORT=5000` or `$PORT` | Stateless; external Azure SQL/PG | Path: `/health/live` | Startup script or GitHub Actions deploy step |
| **11** | **DigitalOcean App Platform** | App Spec / Dockerfile | **YES** | Managed PostgreSQL + Managed Redis | Automatically injected `$PORT` (typically 8080) | Ephemeral container storage | `/health/live` | Pre-deploy Job: `alembic upgrade head` |
| **12** | **DigitalOcean Droplet** | Docker Compose | **YES** | Containerized or Managed PG + Redis | Mapped host port `80`/`443` -> `5000` | Block storage volume for DB/Redis data | `/health/live` | `docker compose exec web alembic upgrade head` |
| **13** | **Generic Linux VPS (Ubuntu/Debian)** | Docker Compose + Nginx Reverse Proxy | **YES** | Local Dockerized or Remote PG + Redis | Nginx reverse proxy `proxy_pass http://127.0.0.1:5000` | Host directory bind-mounts for database volume | `/health/live` & `/health/ready` | `docker compose -f docker-compose.prod.yml run --rm web alembic upgrade head` |
| **14** | **Local Linux / Windows with Docker** | Docker Compose (`docker-compose.yml`) | **YES** | Bundled `postgres:15-alpine` + `redis:7-alpine` | `localhost:5000` | Local named Docker volumes | `/health/live` & `/health/ready` | Auto-executed by startup entrypoint |

---

## 2. In-Depth Evaluation of Serverless Platforms (Vercel / Netlify / AWS Lambda)

### 2.1 Architectural Incompatibility Analysis

While standard container runtimes (Cloud Run, Fargate, App Runner) work seamlessly, **Vercel Serverless Functions and generic Lambda runtimes are architecturally incompatible** with Credence Core's core banking workflows.

```
+---------------------------------------------------------------------------------------------+
|                                SERVERLESS PLATFORM MISALIGNMENT                             |
+---------------------------------------------------------------------------------------------+
| Credence Core Requirement                | Serverless / Lambda Reality                      |
|------------------------------------------|--------------------------------------------------|
| Continuous In-Memory C++ Ledger Engine   | Ephemeral Lambdas terminated after request       |
| PostgreSQL Connection Pooling (max 20)   | Unbounded lambda concurrency exhausts pool       |
| Distributed Redis Locks across workers   | Abrupt execution freeze can orphan locks         |
| Long-running background audit flush      | Execution frozen immediately upon HTTP response  |
| Non-root container security context      | Proprietary runtime sandbox without custom flags |
+---------------------------------------------------------------------------------------------+
```

### 2.2 Recommendation
* **Do NOT deploy the backend to Vercel Serverless.**
* If Vercel is desired for hosting a decoupled frontend single-page application (SPA), configure Vercel strictly for static HTML/JS delivery and route API requests (`/api/*`, `/health/*`) to a containerized Credence Core backend on Render, Railway, AWS ECS, or Cloud Run.

---

## 3. Platform Configuration Checklist

1. **Port Binding Contract:**
   The application strictly adheres to the standard UNIX contract:
   ```bash
   gunicorn --bind 0.0.0.0:${PORT:-5000} --workers ${WORKERS:-4} "backend.app:create_app()"
   ```
2. **Database Contract:**
   All production configurations must pass a valid PostgreSQL connection string:
   ```bash
   DATABASE_URL=postgresql://user:password@host:5432/credence_core
   ```
   *SQLite is strictly rejected in production environments.*
3. **Shared State Contract:**
   Distributed rate limiting and token bucket enforcement require Redis:
   ```bash
   REDIS_URL=redis://:password@host:6379/0
   ```
4. **Health Check Endpoints:**
   * `/health/live`: HTTP 200 indicating the WSGI process is running and accepting HTTP connections.
   * `/health/ready`: HTTP 200 indicating active connectivity to database and Redis without revealing sensitive internal paths or connection secrets.
