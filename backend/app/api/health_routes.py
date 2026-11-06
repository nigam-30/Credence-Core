"""
Credence Core — Health & Observability Routes
Provides Kubernetes-compatible liveness and readiness probes,
database ping checks, ledger integrity checks, and metrics.
No secrets, credentials, or internal file paths are exposed.
"""

import os
import time
import datetime
from flask import Blueprint, jsonify
from sqlalchemy import text

from backend.app.core.database import get_db, engine
from backend.app.middleware.metrics_middleware import get_system_metrics
import ledger

health_bp = Blueprint("health", __name__)


@health_bp.route("/health/live", methods=["GET"])
def liveness():
    """Liveness probe: Indicates if application process is alive."""
    return jsonify({
        "status": "UP",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }), 200


@health_bp.route("/health/ready", methods=["GET"])
def readiness():
    """
    Readiness probe: Deep component health inspection.
    Checks primary database connectivity, ledger integrity,
    C++ engine presence, and storage permissions.
    Strictly avoids exposing secrets, database URLs, error tracebacks, or absolute file paths.
    """
    checks = {}
    is_ready = True

    # 1. Primary Database Connection Check
    try:
        with get_db() as db:
            result = db.execute(text("SELECT 1")).scalar()
            checks["primary_database"] = {
                "status": "UP" if result == 1 else "DEGRADED"
            }
    except Exception:
        is_ready = False
        checks["primary_database"] = {
            "status": "DOWN"
        }

    # 2. Ledger Engine Integrity / Connectivity Check
    try:
        if engine.dialect.name == "sqlite":
            with ledger.ledger_engine._db_session() as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA integrity_check(1)")
                row = cursor.fetchone()
                if isinstance(row, dict):
                    integrity = list(row.values())[0] if row else "unknown"
                elif isinstance(row, (list, tuple)):
                    integrity = row[0] if row else "unknown"
                else:
                    integrity = str(row) if row else "unknown"
                checks["ledger_engine"] = {
                    "status": "UP" if integrity == "ok" else "DEGRADED"
                }
        else:
            with get_db() as db:
                db.execute(text("SELECT 1 FROM ledger_entries LIMIT 1")).scalar()
                checks["ledger_engine"] = {
                    "status": "UP"
                }
    except Exception:
        is_ready = False
        checks["ledger_engine"] = {
            "status": "DOWN"
        }

    # 3. C++ Binary Verification
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    binary_names = ["bank_system", "bank_system.exe"]
    cpp_present = any(os.path.exists(os.path.join(base_dir, b)) for b in binary_names)
    checks["cpp_engine_binary"] = {
        "status": "UP" if cpp_present else "FALLBACK_PYTHON_MODE"
    }

    # 4. Storage Writeability Check
    data_dir = os.environ.get("DATA_DIR", base_dir)
    storage_ok = os.access(data_dir, os.W_OK)
    checks["storage_durable"] = {
        "status": "UP" if storage_ok else "READ_ONLY"
    }
    if not storage_ok:
        is_ready = False

    # 5. Distributed Redis Connectivity Check
    from backend.app.core.redis_client import get_redis_client
    redis_url = os.environ.get("REDIS_URL", "").strip()
    if redis_url:
        try:
            r_client = get_redis_client()
            if r_client and r_client.ping():
                checks["redis_cluster"] = {
                    "status": "UP"
                }
            else:
                checks["redis_cluster"] = {"status": "DOWN"}
                if os.environ.get("FLASK_ENV") == "production":
                    is_ready = False
        except Exception:
            checks["redis_cluster"] = {"status": "DOWN"}
            if os.environ.get("FLASK_ENV") == "production":
                is_ready = False
    else:
        checks["redis_cluster"] = {
            "status": "NOT_CONFIGURED",
            "mode": "in_memory_fallback" if os.environ.get("FLASK_ENV") != "production" else "REQUIRED"
        }
        if os.environ.get("FLASK_ENV") == "production":
            is_ready = False

    status_code = 200 if is_ready else 503
    return jsonify({
        "status": "READY" if is_ready else "NOT_READY",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "components": checks
    }), status_code


@health_bp.route("/health", methods=["GET"])
@health_bp.route("/api/health", methods=["GET"])
def health_summary():
    """Combined health overview."""
    return readiness()


@health_bp.route("/api/metrics", methods=["GET"])
def metrics():
    """Expose application request and performance metrics."""
    data = get_system_metrics()

    # Append database connection pool metrics if available
    try:
        pool = engine.pool
        data["database_pool"] = {
            "size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow()
        }
    except Exception:
        data["database_pool"] = {"status": "pool_stats_unavailable"}

    return jsonify(data), 200
