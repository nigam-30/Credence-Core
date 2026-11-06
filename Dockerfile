# Stage 1: Build C++ engine and install Python dependencies
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    g++ \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install pinned dependencies to isolated prefix
COPY requirements.txt requirements.lock ./
RUN pip install --no-cache-dir --prefix=/install -r requirements.lock

# Copy and compile C++ backend binary
COPY main.cpp account.cpp credit.cpp debit.cpp fd.cpp loan.cpp report.cpp upi.cpp utils.cpp cheque.cpp globals.cpp bank.h ./
RUN g++ -O2 main.cpp account.cpp credit.cpp debit.cpp fd.cpp loan.cpp report.cpp upi.cpp utils.cpp cheque.cpp globals.cpp -o bank_system

# Stage 2: Minimal hardened runtime image (No build tools)
FROM python:3.11-slim AS runtime

# Install only curl for health checks and standard C++ runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libstdc++6 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root application user
RUN groupadd -g 1000 appgroup && \
    useradd -u 1000 -g appgroup -m -s /bin/bash appuser

WORKDIR /app

# Copy installed Python dependencies from builder
COPY --from=builder /install /usr/local

# Copy compiled C++ binary from builder
COPY --from=builder /build/bank_system /app/bank_system

# Copy application source code (.dockerignore excludes DBs, secrets, logs, caches)
COPY . /app

# Enforce non-root ownership and execution permissions
RUN chown -R appuser:appgroup /app && chmod 755 /app/bank_system

USER appuser

# Dynamic port support (default 5000, overridden by platform PORT env var)
ENV PORT=5000 \
    PYTHONUNBUFFERED=1 \
    FLASK_ENV=production

EXPOSE ${PORT}

# Health check using dynamic PORT variable
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://127.0.0.1:${PORT}/health/live || exit 1

# Start the application using Gunicorn with canonical factory
CMD ["gunicorn", "--config", "gunicorn_config.py", "backend.app:create_app()"]
