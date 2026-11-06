"""
Credence Core Release Package Validator
Performs strict recursive inspection of the release ZIP (and any nested archives)
against the sensitive-data denylist and cryptographically verifies every file against
the authoritative FINAL_RELEASE_MANIFEST.sha256.
Fails with code 1 if any forbidden artifact, backup, log, runtime database,
cache, nested archive, or checksum mismatch is detected.
"""

import sys
import zipfile
import hashlib
import io
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DIST_DIR = BASE_DIR / "dist"
RELEASE_ZIP_NAME = "Credence-Core-v1.0.0-Release.zip"
RELEASE_ZIP_PATH = DIST_DIR / RELEASE_ZIP_NAME
MANIFEST_PATH = BASE_DIR / "docs" / "FINAL_RELEASE_MANIFEST.sha256"

# Strict DENYLIST patterns
FORBIDDEN_PATTERNS = [
    # Runtime Databases & Local Data
    "credence_core.db",
    "credence_core.db.pre_restore_bak",
    ".db",
    ".db-wal",
    ".db-shm",
    ".sqlite",
    ".sqlite3",
    "bank_data.json",
    "user_profiles.json",
    "user_investments.json",

    # Secrets & Environment Configurations
    ".env",

    # Backups & Rollbacks
    "db_rollback_backups",
    "runtime_backups",
    "backups",
    ".bak",
    "pre_restore",

    # Logs & Traces
    "security.log",
    ".log",

    # Python Cache & Artifacts
    "__pycache__",
    ".pyc",
    ".pyo",
    ".pytest_cache",

    # Nested Archives & Stale Manifests
    "bank_system_clean.zip",
    ".zip",
    ".tar",
    ".gz",
    ".sha256"
]


def sha256_bytes(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()


def sha256_file(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def inspect_zip_recursively(zip_path: Path, archive_name: str = "Root Archive"):
    violations = []
    inspected_count = 0

    print(f"[*] Inspecting {archive_name}: {zip_path.name}")
    with zipfile.ZipFile(zip_path, "r") as zf:
        infolist = zf.infolist()
        for info in infolist:
            filename = info.filename
            inspected_count += 1
            lower_name = filename.lower()

            # Check each forbidden pattern
            for pattern in FORBIDDEN_PATTERNS:
                if pattern in lower_name:
                    violations.append((filename, pattern, f"Matched forbidden pattern '{pattern}' in {archive_name}"))

            # If a nested archive was found, inspect it recursively
            if lower_name.endswith(".zip") and filename != zip_path.name:
                print(f"  [!] Found nested ZIP: {filename}. Recursively inspecting...")
                nested_data = zf.read(filename)
                nested_stream = io.BytesIO(nested_data)
                nested_violations, nested_count = inspect_zip_in_memory(nested_stream, filename)
                violations.extend(nested_violations)
                inspected_count += nested_count

    return violations, inspected_count


def inspect_zip_in_memory(stream: io.BytesIO, archive_name: str):
    violations = []
    inspected_count = 0
    with zipfile.ZipFile(stream, "r") as zf:
        for info in zf.infolist():
            filename = info.filename
            inspected_count += 1
            lower_name = filename.lower()
            for pattern in FORBIDDEN_PATTERNS:
                if pattern in lower_name:
                    violations.append((f"{archive_name} -> {filename}", pattern, f"Nested forbidden match: '{pattern}'"))
    return violations, inspected_count


def verify_against_manifest(zip_path: Path, manifest_path: Path) -> bool:
    """Verify archive SHA-256 and every individual file against the authoritative manifest."""
    if not manifest_path.exists():
        print(f"[FAIL] Authoritative manifest missing at: {manifest_path}")
        return False

    with open(manifest_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    expected_archive_hash = None
    manifest_entries = {}
    for line in lines:
        if line.startswith("# Archive-SHA256:"):
            expected_archive_hash = line.split(":", 1)[1].strip()
        elif line.startswith("#"):
            continue
        else:
            parts = line.split(None, 1)
            if len(parts) == 2:
                manifest_entries[parts[1].strip()] = parts[0].strip()

    # 1. Verify Archive SHA-256
    actual_archive_hash = sha256_file(zip_path)
    print(f"[*] Verifying archive checksum:")
    print(f"    Expected: {expected_archive_hash}")
    print(f"    Actual:   {actual_archive_hash}")
    if expected_archive_hash and expected_archive_hash != actual_archive_hash:
        print("[CRITICAL] Archive SHA-256 checksum mismatch!")
        return False

    # 2. Verify all entries in archive match manifest
    mismatches = []
    missing_in_archive = []
    with zipfile.ZipFile(zip_path, "r") as zf:
        zip_names = set(zf.namelist())

        for name in zip_names:
            if name.endswith("/"):
                continue  # skip directory entries
            if name not in manifest_entries:
                mismatches.append(f"File in archive but not in manifest: {name}")
                continue
            data = zf.read(name)
            file_hash = sha256_bytes(data)
            if file_hash != manifest_entries[name]:
                mismatches.append(
                    f"Checksum mismatch for {name}: expected {manifest_entries[name]}, got {file_hash}"
                )

        for name in manifest_entries:
            if name not in zip_names:
                missing_in_archive.append(f"File in manifest missing from archive: {name}")

    if mismatches or missing_in_archive:
        for m in mismatches:
            print(f"  [ERROR] {m}")
        for m in missing_in_archive:
            print(f"  [ERROR] {m}")
        return False

    print(f"[OK] All {len(manifest_entries)} archived files match cryptographic manifest checksums exactly.")
    return True


def main():
    if not RELEASE_ZIP_PATH.exists():
        print(f"[FAIL] Release archive does not exist at {RELEASE_ZIP_PATH}. Run package_release.py first.")
        sys.exit(1)

    print(f"[*] Running Release Package Validation on: {RELEASE_ZIP_PATH.name}")
    print(f"    Target Size: {RELEASE_ZIP_PATH.stat().st_size / (1024 * 1024):.2f} MB")

    violations, total_inspected = inspect_zip_recursively(RELEASE_ZIP_PATH)

    print(f"\n[*] Total archive entries inspected: {total_inspected}")

    if violations:
        print(f"\n[CRITICAL FAILURE] Found {len(violations)} forbidden / sensitive artifacts in release package!")
        for file_entry, pattern, reason in violations:
            print(f"  - FORBIDDEN: {file_entry} (Reason: {reason})")
        print("\nRelease gate status: BLOCKED — PURGE FAILED.")
        sys.exit(1)

    # Verify against manifest
    print("\n[*] Cryptographic manifest verification...")
    if not verify_against_manifest(RELEASE_ZIP_PATH, MANIFEST_PATH):
        print("[CRITICAL FAILURE] Manifest verification failed!")
        sys.exit(1)

    print("\n=================================================================")
    print("[PASS] RELEASE ARCHIVE INTEGRITY & CHECKSUMS FULLY VERIFIED")
    print("=================================================================")
    print("  [OK] Zero runtime databases (.db, .sqlite)")
    print("  [OK] Zero database rollback backups or pre-restore snapshots")
    print("  [OK] Zero customer/user JSON runtime stores")
    print("  [OK] Zero security or application log files (.log)")
    print("  [OK] Zero Python __pycache__ or compiled bytecode (.pyc)")
    print("  [OK] Zero nested old zip archives")
    print("  [OK] Zero self-referential or stale manifests packaged")
    print("  [OK] Archive and file-level SHA-256 verified 100%")
    print("=================================================================")


if __name__ == "__main__":
    main()
