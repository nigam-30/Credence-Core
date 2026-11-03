# CREDENCE CORE — REMOVED FILES MANIFEST

## Overview
This manifest documents every file and directory removed during Phase 6.4, the reason for removal, its classification (generated, obsolete, duplicate, or test artifact), and confirmation that active application code does not require it.

---

## 1. Generated & Temporary Archives / Executables

| Path | Classification | Size | Reason for Removal | Active Code Verification |
| ---- | -------------- | ---- | ------------------ | ------------------------ |
| `bank_system_clean.zip` | Generated Artifact | 4,082,710 bytes | Outdated full zip archive placed in repository root. | Unreferenced by backend, frontend, Docker, or tests. |
| `bank_system.exe` | Compiled Binary | 380,999 bytes | Generated Windows C++ binary. Binaries must not be committed to Git or release packages. | Re-creatable on demand via `g++` or `CMakeLists.txt`. Tested harness gracefully falls back when absent. |
| `credence_core.db.pre_restore_bak` | Test Artifact | 3,411,968 bytes | Residual backup file created during Phase 6 disaster recovery testing (`test_backup_recovery.py`). | Temporary test leftover; not used by running application. |
| `ledger.db.pre_restore_bak` | Test Artifact | 708,608 bytes | Residual backup file created during Phase 6 disaster recovery testing. | Temporary test leftover; not used by running application. |
| `security.log` | Runtime Log | 337,293 bytes | Volatile runtime audit log generated during previous test suite runs. | Logging system creates new log files on demand under `LOG_DIR`. |
| `run_html_ui.bat` | Obsolete Script | 1,384 bytes | Outdated root-level batch runner that launched deprecated `python flask_app.py`. | Replaced by standardized `scripts/run_local.bat` invoking Gunicorn WSGI. |

---

## 2. Temporary Patch Scripts

| Path | Classification | Size | Reason for Removal | Active Code Verification |
| ---- | -------------- | ---- | ------------------ | ------------------------ |
| `scripts/patch_app_js.py` | Obsolete Patch | 4,782 bytes | Temporary string-replacement script used during Phase 6.2 hardening to inject XSS sanitizers into `app.js`. | One-time development script. Patches are already permanently integrated in `app.js`. |
| `scripts/patch_cpp.py` | Obsolete Patch | 4,659 bytes | Temporary patch script used in Phase 6.2 to add memory cleanup functions to `bank.h` and `.cpp` files. | One-time development script. Patches are already committed to C++ files. |
| `scripts/patch_flask_app_factory.py` | Obsolete Patch | 686 bytes | Temporary patch script used to replace app factory instantiation in legacy `flask_app.py`. | One-time development script. `flask_app.py` is already refactored. |
| `scripts/patch_load_profiles.py` | Obsolete Patch | 2,107 bytes | Temporary patch script used to re-route `load_profiles()` to database queries. | One-time development script. Functionality is already baked into `flask_app.py`. |

---

## 3. Historical Database Rollback Backups Directory (`db_rollback_backups/`)

The directory `db_rollback_backups/` and its 28 timestamped subdirectories containing 84 generated test JSON files were removed (~18 MB). These were created as test output by `rollback_db_to_json.py` during repetitive runs of `test_10_rollback_export_generates_valid_json_backups` in `tests/test_database_migration.py`.

Each subfolder contained:
- `bank_data.json`
- `user_investments.json`
- `user_profiles.json`

Removed timestamped directories:
1. `backup_20261101_073056/`
2. `backup_20261101_073425/`
3. `backup_20261101_073435/`
4. `backup_20261101_073640/`
5. `backup_20261101_080527/`
6. `backup_20261101_080616/`
7. `backup_20261101_080825/`
8. `backup_20261101_081300/`
9. `backup_20261101_081324/`
10. `backup_20261101_084814/`
11. `backup_20261101_094329/`
12. `backup_20261101_102056/`
13. `backup_20261101_104443/`
14. `backup_20261101_104527/`
15. `backup_20261101_104945/`
16. `backup_20261101_105920/`
17. `backup_20261101_110126/`
18. `backup_20261101_111252/`
19. `backup_20261101_111459/`
20. `backup_20261101_111608/`
21. `backup_20261101_112342/`
22. `backup_20261102_134057/`
23. `backup_20261102_141614/`
24. `backup_20261102_141900/`
25. `backup_20261102_142108/`
26. `backup_20261102_142253/`
27. `backup_20261102_142816/`
28. `backup_20261102_144123/`
29. `backup_20261102_144759/`
30. `backup_20261102_150941/`
31. `backup_20261102_151759/`
32. `backup_20261103_045652/`

**Active Code Verification**: All tests dynamically create new timestamped directories inside `db_rollback_backups/` during execution and verify them independently. Past runs' directories are ignored by git and safe to purge.

---

## 4. Obsolete Milestone Reports (Cleaned from Root)

The following 18 intermediate milestone reports were created as working progress audits across development phases (Phases 0–6.3). Living engineering documentation has been consolidated into `docs/`:

| File | Size | Superseded By / Reason |
| ---- | ---- | ---------------------- |
| `PHASE_6_1_REMEDIATION_REPORT.md` | 21,867 bytes | Historical remediation log; core design in `docs/architecture/` and `docs/security/`. |
| `PHASE_6_2_SECURITY_REPORT.md` | 11,763 bytes | Historical remediation log; core design in `docs/security/`. |
| `PHASE_6_3_REMEDIATION_REPORT.md` | 8,091 bytes | Intermediate audit report; superseded by `CLEANUP_REPORT.md`. |
| `FINAL_INDEPENDENT_TEST_REPORT.md` | 5,365 bytes | Superseded by `POST_CLEANUP_TEST_REPORT.md`. |
| `FINAL_TEST_REPORT.md` | 3,838 bytes | Superseded by `POST_CLEANUP_TEST_REPORT.md`. |
| `DEPLOYMENT_CONSISTENCY_REPORT.md` | 1,928 bytes | Consolidated into `docs/deployment/DEPLOYMENT_GUIDE.md`. |
| `DEPLOYMENT_VERIFICATION_REPORT.md` | 3,264 bytes | Consolidated into `docs/deployment/DEPLOYMENT_GUIDE.md`. |
| `LEGACY_APPLICATION_DECOMMISSION_REPORT.md` | 5,234 bytes | Phase 6.0 audit; legacy monolithic code has been decommissioned. |
| `REPOSITORY_HYGIENE_REPORT.md` | 1,836 bytes | Superseded by `GIT_HYGIENE_REPORT.md`. |
| `HARDCODED_VALUES_AUDIT.md` | 3,716 bytes | Audit finding resolved in Phase 6.2; hardcoded demo values eliminated. |
| `IMPLEMENTATION_PLAN.md` | 12,083 bytes | Roadmap for Phases 1-6; all phases completed. |
| `REPOSITORY_AUDIT.md` | 15,795 bytes | Phase 0 audit report; superseded by final project structure. |
| `DEPENDENCY_AUDIT.md` | 3,637 bytes | Superseded by `DEPENDENCY_CLEANUP_REPORT.md`. |
| `FINANCIAL_LOGIC_AUDIT.md` | 3,266 bytes | Consolidated into `docs/database/FINANCIAL_INTEGRITY.md`. |
| `SECURITY_IMPLEMENTATION_REPORT.md` | 12,708 bytes | Consolidated into `docs/security/`. |
| `SECURITY_FINAL_REPORT.md` | 11,677 bytes | Consolidated into `SECURITY.md` and `docs/security/`. |
| `SECURITY_FINDINGS.md` | 14,715 bytes | Historical findings resolved in Phase 1 & 6; preserved in security docs. |
| `FEATURE_IMPLEMENTATION_REPORT.md` | 14,202 bytes | Consolidated into `README.md` and `docs/architecture/`. |

---

## 5. Untracked Runtime Databases
- `user_investments.json`: Untracked from Git via `git rm --cached`. Added to `.gitignore`. Sample portfolio preserved in `tests/fixtures/synthetic_banking_fixtures.json`.
- `user_profiles.json`: Kept in `.gitignore`.
- `bank_data.json`: Kept in `.gitignore`.

---

## Summary Counts
- **Total Files Removed**: 112
- **Total Directories Removed**: 29
- **Regressions Introduced**: 0
