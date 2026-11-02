#!/usr/bin/env bash
# Credence Core — Disaster Recovery Restore Script
set -euo pipefail

if [ "$#" -lt 1 ]; then
    echo "Usage: $0 <backup_directory_path>"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "[*] Triggering database restoration from: $1"
python3 "${PROJECT_ROOT}/scripts/db_restore.py" "$1"
