"""
Credence Core — Enterprise Structured Logging & Observability
Provides JSON log formatting, error tracking, transaction failure monitoring,
and sanitized security event emission.
Never logs credentials, passwords, PINs, CVVs, or session tokens.
"""

import os
import json
import logging
import datetime
import traceback
import uuid
from typing import Any, Dict, Optional
from flask import has_request_context, request, g

from backend.app.core.config import Config

LOG_FILE = os.path.join(Config.BASE_DIR, "security.log")
APP_LOG_FILE = os.path.join(Config.BASE_DIR, "app.log")


class StructuredJsonFormatter(logging.Formatter):
    """Formats log records as structured single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "lineno": record.lineno,
        }

        # Inject request context if inside a Flask request
        if has_request_context():
            log_obj["request_id"] = getattr(g, "request_id", request.headers.get("X-Request-ID", "-"))
            log_obj["path"] = request.path
            log_obj["method"] = request.method
            log_obj["remote_ip"] = request.headers.get("X-Forwarded-For", request.remote_addr or "127.0.0.1")

        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj)


# Setup primary security logger
security_logger = logging.getLogger("credence_security")
security_logger.setLevel(logging.INFO)

# Setup application monitoring logger
app_logger = logging.getLogger("credence_app")
app_logger.setLevel(logging.INFO)

if not security_logger.handlers:
    file_formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] [SECURITY] %(message)s")
    json_formatter = StructuredJsonFormatter()

    # File handler (standard text format for human inspection)
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setLevel(logging.INFO)
    fh.setFormatter(file_formatter)
    security_logger.addHandler(fh)

    # Console handler (JSON in production / container environments)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    if os.environ.get("LOG_FORMAT", "text").lower() == "json" or os.environ.get("FLASK_ENV") == "production":
        ch.setFormatter(json_formatter)
    else:
        ch.setFormatter(file_formatter)
    security_logger.addHandler(ch)


def get_request_id() -> str:
    """Resolve or generate unique correlation ID for current request."""
    if has_request_context():
        if not hasattr(g, "request_id"):
            g.request_id = request.headers.get("X-Request-ID") or f"req-{uuid.uuid4().hex[:12]}"
        return g.request_id
    return f"sys-{uuid.uuid4().hex[:12]}"


def log_structured_event(event_type: str, actor: str, ip: str, details: Optional[Dict[str, Any]] = None, level: str = "INFO"):
    """Emit a structured security event sanitized of sensitive fields."""
    details = details or {}
    sanitized = {}
    for k, v in details.items():
        if any(secret in k.lower() for secret in ["password", "pin", "cvv", "token", "secret", "cookie"]):
            sanitized[k] = "[REDACTED]"
        else:
            sanitized[k] = v

    payload = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "event": event_type,
        "actor": actor,
        "ip": ip,
        "request_id": get_request_id(),
        "details": sanitized,
    }

    msg = json.dumps(payload)
    if level == "WARNING":
        security_logger.warning(f"STRUCTURED_EVENT={msg}")
    elif level == "ERROR":
        security_logger.error(f"STRUCTURED_EVENT={msg}")
    else:
        security_logger.info(f"STRUCTURED_EVENT={msg}")


def log_error_event(error_name: str, message: str, exc: Optional[Exception] = None, details: Optional[Dict[str, Any]] = None):
    """Track application exceptions with context and stack trace."""
    req_id = get_request_id()
    stack = traceback.format_exc() if exc else None

    payload = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "error_type": error_name,
        "message": message,
        "request_id": req_id,
        "stack_trace": stack,
        "details": details or {}
    }

    app_logger.error(f"ERROR_TRACK={json.dumps(payload)}")


def log_transaction_failure(reference_id: str, account_number: str, reason: str, amount_paise: int, ip: str):
    """Dedicated structured audit trail for failed or rejected transactions."""
    payload = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "event": "TRANSACTION_FAILURE",
        "reference_id": reference_id,
        "account_number": account_number,
        "amount_paise": amount_paise,
        "amount_rupees": amount_paise / 100.0,
        "reason": reason,
        "ip": ip,
        "request_id": get_request_id()
    }
    security_logger.warning(f"TXN_FAILURE={json.dumps(payload)}")
