# DEPLOYMENT CONSISTENCY & RUNTIME ENVIRONMENT AUDIT

> **SIMULATOR NOTICE:** Credence Core is an educational banking system simulator.

---

## 1. RUNTIME CONFIGURATION HARMONIZATION

The deployment infrastructure across Docker, Render, Gunicorn, and local testing has been harmonized to use the single canonical application factory:

| Component | Entrypoint / Factory | Environment Profile | Database Target | Proxy Fix |
|---|---|---|---|---|
| **Render.com** (`render.yaml`) | `gunicorn flask_app:app` | `production` | Managed PostgreSQL | Active (`x_for=1`) |
| **Docker** (`Dockerfile` / `docker-compose.yml`) | `gunicorn -c gunicorn_config.py flask_app:app` | `production` / `development` | Container PostgreSQL | Active (`x_for=1`) |
| **Procfile** | `web: gunicorn flask_app:app` | Production | Managed PostgreSQL | Active |
| **Local Dev / Testing** | `create_app()` / `flask_app.py` | `development` / `testing` | SQLite (`credence_core.db`) | Inactive / Standard |

---

## 2. PRODUCTION FAIL-FAST INVARIANTS

In production mode (`FLASK_ENV=production`), `ProductionConfig.validate_secrets()` runs at startup and immediately aborts process startup if any of the following occur:
1. `SECRET_KEY` is missing, shorter than 32 characters, or in the known insecure dictionary.
2. `MFA_ENCRYPTION_KEY` is missing, shorter than 32 characters, or identical to `SECRET_KEY`.
3. `DATABASE_URL` is not a PostgreSQL connection string (`postgresql://` or `postgres://`). Automatic fallback to SQLite is strictly forbidden.
4. Database connection fails during application factory boot.

---

## 3. SESSION COOKIE RUNTIME BEHAVIOR

- `HttpOnly`: Always `True` across all environments.
- `SameSite`: `"Lax"` to prevent cross-site request leakage.
- `Secure`: Dynamically active when `FLASK_ENV=production` or `HTTPS=on`. In development/testing, relaxed to permit localhost testing over plain HTTP.
