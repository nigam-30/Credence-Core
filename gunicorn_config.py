"""
Credence Core — Production-Grade Gunicorn Configuration
Provides hardened concurrency, graceful worker lifecycle management, request limits,
and structured access/error logging for production containers and VM deployments.
"""

import os
import multiprocessing
import logging

# ══════════════════════════════════════════════════════════════
# SERVER SOCKET & BINDING
# ══════════════════════════════════════════════════════════════
bind = os.environ.get("GUNICORN_BIND", "0.0.0.0:5000")
backlog = int(os.environ.get("GUNICORN_BACKLOG", 2048))

# ══════════════════════════════════════════════════════════════
# WORKER PROCESSES & CONCURRENCY
# ══════════════════════════════════════════════════════════════
# Standard formula: (2 * CPUs) + 1, capped or configurable via env
default_workers = max(2, min(8, (multiprocessing.cpu_count() * 2) + 1))
workers = int(os.environ.get("WEB_CONCURRENCY", default_workers))
worker_class = os.environ.get("GUNICORN_WORKER_CLASS", "gthread")
threads = int(os.environ.get("GUNICORN_THREADS", 2))
worker_connections = int(os.environ.get("GUNICORN_WORKER_CONNECTIONS", 1000))

# ══════════════════════════════════════════════════════════════
# TIMEOUTS & GRACEFUL SHUTDOWN
# ══════════════════════════════════════════════════════════════
timeout = int(os.environ.get("GUNICORN_TIMEOUT", 30))
graceful_timeout = int(os.environ.get("GUNICORN_GRACEFUL_TIMEOUT", 30))
keepalive = int(os.environ.get("GUNICORN_KEEPALIVE", 5))

# ══════════════════════════════════════════════════════════════
# WORKER RECYCLING & RESOURCE PROTECTION
# Prevents memory accumulation in long-running Python workers
# ══════════════════════════════════════════════════════════════
max_requests = int(os.environ.get("GUNICORN_MAX_REQUESTS", 1000))
max_requests_jitter = int(os.environ.get("GUNICORN_MAX_REQUESTS_JITTER", 50))

# ══════════════════════════════════════════════════════════════
# SECURITY & REQUEST CONSTRAINTS
# Mitigate slowloris and oversized header DoS attacks
# ══════════════════════════════════════════════════════════════
limit_request_line = 4096
limit_request_fields = 100
limit_request_field_size = 8190

# ══════════════════════════════════════════════════════════════
# LOGGING
# ══════════════════════════════════════════════════════════════
accesslog = "-"  # stdout for Docker / Cloud native log collectors
errorlog = "-"   # stderr
loglevel = os.environ.get("LOG_LEVEL", "info").lower()
access_log_format = (
    '{"remote_ip":"%(h)s","timestamp":"%(t)s","method":"%(m)s",'
    '"uri":"%(U)s","query":"%(q)s","status":%(s)s,"bytes":%(B)s,'
    '"duration_us":%(D)s,"user_agent":"%(a)s"}'
)

# ══════════════════════════════════════════════════════════════
# PROCESS NAMING
# ══════════════════════════════════════════════════════════════
proc_name = "credence-core"


# ══════════════════════════════════════════════════════════════
# SERVER LIFECYCLE HOOKS
# ══════════════════════════════════════════════════════════════
def on_starting(server):
    server.log.info("Starting Credence Core Gunicorn server on %s with %s workers (%s threads)", bind, workers, threads)


def post_fork(server, worker):
    server.log.info("Spawned worker %s (pid: %s)", worker.age, worker.pid)


def worker_int(worker):
    worker.log.info("Worker received SIGINT/SIGQUIT (pid: %s)", worker.pid)


def worker_abort(worker):
    worker.log.error("Worker received SIGABRT (pid: %s)", worker.pid)
