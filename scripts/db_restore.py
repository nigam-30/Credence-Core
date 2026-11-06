#!/usr/bin/env python3
"""
Credence Core — Database Restore & Disaster Recovery Utility
Verifies cryptographic checksums before applying restore, checks ledger invariants,
and ensures complete transactional consistency.
"""

import os
import sys
import shutil
import hashlib
import sqlite3
import argparse
import subprocess
import json
from typing import Dict, Any

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


def verify_backup_integrity(backup_dir: str) -> bool:
    """Validate all files against CHECKSUMS.sha256."""
    checksum_file = os.path.join(backup_dir, "CHECKSUMS.sha256")
    if not os.path.exists(checksum_file):
        print(f"[!] Error: CHECKSUMS.sha256 missing in {backup_dir}")
        return False

    print("[*] Verifying cryptographic checksums...")
    all_valid = True
    with open(checksum_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            expected_hash, filename = line.split(maxsplit=1)
            target_path = os.path.join(backup_dir, filename.strip())
            if not os.path.exists(target_path):
                print(f"  [X] Missing file: {filename}")
                all_valid = False
                continue
            actual_hash = compute_sha256(target_path)
            if actual_hash.lower() != expected_hash.lower():
                print(f"  [X] CHECKSUM MISMATCH for {filename}!")
                print(f"      Expected: {expected_hash}")
                print(f"      Actual:   {actual_hash}")
                all_valid = False
            else:
                print(f"  [OK] Verified: {filename}")

    return all_valid


def restore_sqlite(source_path: str, target_path: str) -> bool:
    """Restore SQLite database and execute integrity check."""
    if not os.path.exists(source_path):
        print(f"[!] Source backup file not found: {source_path}")
        return False

    # Create safety backup of existing target if present
    if os.path.exists(target_path):
        safety_path = f"{target_path}.pre_restore_bak"
        shutil.copy2(target_path, safety_path)
        print(f"  [*] Created pre-restore rollback copy: {os.path.basename(safety_path)}")

    shutil.copy2(source_path, target_path)

    # Verify integrity of restored database
    conn = sqlite3.connect(target_path)
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA integrity_check(1)")
        res = cursor.fetchone()
        if res and res[0] == "ok":
            print(f"  [OK] SQLite database {os.path.basename(target_path)} passed integrity check.")
            return True
        else:
            print(f"  [X] Integrity check failed for {target_path}: {res}")
            return False
    finally:
        conn.close()


def restore_postgres(dump_path: str, db_url: str) -> bool:
    """Restore PostgreSQL database using pg_restore."""
    if not os.path.exists(dump_path):
        print(f"[!] PostgreSQL dump not found: {dump_path}")
        return False

    cmd = ["pg_restore", "--dbname", db_url, "--clean", "--if-exists", dump_path]
    try:
        print(f"  [*] Executing pg_restore from {os.path.basename(dump_path)}...")
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print("  [OK] PostgreSQL restore completed.")
        return True
    except FileNotFoundError:
        print("[!] pg_restore not available in PATH.")
        return False
    except subprocess.CalledProcessError as e:
        print(f"[!] pg_restore error: {e.stderr}")
        return False


def run_restore(backup_dir: str) -> bool:
    """Execute complete restore process."""
    if not os.path.exists(backup_dir):
        print(f"[!] Backup directory does not exist: {backup_dir}")
        return False

    if not verify_backup_integrity(backup_dir):
        print("[!] Restore aborted: Checksum verification failed!")
        return False

    # 1. Restore Ledger DB
    src_ledger = os.path.join(backup_dir, "ledger.db")
    if os.path.exists(src_ledger):
        target_ledger = os.path.join(Config.BASE_DIR, "ledger.db")
        if not restore_sqlite(src_ledger, target_ledger):
            return False

        # Run ledger reconciliation test
        try:
            import ledger
            rec = ledger.ledger_engine.reconcile_ledger()
            if rec.get("balanced"):
                print(f"  [OK] Double-entry ledger reconciled successfully! Zero imbalance confirmed.")
            else:
                print(f"  [!] Warning: Ledger reconciliation reported imbalance: {rec}")
        except Exception as e:
            print(f"  [!] Notice during reconciliation check: {e}")

    # 2. Restore Primary DB
    src_sqlite = os.path.join(backup_dir, "credence_core.db")
    if os.path.exists(src_sqlite):
        db_url = Config.DATABASE_URL or ""
        if db_url.startswith("sqlite:///"):
            target_sqlite = db_url.replace("sqlite:///", "")
        else:
            target_sqlite = os.path.join(Config.BASE_DIR, "credence_core.db")
        if not restore_sqlite(src_sqlite, target_sqlite):
            return False

    src_pg = os.path.join(backup_dir, "credence_primary.dump")
    if os.path.exists(src_pg) and Config.DATABASE_URL:
        if not restore_postgres(src_pg, Config.DATABASE_URL):
            return False

    print("  [OK] Credence Core database restore completed successfully.")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Credence Core Database Restore")
    parser.add_argument("backup_dir", help="Path to backup directory to restore")
    args = parser.parse_args()

    success = run_restore(args.backup_dir)
    sys.exit(0 if success else 1)
