"""
Credence Core — Controlled Deployment Migration Script
Executes database schema migrations and validation as an explicit pre-deploy step.
Ensures zero-downtime, verified database ready state before application startup.
"""

import sys
import os
import logging

# Ensure root directory is on Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import init_db, get_db_url, mask_database_url, IS_POSTGRES, IS_PRODUCTION, engine
import ledger

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] [MIGRATION] %(message)s")
logger = logging.getLogger("credence.migration")


def run_deployment_migrations():
    """Execute all schema checks, table initializations, and system accounts."""
    db_url = get_db_url()
    logger.info(f"Initiating controlled deployment migrations against: {mask_database_url(db_url)}")

    if IS_PRODUCTION and not IS_POSTGRES:
        logger.error("FATAL: Production migrations require PostgreSQL. SQLite is forbidden in production.")
        sys.exit(1)

    try:
        # Step 1: Verify database engine connectivity
        with engine.connect() as conn:
            logger.info("Database connectivity verified.")

        # Step 2: Initialize / update tables and schema
        logger.info("Applying database schemas and column upgrades...")
        init_db()
        logger.info("Database schema applied successfully.")

        # Step 3: Ensure System GL Accounts exist in double-entry ledger
        logger.info("Ensuring system General Ledger accounts...")
        engine_inst = ledger.FinancialIntegrityEngine()
        engine_inst._init_db()
        logger.info("General Ledger system accounts verified.")

        # Step 4: Verify mathematical balance integrity of ledger
        logger.info("Verifying ledger reconciliation...")
        recon = engine_inst.reconcile_ledger()
        if recon["status"] != "HEALTHY" and recon["total_transactions"] > 0:
            logger.error(f"FATAL: Ledger discrepancy detected during migration: {recon}")
            sys.exit(1)
        logger.info(f"Ledger reconciliation check passed: Status={recon['status']}, Discrepancy={recon['discrepancy_paise']} paise.")

        logger.info("Controlled deployment migration completed successfully.")
        return 0

    except Exception as e:
        logger.critical(f"FATAL: Deployment migration failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    sys.exit(run_deployment_migrations())
