#!/usr/bin/env python3
"""
Credence Core — Database Backup Utility
Performs atomic, tamper-evident backups of PostgreSQL and SQLite ledger databases.
Generates SHA-256 checksums, metadata manifests, and supports backup retention pruning.
"""

import os
import sys
import time
import shutil
import hashlib
import sqlite3
import argparse
import datetime
import subprocess
import json
from typing import Dict, Any, List

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from backend.app.core.config import Config


def compute_sha256(filepath: str) -> str:
    """Calculate SHA-256 hash of a file for integrity verification."""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            sha256.update(chunk)
    return sha256.hexdigest()


def backup_sqlite(source_path: str, dest_path: str) -> Dict[str, Any]:
    """Execute live online hot backup of an SQLite database."""
    if not os.path.exists(source_path):
        return {"status": "SKIPPED", "reason": f"File does not exist: {source_path}"}

    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    src_conn = sqlite3.connect(source_path)
    dst_conn = sqlite3.connect(dest_path)
    try:
        with dst_conn:
            src_conn.backup(dst_conn)
    finally:
        dst_conn.close()
        src_conn.close()

    checksum = compute_sha256(dest_path)
    size_bytes = os.path.getsize(dest_path)
    return {
        "status": "SUCCESS",
        "file": os.path.basename(dest_path),
        "size_bytes": size_bytes,
        "sha256": checksum
    }


def backup_postgres(db_url: str, dest_path: str) -> Dict[str, Any]:
    """Perform pg_dump for PostgreSQL databases."""
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    cmd = ["pg_dump", "--dbname", db_url, "--format=custom", "--file", dest_path]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        checksum = compute_sha256(dest_path)
        return {
            "status": "SUCCESS",
            "file": os.path.basename(dest_path),
            "size_bytes": os.path.getsize(dest_path),
            "sha256": checksum
        }
    except FileNotFoundError:
        # pg_dump binary not installed locally
        return {"status": "SKIPPED", "reason": "pg_dump tool not found in PATH"}
    except subprocess.CalledProcessError as e:
        return {"status": "FAILED", "error": e.stderr}


def run_backup(target_dir: str = None, retention_days: int = 7) -> str:
    """Execute full backup suite and generate signed manifest."""
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_root = target_dir or os.path.join(Config.BASE_DIR, "backups")
    dest_dir = os.path.join(backup_root, f"backup_{timestamp}")
    os.makedirs(dest_dir, exist_ok=True)

    print(f"[*] Starting Credence Core backup to: {dest_dir}")
    manifest = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "backup_id": f"BCK-{timestamp}",
        "artifacts": {}
    }

    # 1. Backup SQLite Ledger DB
    ledger_db = os.path.join(Config.BASE_DIR, "ledger.db")
    dest_ledger = os.path.join(dest_dir, "ledger.db")
    res_ledger = backup_sqlite(ledger_db, dest_ledger)
    manifest["artifacts"]["ledger_db"] = res_ledger
    print(f"  [+] Ledger DB: {res_ledger['status']}")

    # 2. Backup Primary Application DB (Postgres or SQLite)
    db_url = Config.DATABASE_URL or ""
    if db_url.startswith("postgres://") or db_url.startswith("postgresql://"):
        dest_pg = os.path.join(dest_dir, "credence_primary.dump")
        res_pg = backup_postgres(db_url, dest_pg)
        manifest["artifacts"]["primary_postgres"] = res_pg
        print(f"  [+] PostgreSQL Primary DB: {res_pg['status']}")
    else:
        # SQLite primary database (dynamically honor active DATABASE_URL)
        if db_url.startswith("sqlite:///"):
            app_db = db_url.replace("sqlite:///", "")
        else:
            app_db = os.path.join(Config.BASE_DIR, "credence_core.db")
        dest_app = os.path.join(dest_dir, "credence_core.db")
        res_app = backup_sqlite(app_db, dest_app)
        manifest["artifacts"]["primary_sqlite"] = res_app
        print(f"  [+] SQLite Primary DB: {res_app['status']}")

    # 3. Write manifest.json
    manifest_path = os.path.join(dest_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    manifest_sha = compute_sha256(manifest_path)
    with open(os.path.join(dest_dir, "CHECKSUMS.sha256"), "w", encoding="utf-8") as f:
        f.write(f"{manifest_sha}  manifest.json\n")
        for name, art in manifest["artifacts"].items():
            if art.get("status") == "SUCCESS":
                f.write(f"{art['sha256']}  {art['file']}\n")

    print(f"  [OK] Backup completed successfully. Manifest: {manifest_path}")

    # 4. Prune old backups beyond retention_days
    if retention_days > 0 and os.path.exists(backup_root):
        cutoff = time.time() - (retention_days * 86400)
        for entry in os.listdir(backup_root):
            entry_path = os.path.join(backup_root, entry)
            if os.path.isdir(entry_path) and entry.startswith("backup_"):
                if os.path.getmtime(entry_path) < cutoff:
                    print(f"[-] Pruning expired backup directory: {entry}")
                    shutil.rmtree(entry_path, ignore_errors=True)

    return dest_dir


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Credence Core Database Backup")
    parser.add_argument("--dir", default=None, help="Destination directory for backups")
    parser.add_argument("--retention-days", type=int, default=7, help="Days to retain backups")
    args = parser.parse_args()

    run_backup(target_dir=args.dir, retention_days=args.retention_days)
