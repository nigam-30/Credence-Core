#!/usr/bin/env bash
# Credence Core — Scheduled / Container Backup Script
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "[*] Triggering automated database backup..."
python3 "${PROJECT_ROOT}/scripts/db_backup.py" --retention-days 14 "$@"
