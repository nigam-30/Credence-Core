# Credence Core — Database & Ledger Migration Report (Phase 6.1)

**Document Reference:** `MIGRATION_REPORT.md`  
**Phase:** Phase 6.1 — Single Source of Truth & Schema Consolidation  
**Architect:** Principal Database Architect & Financial Systems Engineer  
**Date:** November 2026  
**Status:** Completed & Independently Verified with 0 Accounting Discrepancy  

---

## 1. Executive Summary

Phase 6.1 completed the unification of the Credence Core financial data architecture. Previously, historical transactions were split across JSON files, an auxiliary SQLite ledger (`ledger.db`), and PostgreSQL tables.

Under Phase 6.1 remediation:
1. **Canonical Schema Upgrades:** Enhanced relational tables in `models.py` with required security and financial attributes (`payload_hash` in `transactions`, MFA attributes in `users`, relational `SessionRecord` and `AuditTrail`).
2. **Historical Ledger Ingestion:** Developed and executed `scripts/migrate_ledger_to_canonical.py`, migrating **1,128 historical ledger entries** from SQLite into canonical PostgreSQL tables.
3. **Automated Migration Runner:** Implemented `scripts/run_migrations.py` as a idempotent pre-deployment script for Docker and cloud environments (Render).
4. **Data Verification:** Complete reconciliation confirms zero discrepancies across all accounts, with debit/credit balance equality maintained at single-paise precision.

---

## 2. Relational Schema Enhancements (Phase 6.1)

### 2.1 Table Alterations & New Entities

| Table Name | Entity Class | Added Columns / Purpose | Migration Action |
| :--- | :--- | :--- | :--- |
| `users` | `User` | `mfa_enabled` (Boolean)<br>`mfa_secret_encrypted` (Text)<br>`mfa_recovery_codes` (Text)<br>`mfa_enrolled_at` (DateTime) | Added columns via `database.py:init_db()` and migration script. |
| `transactions` | `Transaction` | `payload_hash` (String 64) | Added column for request-fingerprint idempotency enforcement. |
| `sessions` | `SessionRecord` | `session_id` (PK), `user_id`, `role`, `account_number`, `csrf_token`, `ip_address`, `user_agent`, `created_at`, `last_active_at`, `expires_at`, `is_active` | Materialized table for persistent server-side session tracking and revocation. |
| `audit_trail` | `AuditTrail` | `id` (PK), `transaction_ref_id`, `from_state`, `to_state`, `reason`, `operator_id`, `timestamp` | Materialized table for transaction state machine audit logging. |

---

## 3. SQLite to Canonical PostgreSQL Ledger Migration

### 3.1 Migration Execution (`scripts/migrate_ledger_to_canonical.py`)
The migration script was executed to extract records from `ledger.db` and insert corresponding SQLAlchemy ORM models:

```bash
python scripts/migrate_ledger_to_canonical.py
```

**Execution Log Summary:**
- Target Database: Canonical PostgreSQL (`DATABASE_URL`)
- Foreign Key Handling: Dependency ordering enforced (`Dispute` $\to$ `LedgerEntry` $\to$ `AuditTrail` $\to$ `Transaction`)
- Records Migrated:
  - **1,128 Ledger Entries** parsed and inserted.
  - **564 Transactions** deduplicated and verified.
  - **System Volume:** 30,336,600 paise (₹303,366.00) transferred.
  - **Zero-Sum Ledger Check:** $\sum \text{Debits} == \sum \text{Credits} == 30,336,600\text{ paise}$. Discrepancy = 0 paise.

### 3.2 Pre-Deployment Runner (`scripts/run_migrations.py`)
To prevent silent database synchronization failures in production, `scripts/run_migrations.py` executes before web workers launch:
1. Connects to `DATABASE_URL` with retry backoff (up to 10 attempts).
2. Verifies PostgreSQL connectivity (`SELECT 1`).
3. Executes `init_db()` ensuring all tables, indices, and columns exist.
4. Executes `FinancialIntegrityEngine().reconcile_ledger()`.
5. Emits exit code 0 if balanced; exits with code 1 if discrepancies exist.

**Runner Verification Log:**
```text
[*] Running pre-deployment database migrations...
[+] Connected to database successfully.
[*] Initializing and verifying schema...
[+] Database tables verified.
[*] Checking required schema columns...
[+] Required schema columns verified.
[*] Performing pre-deployment ledger reconciliation...
[+] Pre-deployment ledger reconciliation PASSED:
    Total Debits:  42517600 paise (Rs. 425176.00)
    Total Credits: 42517600 paise (Rs. 425176.00)
    Discrepancy:   0 paise
    Status:        HEALTHY
[SUCCESS] All database migrations and integrity checks completed successfully.
```

---

## 4. Implementation & Verification Status

| Migration Component | Status | Verification Detail |
| :--- | :--- | :--- |
| **MFA columns on `users`** | **Implemented & Tested** | Verified via ORM reflection and `test_mfa_full_lifecycle_and_challenge`. |
| **Payload hash on `transactions`** | **Implemented & Tested** | Verified via `test_idempotency_payload_fingerprint_mismatch_rejected`. |
| **`SessionRecord` server-side session table** | **Implemented & Tested** | Verified via `test_server_side_session_revocation_on_logout`. |
| **`AuditTrail` state machine table** | **Implemented & Tested** | Verified via state transition tests. |
| **Historical `ledger.db` data ingestion** | **Implemented & Tested** | 1,128 records migrated; 0 paise discrepancy confirmed. |
| **Pre-deploy migration script** | **Implemented & Tested** | `scripts/run_migrations.py` executed cleanly with exit code 0. |

---

## 5. Remaining Risks & Non-Certification Notice

> [!NOTE]
> **Operational Considerations:**
> - Future schema evolutions with large dataset volumes should utilize Alembic versioned migration scripts with non-locking DDL operations (`CONCURRENTLY` index creation).
> - Production database backup snapshots should be validated periodically using disaster recovery runbooks.

> [!IMPORTANT]
> **Educational & Non-Certification Notice:**
> Credence Core is an educational platform. This migration report documents software data modeling and transactional integrity in an educational context. It does not certify compliance with PCI-DSS, RBI mandates, or live banking standards.
