"""
Credence Core — Metrics and Observability Middleware
Tracks request rates, latency percentiles, status code distribution,
and database connection pool status for production monitoring.
"""

import time
import threading
from typing import Dict, Any, List
from flask import Flask, request, g

_metrics_lock = threading.Lock()
_start_time = time.time()

# In-memory metrics counters
_request_total = 0
_status_codes: Dict[int, int] = {}
_latencies: List[float] = []  # circular buffer of latency in milliseconds
_MAX_LATENCY_SAMPLES = 2000
_active_requests = 0


def record_request_start():
    """Hook before request processing."""
    global _active_requests
    g._request_start_time = time.perf_counter()
    with _metrics_lock:
        _active_requests += 1


def record_request_end(response):
    """Hook after request processing."""
    global _request_total, _active_requests
    duration_ms = 0.0
    if hasattr(g, "_request_start_time"):
        duration_ms = (time.perf_counter() - g._request_start_time) * 1000.0

    # Add custom trace header
    response.headers["X-Response-Time-Ms"] = f"{duration_ms:.2f}"

    status = response.status_code
    with _metrics_lock:
        _request_total += 1
        _active_requests = max(0, _active_requests - 1)
        _status_codes[status] = _status_codes.get(status, 0) + 1
        _latencies.append(duration_ms)
        if len(_latencies) > _MAX_LATENCY_SAMPLES:
            _latencies.pop(0)

    return response


def get_system_metrics() -> Dict[str, Any]:
    """Calculate real-time system metrics and latency percentiles."""
    with _metrics_lock:
        total = _request_total
        active = _active_requests
        statuses = dict(_status_codes)
        sorted_latencies = sorted(_latencies)

    uptime = time.time() - _start_time
    rps = (total / uptime) if uptime > 0 else 0.0

    # Percentile calculations
    n = len(sorted_latencies)
    if n > 0:
        p50 = sorted_latencies[int(n * 0.50)]
        p95 = sorted_latencies[min(int(n * 0.95), n - 1)]
        p99 = sorted_latencies[min(int(n * 0.99), n - 1)]
        avg = sum(sorted_latencies) / n
    else:
        p50 = p95 = p99 = avg = 0.0

    # Group HTTP status categories
    s2xx = sum(count for code, count in statuses.items() if 200 <= code < 300)
    s3xx = sum(count for code, count in statuses.items() if 300 <= code < 400)
    s4xx = sum(count for code, count in statuses.items() if 400 <= code < 500)
    s5xx = sum(count for code, count in statuses.items() if 500 <= code < 600)

    error_rate = ((s4xx + s5xx) / total * 100.0) if total > 0 else 0.0

    return {
        "uptime_seconds": round(uptime, 2),
        "requests_total": total,
        "active_requests": active,
        "requests_per_second": round(rps, 2),
        "status_distribution": {
            "2xx": s2xx,
            "3xx": s3xx,
            "4xx": s4xx,
            "5xx": s5xx,
            "raw": statuses
        },
        "error_rate_pct": round(error_rate, 2),
        "latency_ms": {
            "avg": round(avg, 2),
            "p50": round(p50, 2),
            "p95": round(p95, 2),
            "p99": round(p99, 2),
            "samples": n
        }
    }


def register_metrics_middleware(app: Flask):
    """Register request hooks on Flask application."""
    app.before_request(record_request_start)
    app.after_request(record_request_end)
