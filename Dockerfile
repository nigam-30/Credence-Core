FROM python:3.11-slim

# Install g++ compiler, build tools, and curl for healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
    g++ \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root application user
RUN groupadd -g 1000 appgroup && \
    useradd -u 1000 -g appgroup -m -s /bin/bash appuser

WORKDIR /app

# Copy dependency definition
COPY requirements.txt requirements.lock ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy all source files
COPY . .

# Compile C++ backend binary
RUN g++ main.cpp account.cpp credit.cpp debit.cpp fd.cpp loan.cpp report.cpp upi.cpp utils.cpp cheque.cpp globals.cpp -o bank_system

# Set directory permissions for non-root user
RUN chown -R appuser:appgroup /app

USER appuser

# Expose port
EXPOSE 5000

ENV PORT=5000
ENV PYTHONUNBUFFERED=1

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:5000/health/live || exit 1

# Start the application using Gunicorn with canonical factory
CMD ["gunicorn", "--config", "gunicorn_config.py", "backend.app:create_app()"]
