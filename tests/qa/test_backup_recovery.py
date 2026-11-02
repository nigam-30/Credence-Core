"""
Credence Core — QA Test Suite 4: Database Disaster Recovery Testing
Verifies backup creation, cryptographic checksum verification, tamper detection,
and complete ledger recovery after failure.
"""

import os
import sys
import shutil
import tempfile
import unittest

from scripts import db_backup, db_restore
import ledger


class DisasterRecoveryTestSuite(unittest.TestCase):

    def setUp(self):
        self.temp_backup_dir = tempfile.mkdtemp(prefix="credence_backup_test_")

    def tearDown(self):
        shutil.rmtree(self.temp_backup_dir, ignore_errors=True)

    def test_backup_and_restore_lifecycle(self):
        """Execute full backup and restore cycle with cryptographic integrity validation."""
        # 1. Execute Backup
        backup_dir = db_backup.run_backup(target_dir=self.temp_backup_dir, retention_days=1)
        self.assertTrue(os.path.exists(backup_dir))

        manifest_path = os.path.join(backup_dir, "manifest.json")
        checksums_path = os.path.join(backup_dir, "CHECKSUMS.sha256")
        self.assertTrue(os.path.exists(manifest_path))
        self.assertTrue(os.path.exists(checksums_path))

        # 2. Checksum validation passes on pristine backup
        self.assertTrue(db_restore.verify_backup_integrity(backup_dir))

        # 3. Simulate tamper / corruption: Append corrupted byte to ledger.db backup
        ledger_backup_file = os.path.join(backup_dir, "ledger.db")
        if os.path.exists(ledger_backup_file):
            with open(ledger_backup_file, "ab") as f:
                f.write(b"CORRUPTED_TAMPER_BYTES")

            # Must detect checksum mismatch and abort restore
            self.assertFalse(db_restore.verify_backup_integrity(backup_dir))
            restore_tampered = db_restore.run_restore(backup_dir)
            self.assertFalse(restore_tampered)

        # 4. Clean backup and restore
        clean_backup_dir = db_backup.run_backup(target_dir=self.temp_backup_dir, retention_days=1)
        restore_clean = db_restore.run_restore(clean_backup_dir)
        self.assertTrue(restore_clean)

        # 5. Ledger reconciliation invariant
        rec = ledger.ledger_engine.reconcile_ledger()
        self.assertIn(rec["status"], ("HEALTHY", "BALANCED"))
        self.assertEqual(rec["discrepancy_paise"], 0)


if __name__ == "__main__":
    unittest.main()
