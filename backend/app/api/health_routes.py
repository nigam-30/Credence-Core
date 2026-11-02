"""
Credence Core — Health & Observability Routes
Provides Kubernetes-compatible liveness and readiness probes,
database ping checks, ledger integrity checks, and metrics.
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
    Checks primary database connectivity, SQLite ledger integrity,
    C++ engine presence, and file storage permissions.
    """
    checks = {}
    is_ready = True

    # 1. Primary Database Connection Check
    try:
        with get_db() as db:
            result = db.execute(text("SELECT 1")).scalar()
            checks["primary_database"] = {
                "status": "UP" if result == 1 else "DEGRADED",
                "dialect": engine.dialect.name
            }
    except Exception as e:
        is_ready = False
        checks["primary_database"] = {
            "status": "DOWN",
            "error": str(e)
        }

    # 2. SQLite Ledger Integrity Check
    try:
        with ledger.ledger_engine._db_session() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check(1)")
            row = cursor.fetchone()
            integrity = row[0] if row else "unknown"
            checks["ledger_engine"] = {
                "status": "UP" if integrity == "ok" else "DEGRADED",
                "integrity": integrity
            }
    except Exception as e:
        is_ready = False
        checks["ledger_engine"] = {
            "status": "DOWN",
            "error": str(e)
        }

    # 3. C++ Binary Verification
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    binary_names = ["bank_system", "bank_system.exe"]
    cpp_present = any(os.path.exists(os.path.join(base_dir, b)) for b in binary_names)
    checks["cpp_engine_binary"] = {
        "status": "UP" if cpp_present else "FALLBACK_PYTHON_MODE",
        "binary_present": cpp_present
    }

    # 4. Storage Writeability Check
    data_dir = os.environ.get("DATA_DIR", base_dir)
    storage_ok = os.access(data_dir, os.W_OK)
    checks["storage_durable"] = {
        "status": "UP" if storage_ok else "READ_ONLY",
        "data_dir": data_dir
    }
    if not storage_ok:
        is_ready = False

    status_code = 200 if is_ready else 503
    return jsonify({
        "status": "READY" if is_ready else "NOT_READY",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "components": checks
    }), status_code


@health_bp.route("/health", methods=["GET"])
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
