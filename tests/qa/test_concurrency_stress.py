"""
Credence Core — QA Test Suite 3: Concurrency & Race-Condition Stress Testing
Verifies atomic isolation, overdraft prevention, and double-entry consistency under concurrent load.
"""

import unittest
import concurrent.futures
import uuid
import tempfile
import os
import ledger


class ConcurrencyStressTestSuite(unittest.TestCase):

    def setUp(self):
        self.temp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_file.close()
        self.temp_db_path = self.temp_file.name

        self.engine = ledger.FinancialIntegrityEngine(db_path=self.temp_db_path)
        # Seed test account with ₹5,000.00 (500,000 paise)
        self.test_src = f"STRESS_SRC_{uuid.uuid4().hex[:6]}"
        self.test_dst = f"STRESS_DST_{uuid.uuid4().hex[:6]}"

        with self.engine._db_session() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO accounts (account_number, account_type, balance_paise, status) VALUES (?, 'SAVINGS', 0, 'ACTIVE')",
                (self.test_src,)
            )
            cursor.execute(
                "INSERT INTO accounts (account_number, account_type, balance_paise, status) VALUES (?, 'SAVINGS', 0, 'ACTIVE')",
                (self.test_dst,)
            )
            conn.commit()

        # Execute legitimate ledger deposit so ledger entries balance perfectly
        self.engine.execute_transaction(
            transaction_type="DEPOSIT",
            amount_rupees=5000.0,
            source_account=ledger.GL_CASH_VAULT,
            destination_account=self.test_src,
            description="Initial stress test seed deposit"
        )

    def tearDown(self):
        if hasattr(self, "temp_db_path") and os.path.exists(self.temp_db_path):
            try:
                os.remove(self.temp_db_path)
            except Exception:
                pass

    def test_concurrent_transfers_overdraft_prevention(self):
        """
        Execute 20 concurrent threads attempting to transfer ₹400.00 (40,000 paise) each.
        Total requested: ₹8,000.00. Available: ₹5,000.00.
        Exactly 12 transfers should succeed (12 * 400 = 4,800), 8 must fail with InsufficientFundsError.
        Final balance must be exactly ₹200.00 (20,000 paise). Overdrafts MUST NOT occur.
        """
        num_workers = 20
        transfer_amt = 400.00

        def do_transfer(worker_id):
            try:
                res = self.engine.execute_transaction(
                    transaction_type="CONCURRENT_STRESS_XFER",
                    amount_rupees=transfer_amt,
                    source_account=self.test_src,
                    destination_account=self.test_dst,
                    description=f"Concurrent stress test worker #{worker_id}",
                    idempotency_key=f"STRESS-KEY-{worker_id}-{uuid.uuid4().hex[:6]}"
                )
                return {"success": True, "ref": res["reference_id"]}
            except ledger.InsufficientFundsError:
                return {"success": False, "reason": "INSUFFICIENT_FUNDS"}
            except Exception as e:
                return {"success": False, "reason": str(e)}

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [executor.submit(do_transfer, i) for i in range(num_workers)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        successes = [r for r in results if r["success"]]
        failures = [r for r in results if not r["success"]]

        print(f"\n  [Concurrency Stress] Successes: {len(successes)} | Failures: {len(failures)}")

        # Exactly 12 transfers should have succeeded (12 * 400 = 4800 paise remaining = 200)
        self.assertEqual(len(successes), 12)
        self.assertEqual(len(failures), 8)

        # Check source and destination balances
        src_bal = self.engine.get_account_balance(self.test_src)
        dst_bal = self.engine.get_account_balance(self.test_dst)

        self.assertEqual(src_bal["available_paise"], 20000)
        self.assertEqual(dst_bal["available_paise"], 480000)

        # Zero-sum verification: Source + Destination = Initial Deposit
        self.assertEqual(src_bal["available_paise"] + dst_bal["available_paise"], 500000)

        # Double-entry ledger reconciliation check
        recon = self.engine.reconcile_ledger()
        self.assertIn(recon["status"], ("HEALTHY", "BALANCED"))
        self.assertEqual(recon["discrepancy_paise"], 0)


if __name__ == "__main__":
    unittest.main()
