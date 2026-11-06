"""
Credence Core Release Packaging Script
Builds a sanitized production release ZIP using an explicit ALLOWLIST and generates
the authoritative cryptographic SHA-256 release manifest AFTER release contents are frozen.
Does NOT delete user files or backups from the working tree.
"""

import os
import sys
import zipfile
import hashlib
import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DIST_DIR = BASE_DIR / "dist"
RELEASE_ZIP_NAME = "Credence-Core-v1.0.0-Release.zip"
RELEASE_ZIP_PATH = DIST_DIR / RELEASE_ZIP_NAME
MANIFEST_PATH = BASE_DIR / "docs" / "FINAL_RELEASE_MANIFEST.sha256"

# Strict Source Directory ALLOWLIST
ALLOWLIST_DIRS = [
    "backend",
    "alembic",
    "tests",
    "docs",
    "scripts"
]

# Strict Root File ALLOWLIST
ALLOWLIST_ROOT_FILES = [
    "alembic.ini",
    "app.js",
    "code.html",
    "code(1).html",
    "database.py",
    "models.py",
    "security.py",
    "ledger.py",
    "flask_app.py",
    "main.cpp",
    "account.cpp",
    "credit.cpp",
    "debit.cpp",
    "fd.cpp",
    "loan.cpp",
    "report.cpp",
    "upi.cpp",
    "utils.cpp",
    "cheque.cpp",
    "globals.cpp",
    "bank.h",
    "CMakeLists.txt",
    "gunicorn_config.py",
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.dev.yml",
    "render.yaml",
    "requirements.txt",
    "requirements.lock",
    "requirements-dev.txt",
    ".env.example",
    ".gitignore",
    ".gitattributes",
    ".dockerignore",
    "Procfile",
    "LICENSE",
    "SECURITY.md",
    "CONTRIBUTING.md",
    "README.md",
    "vercel.json"
]

# Strict DENYLIST patterns (safety enforcement)
DENY_EXTENSIONS = {
    ".db", ".db-wal", ".db-shm", ".sqlite", ".sqlite3",
    ".bak", ".pre_restore_bak", ".log",
    ".pyc", ".pyo", ".pyd",
    ".zip", ".tar", ".gz",
    ".sha256"  # Manifest files are external authorities and must NEVER be packaged self-referentially inside the ZIP
}

DENY_NAMES = {
    "credence_core.db",
    "credence_core.db.pre_restore_bak",
    "security.log",
    "bank_data.json",
    "user_profiles.json",
    "user_investments.json",
    "bank_system_clean.zip",
    "Credence-Core-v1.0.0-Release.zip",
    ".env",
    "FINAL_RELEASE_MANIFEST.sha256",
    "RELEASE_MANIFEST.sha256"
}

DENY_DIRS = {
    "__pycache__",
    ".pytest_cache",
    ".git",
    "db_rollback_backups",
    "runtime_backups",
    "backups",
    "dist",
    "logs",
    "storage"
}


def should_include_file(rel_path_str: str) -> bool:
    rel_path = Path(rel_path_str)
    parts = rel_path.parts

    # Exclude any hidden directories or denied directories
    for d in parts[:-1]:
        if d in DENY_DIRS or (d.startswith(".") and d not in (".github",)):
            return False

    name = rel_path.name
    # Exclude exact deny names
    if name in DENY_NAMES or name.startswith(".env"):
        return False

    # Exclude denied extensions
    ext = rel_path.suffix.lower()
    if ext in DENY_EXTENSIONS or ".bak" in name.lower() or name.endswith(".sha256"):
        return False

    # Root files: must be in explicit root allowlist
    if len(parts) == 1:
        return name in ALLOWLIST_ROOT_FILES

    # Nested files: top-level directory must be in allowlist
    top_dir = parts[0]
    if top_dir not in ALLOWLIST_DIRS:
        return False

    return True


def sha256_file(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def main():
    print(f"[*] Packaging Credence Core Distributable Release from: {BASE_DIR}")
    DIST_DIR.mkdir(parents=True, exist_ok=True)

    if RELEASE_ZIP_PATH.exists():
        RELEASE_ZIP_PATH.unlink()

    included_files = []

    # 1. Collect all valid source files matching strict allowlist
    for root, dirs, files in os.walk(BASE_DIR):
        dirs[:] = [d for d in dirs if d not in DENY_DIRS and not d.startswith(".")]

        for f in files:
            full_path = Path(root) / f
            rel_path = full_path.relative_to(BASE_DIR).as_posix()
            if should_include_file(rel_path):
                included_files.append((full_path, rel_path))

    included_files.sort(key=lambda x: x[1])

    print(f"[*] Total files matched by strict allowlist: {len(included_files)}")

    # 2. Build the ZIP archive
    manifest_entries = []
    with zipfile.ZipFile(RELEASE_ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for full_path, arcname in included_files:
            file_hash = sha256_file(full_path)
            manifest_entries.append(f"{file_hash}  {arcname}")
            zf.write(full_path, arcname)

    # 3. Freeze archive and compute archive SHA-256
    zip_hash = sha256_file(RELEASE_ZIP_PATH)
    zip_size_mb = RELEASE_ZIP_PATH.stat().st_size / (1024 * 1024)
    print(f"[OK] Release ZIP created: {RELEASE_ZIP_PATH}")
    print(f"     Size: {zip_size_mb:.2f} MB | Archive SHA-256: {zip_hash}")

    # 4. Write Authoritative Release Manifest ONLY AFTER release contents are frozen
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    manifest_content = (
        f"# CREDENCE CORE v1.0.0 AUTHORITATIVE FINAL RELEASE MANIFEST\n"
        f"# Archive: {RELEASE_ZIP_NAME}\n"
        f"# Archive-SHA256: {zip_hash}\n"
        f"# Total-Packaged-Files: {len(included_files)}\n"
        f"# Generated: {now_iso}\n\n"
        + "\n".join(manifest_entries) + "\n"
    )
    with open(MANIFEST_PATH, "w", encoding="utf-8") as mf:
        mf.write(manifest_content)

    dist_manifest = DIST_DIR / "FINAL_RELEASE_MANIFEST.sha256"
    with open(dist_manifest, "w", encoding="utf-8") as mf:
        mf.write(manifest_content)

    print(f"[OK] Authoritative manifest generated at: {MANIFEST_PATH} and {dist_manifest}")

    # 5. Self-Verification Gate: verify archive immediately
    print("[*] Running immediate verification on packaged archive...")
    with zipfile.ZipFile(RELEASE_ZIP_PATH, "r") as zf:
        infolist = zf.infolist()
        if len(infolist) != len(included_files):
            print(f"[FAIL] Entry count mismatch: expected {len(included_files)}, found {len(infolist)}")
            sys.exit(1)
        for info in infolist:
            name_lower = info.filename.lower()
            for denied_ext in DENY_EXTENSIONS:
                if name_lower.endswith(denied_ext):
                    print(f"[FAIL] Forbidden file packaged in release: {info.filename}")
                    sys.exit(1)
            for denied_name in DENY_NAMES:
                if Path(info.filename).name.lower() == denied_name.lower():
                    print(f"[FAIL] Forbidden file packaged in release: {info.filename}")
                    sys.exit(1)

    print("[PASS] Packaging gate successfully validated.")


if __name__ == "__main__":
    main()
