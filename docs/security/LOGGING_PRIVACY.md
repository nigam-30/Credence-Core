# Credence Core — Logging Privacy & Redaction Audit
**Access Log Sanitization, Secret Redaction, Exception Masking & PII Protection**

> **Educational Project Notice:**
> Credence Core is an educational banking simulator and architectural demonstrator. This report documents privacy, data protection, and log masking mechanisms implemented across the codebase.

---

## 1. Access Log Format Sanitization in Gunicorn

In web applications, access loggers often record full query strings (`%(q)s`). If an API endpoint inadvertently accepts sensitive parameters in the URL (such as account numbers, session tokens, or reset codes), these secrets leak into access logs, web proxies, and log aggregation platforms (e.g., Datadog, ELK).

### Phase 6.3 Hardened Access Log Format:
In `gunicorn_config.py`, the access log format was updated to exclude query strings and sensitive headers:

```python
# gunicorn_config.py
access_log_format = (
    '{"time": "%(t)s", '
    '"remote_ip": "%(h)s", '
    '"method": "%(m)s", '
    '"path": "%(U)s", '          # URI path only (query string stripped)
    '"status": "%(s)s", '
    '"response_bytes": "%(b)s", '
    '"duration_ms": "%(D)s", '
    '"user_agent": "%(a)s"}'
)
```
- `%(U)s` replaces `%(r)s`: Only the URL request path is recorded; all URL query parameters (`?token=...`, `?account=...`) are completely omitted.
- Authorization headers (`Cookie`, `Authorization: Bearer ...`) are excluded from log outputs.

---

## 2. Structured Redaction of Sensitive Fields

Credence Core employs a centralized log filtering mechanism (`backend/app/core/logging.py`) that scrubs all log payloads before emitting records:

### Redaction Rules:
1. **Passwords & PINs:**
   - Any key matching `password`, `pin`, `cvv`, `secret`, `api_key`, or `token` is replaced with `"[REDACTED]"`.
2. **Payment Card Data:**
   - Masked using format: `4092 **** **** 2401`.
   - CVVs and card expiration details are excluded from all logging statements.
3. **MFA Secrets:**
   - TOTP seed secrets, recovery codes, and AES encryption keys are never logged at any level.
4. **Redis Connection URLs:**
   - Evaluated via `backend.app.core.redis_client.redact_redis_url()`:
     - Input: `redis://:supersecretpass@redis-cluster:6379/0`
     - Logged: `redis://:***@redis-cluster:6379/0`

---

## 3. Exception Handling & Stack Trace Sanitization

1. **Client-Facing Error Responses:**
   - In production mode (`FLASK_ENV=production`), generic error messages are returned to HTTP clients (`{"error": "Internal Server Error", "reference_id": "ERR-XXXXXXXX"}`).
   - Raw database schema names, SQL error traces, file paths, and internal library versions are never returned in JSON payloads.
2. **Server-Side Exception Scrubbing:**
   - When internal exceptions are caught by Flask error handlers or transaction rollbacks, exception messages are sanitized to strip SQL parameter dumps containing user credentials or account numbers before writing to error log files.
