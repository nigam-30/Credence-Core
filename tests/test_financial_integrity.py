"""
Credence Core — Phase 2: Financial Integrity Engine Test Suite
Automated verification of double-entry ledger, idempotency, atomic commits,
integer paise precision, overdraft prevention, concurrent transfers, reversals,
and ledger reconciliation.
"""

import unittest
import threading
import uuid
from decimal import Decimal
from flask_app import app, bank
import ledger
from ledger import (
    ledger_engine,
    rupees_to_paise,
    paise_to_rupees,
    format_rupees,
    GL_CASH_VAULT,
    GL_CLEARING_ESCROW,
    GL_BILL_PAYMENT_CLEARING,
    GL_MERCHANT_SETTLEMENT,
    GL_INVESTMENT_ESCROW,
    GL_GOLD_VAULT_CLEARING,
    GL_LOAN_PRINCIPAL,
    GL_FIXED_DEPOSIT_RESERVE,
    GL_ASBA_IPO_ESCROW,
    STATE_SUCCESSFUL,
    STATE_FAILED,
    STATE_REVERSED,
    InsufficientFundsError,
    LimitExceededError,
    DuplicateTransactionError,
    InvalidAmountError,
    AccountNotFoundError
)
import security

class CredenceFinancialIntegrityTestSuite(unittest.TestCase):

    def setUp(self):
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = True
        self.client = app.test_client()
        self.uid = uuid.uuid4().hex[:6].upper()

    def _login(self, client, account="40273146502136", role="user"):
        with client.session_transaction() as sess:
            sess["user_id"] = str(account)
            sess["role"] = role
            sess["auth_time"] = 9999999999.0
            sess["csrf_token"] = security.generate_csrf_token()
            token = sess["csrf_token"]
        return token

    # 1. IMMUTABLE DOUBLE-ENTRY ACCOUNTING LEDGER
    def test_double_entry_balance_invariant(self):
        """Every transaction must have equal total debits and total credits."""
        acc_a = f"ACC_DE_A_{self.uid}"
        acc_b = f"ACC_DE_B_{self.uid}"
        ledger_engine.ensure_account(acc_a, 0)
        ledger_engine.ensure_account(acc_b, 0)

        # Deposit ₹5,000 into acc_a
        txn_dep = ledger_engine.execute_transaction(
            transaction_type="DEPOSIT",
            amount_rupees="5000.00",
            source_account=GL_CASH_VAULT,
            destination_account=acc_a,
            description="Initial Funding"
        )
        self.assertEqual(txn_dep["state"], STATE_SUCCESSFUL)

        # Transfer ₹1,500 from acc_a to acc_b
        txn_xfer = ledger_engine.execute_transaction(
            transaction_type="TRANSFER_IMPS",
            amount_rupees="1500.00",
            source_account=acc_a,
            destination_account=acc_b,
            description="Inter-account IMPS"
        )
        self.assertEqual(txn_xfer["state"], STATE_SUCCESSFUL)

        # Verify legs in ledger_entries table for this reference_id
        with ledger_engine._db_session() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT direction, amount_paise, account_number
                FROM ledger_entries WHERE reference_id = ?
            """, (txn_xfer["reference_id"],))
            legs = cursor.fetchall()
            self.assertEqual(len(legs), 2, "Transaction must consist of exactly 2 double-entry legs")

            debits = sum(leg["amount_paise"] for leg in legs if leg["direction"] == "DEBIT")
            credits = sum(leg["amount_paise"] for leg in legs if leg["direction"] == "CREDIT")
            self.assertEqual(debits, 150000)
            self.assertEqual(credits, 150000)
            self.assertEqual(debits, credits, "Debits and credits must balance exactly")

    # 2. UNIQUE TRANSACTION REFERENCE IDs
    def test_unique_reference_ids(self):
        """Transactions must have globally unique reference IDs matching standard prefix."""
        refs = set()
        acc = f"ACC_REF_{self.uid}"
        ledger_engine.ensure_account(acc, 0)

        for i in range(10):
            txn = ledger_engine.execute_transaction(
                transaction_type="DEPOSIT",
                amount_rupees="10.00",
                source_account=GL_CASH_VAULT,
                destination_account=acc,
                description=f"Deposit batch {i}"
            )
            ref = txn["reference_id"]
            self.assertTrue(ref.startswith("TXN-"), f"Reference {ref} did not match TXN prefix")
            self.assertNotIn(ref, refs, f"Duplicate reference ID detected: {ref}")
            refs.add(ref)

    # 3. INTEGER PAISE & PRECISION MONETARY CALCULATIONS
    def test_integer_paise_precision(self):
        """Monetary calculations must use exact integer paise, eliminating float errors."""
        paise_1 = rupees_to_paise("0.10")
        paise_2 = rupees_to_paise("0.20")
        paise_sum = paise_1 + paise_2
        self.assertEqual(paise_sum, 30)
        self.assertEqual(paise_to_rupees(paise_sum), Decimal("0.30"))

        # String formatting and conversion
        self.assertEqual(rupees_to_paise("1,234.56"), 123456)
        self.assertEqual(rupees_to_paise("₹ 9,999.99"), 999999)
        self.assertEqual(format_rupees(999999), "₹9,999.99")

    # 4. REJECTION OF ZERO, NEGATIVE, NAN AND INFINITE AMOUNTS
    def test_reject_invalid_amounts(self):
        """Zero, negative, NaN, Infinite, and sub-paise amounts must be strictly rejected."""
        invalid_inputs = [
            0,
            "0",
            "0.00",
            -10,
            "-50.00",
            "NaN",
            "nan",
            "Inf",
            "-Infinity",
            "+infinity",
            "",
            None,
            "10.555"
        ]
        for val in invalid_inputs:
            with self.assertRaises(InvalidAmountError, msg=f"Should have rejected invalid amount: {val}"):
                rupees_to_paise(val)

    # 5. OVERDRAFT PREVENTION & AVAILABLE BALANCE
    def test_overdraft_prevention(self):
        """Attempting to withdraw or transfer more than available balance must fail."""
        acc = f"ACC_OD_{self.uid}"
        ledger_engine.ensure_account(acc, 0)

        # Deposit ₹500
        ledger_engine.execute_transaction(
            transaction_type="DEPOSIT",
            amount_rupees="500.00",
            source_account=GL_CASH_VAULT,
            destination_account=acc,
            description="Seed Funds"
        )

        # Attempt to transfer ₹501 (1 rupee overdraft)
        with self.assertRaises(InsufficientFundsError):
            ledger_engine.execute_transaction(
                transaction_type="TRANSFER_IMPS",
                amount_rupees="501.00",
                source_account=acc,
                destination_account=GL_CLEARING_ESCROW,
                description="Overdraft Attempt"
            )

        # Ensure balance is unchanged
        bal = ledger_engine.get_account_balance(acc)
        self.assertEqual(bal["balance_paise"], 50000)

    # 6. IDEMPOTENCY KEYS & REPEATED REQUESTS
    def test_idempotency_keys_prevent_double_execution(self):
        """Repeating a transaction with the same idempotency key must replay cached response without re-debiting."""
        acc_src = f"ACC_IDEM_SRC_{self.uid}"
        acc_dst = f"ACC_IDEM_DST_{self.uid}"
        ledger_engine.ensure_account(acc_src, 0)
        ledger_engine.ensure_account(acc_dst, 0)

        # Seed acc_src with ₹1,000
        ledger_engine.execute_transaction(
            transaction_type="DEPOSIT",
            amount_rupees="1000.00",
            source_account=GL_CASH_VAULT,
            destination_account=acc_src,
            description="Initial deposit"
        )

        idempotency_key = f"IDEM-KEY-{self.uid}"

        # 1st attempt: Execute
        res1 = ledger_engine.execute_transaction(
            transaction_type="TRANSFER_IMPS",
            amount_rupees="250.00",
            source_account=acc_src,
            destination_account=acc_dst,
            description="Payment with key",
            idempotency_key=idempotency_key
        )
        self.assertTrue(res1["success"])
        ref1 = res1["reference_id"]

        # Verify source balance is ₹750
        self.assertEqual(ledger_engine.get_account_balance(acc_src)["balance_paise"], 75000)

        # 2nd attempt: Replay same request with same key
        res2 = ledger_engine.execute_transaction(
            transaction_type="TRANSFER_IMPS",
            amount_rupees="250.00",
            source_account=acc_src,
            destination_account=acc_dst,
            description="Payment with key",
            idempotency_key=idempotency_key
        )
        self.assertTrue(res2["success"])
        self.assertTrue(res2.get("idempotent_replay", False), "Must be marked as idempotent replay")
        self.assertEqual(res2["reference_id"], ref1, "Must return original reference ID")

        # Source balance must STILL be ₹750 (NO second debit of ₹250 occurred!)
        self.assertEqual(ledger_engine.get_account_balance(acc_src)["balance_paise"], 75000)
        self.assertEqual(ledger_engine.get_account_balance(acc_dst)["balance_paise"], 25000)

    # 7. CONCURRENT TRANSFERS & RACE CONDITION PREVENTION
    def test_concurrent_transfers_no_race_condition(self):
        """Concurrent requests attempting to spend beyond balance must be serialized without overdraft."""
        acc_source = f"ACC_RACE_SRC_{self.uid}"
        acc_target = f"ACC_RACE_DST_{self.uid}"
        ledger_engine.ensure_account(acc_source, 0)
        ledger_engine.ensure_account(acc_target, 0)

        # Seed source account with exactly ₹1,000
        ledger_engine.execute_transaction(
            transaction_type="DEPOSIT",
            amount_rupees="1000.00",
            source_account=GL_CASH_VAULT,
            destination_account=acc_source,
            description="Race Seed"
        )

        successes = []
        failures = []

        def attempt_transfer(idx):
            try:
                res = ledger_engine.execute_transaction(
                    transaction_type="TRANSFER_IMPS",
                    amount_rupees="200.00",
                    source_account=acc_source,
                    destination_account=acc_target,
                    description=f"Concurrent attempt #{idx}"
                )
                successes.append(res)
            except InsufficientFundsError:
                failures.append(idx)
            except Exception as e:
                failures.append(str(e))

        # Launch 10 concurrent threads (Total attempted: 10 * ₹200 = ₹2,000 against ₹1,000 balance)
        threads = [threading.Thread(target=attempt_transfer, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Exactly 5 transfers should succeed (5 * ₹200 = ₹1,000) and 5 should fail with InsufficientFundsError
        self.assertEqual(len(successes), 5, f"Expected exactly 5 successes, got {len(successes)}")
        self.assertEqual(len(failures), 5, f"Expected exactly 5 failures, got {len(failures)}")

        # Source balance MUST be exactly 0, never negative
        final_src_bal = ledger_engine.get_account_balance(acc_source)["balance_paise"]
        final_dst_bal = ledger_engine.get_account_balance(acc_target)["balance_paise"]
        self.assertEqual(final_src_bal, 0, "Source balance must be exactly 0 (no overdraft)")
        self.assertEqual(final_dst_bal, 100000, "Target balance must be exactly ₹1,000")

    # 8. TRANSACTION STATES & AUDIT TRAIL
    def test_transaction_states_lifecycle(self):
        """Transactions must transition across standard states and maintain an audit trail."""
        acc = f"ACC_STATE_{self.uid}"
        ledger_engine.ensure_account(acc, 0)

        txn = ledger_engine.execute_transaction(
            transaction_type="DEPOSIT",
            amount_rupees="300.00",
            source_account=GL_CASH_VAULT,
            destination_account=acc,
            description="State test"
        )
        ref = txn["reference_id"]
        self.assertEqual(txn["state"], STATE_SUCCESSFUL)

        # Check audit trail for this reference
        with ledger_engine._db_session() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT action, from_state, to_state
                FROM audit_trail WHERE reference_id = ?
                ORDER BY audit_id ASC
            """, (ref,))
            audit_events = cursor.fetchall()
            self.assertTrue(len(audit_events) >= 2)
            self.assertEqual(audit_events[-1]["to_state"], STATE_SUCCESSFUL)

    # 9. REVERSALS INSTEAD OF EDITING HISTORICAL LEDGER ENTRIES
    def test_reversals_compensating_entries(self):
        """Reversals must not edit or delete historical rows; they must add opposing double-entry legs."""
        acc_a = f"ACC_REV_A_{self.uid}"
        acc_b = f"ACC_REV_B_{self.uid}"
        ledger_engine.ensure_account(acc_a, 0)
        ledger_engine.ensure_account(acc_b, 0)

        # Seed acc_a with ₹2,000
        ledger_engine.execute_transaction(
            transaction_type="DEPOSIT",
            amount_rupees="2000.00",
            source_account=GL_CASH_VAULT,
            destination_account=acc_a,
            description="Funding"
        )

        # Transfer ₹800 from A to B
        orig_txn = ledger_engine.execute_transaction(
            transaction_type="TRANSFER_IMPS",
            amount_rupees="800.00",
            source_account=acc_a,
            destination_account=acc_b,
            description="Erroneous Transfer"
        )
        orig_ref = orig_txn["reference_id"]

        self.assertEqual(ledger_engine.get_account_balance(acc_a)["balance_paise"], 120000)
        self.assertEqual(ledger_engine.get_account_balance(acc_b)["balance_paise"], 80000)

        # Reverse the transfer
        rev_res = ledger_engine.reverse_transaction(
            reference_id=orig_ref,
            reason="Fraudulent unauthorized transaction",
            actor="COMPLIANCE_OFFICER"
        )
        self.assertTrue(rev_res["success"])
        rev_ref = rev_res["reversal_reference_id"]

        # Check that original transaction state is REVERSED
        with ledger_engine._db_session() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT state FROM transactions WHERE reference_id = ?", (orig_ref,))
            self.assertEqual(cursor.fetchone()["state"], STATE_REVERSED)

            # Check that reversal transaction is SUCCESSFUL with type REVERSAL
            cursor.execute("SELECT state, transaction_type, original_reference_id FROM transactions WHERE reference_id = ?", (rev_ref,))
            rev_row = cursor.fetchone()
            self.assertEqual(rev_row["state"], STATE_SUCCESSFUL)
            self.assertEqual(rev_row["transaction_type"], "REVERSAL")
            self.assertEqual(rev_row["original_reference_id"], orig_ref)

        # Balances must be fully restored
        self.assertEqual(ledger_engine.get_account_balance(acc_a)["balance_paise"], 200000)
        self.assertEqual(ledger_engine.get_account_balance(acc_b)["balance_paise"], 0)

    # 10. FULL LEDGER RECONCILIATION
    def test_ledger_mathematical_reconciliation(self):
        """Mathematical reconciliation must verify Sum(Debits) == Sum(Credits) with 0 discrepancy."""
        recon = ledger_engine.reconcile_ledger()
        self.assertEqual(recon["status"], "HEALTHY")
        self.assertEqual(recon["discrepancy_paise"], 0)
        self.assertEqual(recon["total_system_debits_paise"], recon["total_system_credits_paise"])
        self.assertEqual(len(recon["account_discrepancies"]), 0, f"Account discrepancies found: {recon['account_discrepancies']}")

    # 11. END-TO-END FINANCIAL OPERATIONS VIA REST API
    def test_e2e_financial_operations_api(self):
        """Verify API mutations (Deposit, Transfer, Bill Pay) update double-entry ledger."""
        csrf_token = self._login(self.client, account="40273146502136", role="user")
        idem_suffix = uuid.uuid4().hex[:6]

        # 1. Deposit via API
        res_dep = self.client.post(
            "/api/deposit",
            json={"amount": "1000", "idempotency_key": f"DEP-API-{idem_suffix}"},
            headers={"X-CSRF-Token": csrf_token}
        )
        self.assertEqual(res_dep.status_code, 200)
        data_dep = res_dep.get_json()
        self.assertTrue(data_dep.get("success"))
        self.assertTrue("reference_id" in data_dep)
        ref_dep = data_dep["reference_id"]

        # Verify double-entry ledger entry was created
        with ledger_engine._db_session() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM ledger_entries WHERE reference_id = ?", (ref_dep,))
            self.assertEqual(len(cursor.fetchall()), 2)

        # 2. Transfer via API
        res_xfer = self.client.post(
            "/api/transfer",
            json={"to_acc": "99999999999999", "amount": "200", "method": "IMPS", "idempotency_key": f"XFER-API-{idem_suffix}"},
            headers={"X-CSRF-Token": csrf_token}
        )
        self.assertEqual(res_xfer.status_code, 200)
        data_xfer = res_xfer.get_json()
        self.assertTrue(data_xfer.get("success"))
        self.assertTrue("reference_id" in data_xfer)

        # 3. Bill Pay via API
        res_bill = self.client.post(
            "/api/pay_bill",
            json={"biller": "Electricity", "company": "Tata Power", "amount": "150", "method": "Account Balance"},
            headers={"X-CSRF-Token": csrf_token}
        )
        self.assertEqual(res_bill.status_code, 200)
        data_bill = res_bill.get_json()
        self.assertTrue(data_bill.get("success"))
        self.assertTrue("reference_id" in data_bill)

        # Final full system reconciliation
        recon = ledger_engine.reconcile_ledger()
        self.assertEqual(recon["status"], "HEALTHY")
        self.assertEqual(recon["discrepancy_paise"], 0)


if __name__ == "__main__":
    unittest.main()
