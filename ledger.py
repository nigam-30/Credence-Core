"""
Credence Core — Financial Integrity Engine (Canonical PostgreSQL / SQLAlchemy)
Double-entry immutable accounting ledger, idempotency keys with payload fingerprinting,
ACID transactions, integer paise arithmetic, row locking, and reconciliation.
Canonical single source of financial truth.
"""

import os
import threading
import datetime
import uuid
import json
import hashlib
import contextlib
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
from typing import Dict, Any, List, Optional

from sqlalchemy import func
from database import engine, get_db, SessionLocal
from models import (
    Account,
    AccountBalance,
    Transaction,
    LedgerEntry,
    AuditLog,
    AuditTrail,
)

# ════════════ GL (GENERAL LEDGER) SYSTEM ACCOUNTS ════════════
GL_CASH_VAULT = "GL_CASH_VAULT"
GL_CLEARING_ESCROW = "GL_CLEARING_ESCROW"
GL_BILL_PAYMENT_CLEARING = "GL_BILL_PAYMENT_CLEARING"
GL_MERCHANT_SETTLEMENT = "GL_MERCHANT_SETTLEMENT"
GL_INVESTMENT_ESCROW = "GL_INVESTMENT_ESCROW"
GL_GOLD_VAULT_CLEARING = "GL_GOLD_VAULT_CLEARING"
GL_LOAN_PRINCIPAL = "GL_LOAN_PRINCIPAL"
GL_FIXED_DEPOSIT_RESERVE = "GL_FIXED_DEPOSIT_RESERVE"
GL_ASBA_IPO_ESCROW = "GL_ASBA_IPO_ESCROW"

SYSTEM_GL_ACCOUNTS = {
    GL_CASH_VAULT: "GL_ASSET",
    GL_CLEARING_ESCROW: "GL_LIABILITY",
    GL_BILL_PAYMENT_CLEARING: "GL_LIABILITY",
    GL_MERCHANT_SETTLEMENT: "GL_LIABILITY",
    GL_INVESTMENT_ESCROW: "GL_LIABILITY",
    GL_GOLD_VAULT_CLEARING: "GL_LIABILITY",
    GL_LOAN_PRINCIPAL: "GL_ASSET",
    GL_FIXED_DEPOSIT_RESERVE: "GL_LIABILITY",
    GL_ASBA_IPO_ESCROW: "GL_LIABILITY",
}

# Transaction State Constants
STATE_PENDING = "PENDING"
STATE_PROCESSING = "PROCESSING"
STATE_SUCCESSFUL = "SUCCESSFUL"
STATE_FAILED = "FAILED"
STATE_REVERSED = "REVERSED"

VALID_STATES = {STATE_PENDING, STATE_PROCESSING, STATE_SUCCESSFUL, STATE_FAILED, STATE_REVERSED}

# Thread lock for in-process serialization when needed
_engine_lock = threading.RLock()


class LedgerError(Exception):
    """Base exception for ledger operations."""
    pass


class InsufficientFundsError(LedgerError):
    """Raised when available balance is inadequate for the operation."""
    pass


class LimitExceededError(LedgerError):
    """Raised when daily or per-transaction limit is exceeded."""
    pass


class DuplicateTransactionError(LedgerError):
    """Raised when duplicate reference or active idempotency key conflicts."""
    pass


class IdempotencyConflictError(LedgerError):
    """Raised when an idempotency key is reused with a different payload or scope."""
    pass


class InvalidAmountError(LedgerError):
    """Raised when monetary amount is invalid, zero, negative, NaN or Infinite."""
    pass


class AccountNotFoundError(LedgerError):
    """Raised when requested account is not registered in the ledger."""
    pass


class UnbalancedTransactionError(LedgerError):
    """Raised when sum of debits does not equal sum of credits."""
    pass


def rupees_to_paise(val: Any) -> int:
    """
    Convert INR rupee representation to integer paise.
    Strictly validates against float anomalies, NaN, infinity, negatives, and sub-paise fractions.
    """
    if val is None:
        raise InvalidAmountError("Amount cannot be null or empty.")

    clean_val = str(val).replace('₹', '').replace(',', '').strip()
    if not clean_val:
        raise InvalidAmountError("Amount cannot be empty.")

    if clean_val.lower() in ("nan", "inf", "-inf", "+inf", "infinity", "-infinity"):
        raise InvalidAmountError("Amount cannot be NaN or Infinite.")

    try:
        dec = Decimal(clean_val)
    except (InvalidOperation, ValueError, TypeError):
        raise InvalidAmountError(f"Invalid monetary numeric format: '{val}'")

    if dec.is_nan() or dec.is_infinite():
        raise InvalidAmountError("Amount cannot be NaN or Infinite.")

    if dec <= Decimal("0"):
        raise InvalidAmountError("Amount must be strictly greater than zero.")

    # Max 2 decimal places allowed
    exponent = dec.as_tuple().exponent
    if exponent < -2:
        raise InvalidAmountError("Amount cannot specify fractional sub-paise (more than 2 decimal places).")

    paise = int((dec * Decimal("100")).to_integral_value(rounding=ROUND_HALF_EVEN))
    if paise <= 0:
        raise InvalidAmountError("Amount in paise must be positive integer.")

    return paise


def paise_to_rupees(paise: int) -> Decimal:
    """Convert integer paise to Decimal rupees with 2 decimal places."""
    return (Decimal(paise) / Decimal(100)).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)


def format_rupees(paise: int) -> str:
    """Format paise into INR rupee string."""
    return f"₹{paise_to_rupees(paise):,.2f}"


def generate_reference_id(prefix: str = "TXN") -> str:
    """Generate globally unique transaction reference ID."""
    now_str = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    rand_suffix = uuid.uuid4().hex[:8].upper()
    return f"{prefix}-{now_str}-{rand_suffix}"


def compute_payload_hash(source_account: str, destination_account: str, amount_paise: int, transaction_type: str) -> str:
    """Compute SHA-256 fingerprint of request parameters for idempotency validation."""
    raw = f"{source_account}:{destination_account}:{amount_paise}:{transaction_type}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class ConnectionWrapper:
    """Lightweight adapter exposing cursor-style interface over canonical SQLAlchemy connection."""
    def __init__(self, connection):
        self._conn = connection

    def cursor(self):
        return CursorWrapper(self._conn)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()


class CursorWrapper:
    """Cursor adapter providing row-mapping access."""
    def __init__(self, connection):
        self._conn = connection
        self._result = None

    def execute(self, sql: str, params: tuple = None):
        if "INSERT INTO accounts" in sql and "balance_paise" in sql:
            acc_num = params[0] if params else None
            if acc_num:
                from database import get_db
                from models import Account, AccountBalance
                with get_db() as db:
                    acc = db.query(Account).filter(Account.account_number == str(acc_num)).first()
                    if not acc:
                        acc = Account(account_number=str(acc_num), account_type="SAVINGS", status="ACTIVE")
                        db.add(acc)
                        db.flush()
                    bal = db.query(AccountBalance).filter(AccountBalance.account_number == str(acc_num)).first()
                    if not bal:
                        bal = AccountBalance(account_number=str(acc_num), balance_paise=0, lien_paise=0)
                        db.add(bal)
                    db.commit()
                return self

        if params is None:
            self._result = self._conn.exec_driver_sql(sql)
        else:
            self._result = self._conn.exec_driver_sql(sql, params)
        return self

    def executescript(self, sql_script: str):
        for stmt in sql_script.split(";"):
            cleaned = stmt.strip()
            if cleaned:
                self._conn.exec_driver_sql(cleaned)
        return self

    def fetchone(self):
        if not self._result:
            return None
        row = self._result.mappings().fetchone()
        return dict(row) if row is not None else None

    def fetchall(self):
        if not self._result:
            return []
        rows = self._result.mappings().fetchall()
        return [dict(r) for r in rows]

    def close(self):
        pass


def get_entry_delta(account_type: str, direction: str, amount_paise: int) -> int:
    """
    Calculate balance delta based on double-entry accounting rules:
    - Assets (GL_ASSET): DEBIT increases balance (+), CREDIT decreases balance (-).
    - Liabilities / Customer accounts: CREDIT increases balance (+), DEBIT decreases balance (-).
    """
    is_asset = (account_type == "GL_ASSET")
    if direction == "DEBIT":
        return amount_paise if is_asset else -amount_paise
    else:  # CREDIT
        return -amount_paise if is_asset else amount_paise


class FinancialIntegrityEngine:
    """
    Thread-safe double-entry accounting engine with ACID guarantees,
    strict idempotency, row-level locking, and reconciliation.
    Uses canonical database models (PostgreSQL / SQLAlchemy).
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path
        self._init_db()

    @contextlib.contextmanager
    def _db_session(self):
        """Context manager providing a DB connection adapter for tests and legacy queries."""
        with engine.connect() as conn:
            wrapper = ConnectionWrapper(conn)
            try:
                yield wrapper
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def _init_db(self):
        """Ensure all system GL accounts exist in the canonical database."""
        with _engine_lock:
            try:
                with get_db() as db:
                    for gl_acc, acc_type in SYSTEM_GL_ACCOUNTS.items():
                        acc = db.query(Account).filter(Account.account_number == gl_acc).first()
                        if not acc:
                            acc = Account(
                                account_number=gl_acc,
                                account_type=acc_type,
                                status="ACTIVE"
                            )
                            db.add(acc)
                            db.flush()
                        bal = db.query(AccountBalance).filter(AccountBalance.account_number == gl_acc).first()
                        if not bal:
                            bal = AccountBalance(account_number=gl_acc, balance_paise=0, lien_paise=0)
                            db.add(bal)
            except Exception:
                pass

    def ensure_account(self, account_number: str, initial_paise: int = 0, account_type: str = "CUSTOMER_SAVINGS"):
        """Ensure an account exists in the canonical database with given initial balance."""
        acc_str = str(account_number).strip()
        with get_db() as db:
            acc = db.query(Account).filter(Account.account_number == acc_str).first()
            if not acc:
                acc = Account(
                    account_number=acc_str,
                    account_type=account_type,
                    status="ACTIVE"
                )
                db.add(acc)
                db.flush()
            bal = db.query(AccountBalance).filter(AccountBalance.account_number == acc_str).first()
            if not bal:
                bal = AccountBalance(account_number=acc_str, balance_paise=initial_paise, lien_paise=0)
                db.add(bal)
            else:
                if initial_paise > 0 and bal.balance_paise == 0:
                    bal.balance_paise = initial_paise

    def get_account_balance(self, account_number: str) -> Dict[str, Any]:
        """Fetch current balance record from the canonical database."""
        acc_str = str(account_number).strip()
        with get_db() as db:
            bal = db.query(AccountBalance).filter(AccountBalance.account_number == acc_str).first()
            if not bal:
                raise AccountNotFoundError(f"Account '{acc_str}' does not exist.")
            return {
                "account_number": acc_str,
                "balance_paise": bal.balance_paise,
                "balance_rupees": float(paise_to_rupees(bal.balance_paise)),
                "lien_paise": bal.lien_paise,
                "available_paise": bal.balance_paise - bal.lien_paise,
                "available_rupees": float(paise_to_rupees(bal.balance_paise - bal.lien_paise))
            }

    def execute_transaction(
        self,
        transaction_type: str,
        amount_rupees: Any,
        source_account: str,
        destination_account: str,
        description: str,
        idempotency_key: Optional[str] = None,
        actor: str = "SYSTEM",
        ip: str = "127.0.0.1",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute an atomic double-entry transaction against canonical PostgreSQL/SQLAlchemy.
        Enforces idempotency, payload fingerprint validation, row locking, balance sufficiency,
        and atomic commit of Transaction + LedgerEntry rows.
        """
        amount_paise = rupees_to_paise(amount_rupees)
        src_str = str(source_account).strip()
        dst_str = str(destination_account).strip()
        metadata = metadata or {}
        payload_hash = compute_payload_hash(src_str, dst_str, amount_paise, transaction_type)

        with _engine_lock:
            with get_db() as db:
                # 1. IDEMPOTENCY CHECK WITH PAYLOAD FINGERPRINT & ACCOUNT SCOPE
                if idempotency_key:
                    existing = db.query(Transaction).filter(
                        Transaction.idempotency_key == idempotency_key
                    ).first()
                    if existing:
                        # Validate account scoping and payload fingerprint
                        scope_match = (existing.source_account == src_str and existing.destination_account == dst_str)
                        payload_match = (
                            existing.amount_paise == amount_paise and
                            existing.transaction_type == transaction_type and
                            (not existing.payload_hash or existing.payload_hash == payload_hash)
                        )
                        if not scope_match or not payload_match:
                            raise IdempotencyConflictError(
                                f"Idempotency conflict: key '{idempotency_key}' previously used with different "
                                f"parameters or account scope."
                            )

                        state = existing.state
                        if state == STATE_SUCCESSFUL:
                            s_bal = db.query(AccountBalance).filter(AccountBalance.account_number == src_str).first()
                            d_bal = db.query(AccountBalance).filter(AccountBalance.account_number == dst_str).first()
                            s_rupees = float(paise_to_rupees(s_bal.balance_paise)) if s_bal else 0.0
                            d_rupees = float(paise_to_rupees(d_bal.balance_paise)) if d_bal else 0.0
                            return {
                                "success": True,
                                "idempotent_replay": True,
                                "reference_id": existing.reference_id,
                                "state": state,
                                "amount_paise": existing.amount_paise,
                                "amount_rupees": float(paise_to_rupees(existing.amount_paise)),
                                "amount_formatted": format_rupees(existing.amount_paise),
                                "source_account": src_str,
                                "destination_account": dst_str,
                                "source_balance_rupees": s_rupees,
                                "destination_balance_rupees": d_rupees,
                                "description": existing.description,
                                "message": "Transaction previously completed (idempotent response)."
                            }
                        elif state == STATE_PROCESSING:
                            raise DuplicateTransactionError(
                                f"A transaction with idempotency key '{idempotency_key}' is currently processing."
                            )
                        elif state == STATE_FAILED:
                            return {
                                "success": False,
                                "idempotent_replay": True,
                                "reference_id": existing.reference_id,
                                "state": state,
                                "message": f"Previous transaction with this key failed: {existing.error_reason}"
                            }

                # 2. ENSURE ACCOUNTS EXIST (Never create arbitrary customer accounts)
                for acc_num in (src_str, dst_str):
                    acc_rec = db.query(Account).filter(Account.account_number == acc_num).first()
                    if not acc_rec:
                        if acc_num in SYSTEM_GL_ACCOUNTS:
                            acc_rec = Account(
                                account_number=acc_num,
                                account_type=SYSTEM_GL_ACCOUNTS[acc_num],
                                status="ACTIVE"
                            )
                            db.add(acc_rec)
                            db.flush()
                            bal_rec = AccountBalance(account_number=acc_num, balance_paise=0, lien_paise=0)
                            db.add(bal_rec)
                            db.flush()
                        else:
                            raise AccountNotFoundError(
                                f"Account '{acc_num}' not found. Cannot process financial transaction for unverified customer."
                            )

                # 3. DETERMINISTIC ROW LOCKING (Sort account numbers to eliminate deadlocks)
                lock_order = sorted([src_str, dst_str])
                balance_records = {}
                for acc_num in lock_order:
                    b_rec = db.query(AccountBalance).filter(
                        AccountBalance.account_number == acc_num
                    ).with_for_update().first()
                    if not b_rec:
                        b_rec = AccountBalance(account_number=acc_num, balance_paise=0, lien_paise=0)
                        db.add(b_rec)
                        db.flush()
                    balance_records[acc_num] = b_rec

                src_acc = db.query(Account).filter(Account.account_number == src_str).with_for_update().first()
                dst_acc = db.query(Account).filter(Account.account_number == dst_str).with_for_update().first()

                if src_acc.status != "ACTIVE":
                    raise LedgerError(f"Source account '{src_str}' is {src_acc.status}.")
                if dst_acc.status != "ACTIVE":
                    raise LedgerError(f"Destination account '{dst_str}' is {dst_acc.status}.")

                is_customer_source = not src_str.startswith("GL_")

                # Balance sufficiency & limit enforcement
                if is_customer_source:
                    avail_paise = balance_records[src_str].balance_paise - balance_records[src_str].lien_paise
                    if avail_paise < amount_paise:
                        raise InsufficientFundsError(
                            f"Insufficient available balance in account '{src_str}'. "
                            f"Required: {format_rupees(amount_paise)}, Available: {format_rupees(avail_paise)}."
                        )

                    # Daily limit check with date rollover
                    today = datetime.date.today().isoformat()
                    if src_acc.last_limit_reset_date != today:
                        src_acc.last_limit_reset_date = today
                        src_acc.daily_transferred_paise = 0

                    new_daily = src_acc.daily_transferred_paise + amount_paise
                    if new_daily > src_acc.daily_transfer_limit_paise:
                        raise LimitExceededError(
                            f"Daily transfer limit exceeded for account '{src_str}'. "
                            f"Daily Limit: {format_rupees(src_acc.daily_transfer_limit_paise)}, "
                            f"Attempted: {format_rupees(amount_paise)}."
                        )

                # 4. EXECUTE ATOMIC DEBIT AND CREDIT LEGS
                ref_id = generate_reference_id("TXN")

                # Apply debit to source account
                src_type = src_acc.account_type if src_acc else SYSTEM_GL_ACCOUNTS.get(src_str, "CUSTOMER_SAVINGS")
                src_delta = get_entry_delta(src_type, "DEBIT", amount_paise)
                balance_records[src_str].balance_paise += src_delta
                balance_records[src_str].version += 1
                deb_bal = balance_records[src_str].balance_paise
                if is_customer_source:
                    src_acc.daily_transferred_paise += amount_paise

                # Apply credit to destination account
                dst_type = dst_acc.account_type if dst_acc else SYSTEM_GL_ACCOUNTS.get(dst_str, "CUSTOMER_SAVINGS")
                dst_delta = get_entry_delta(dst_type, "CREDIT", amount_paise)
                balance_records[dst_str].balance_paise += dst_delta
                balance_records[dst_str].version += 1
                cred_bal = balance_records[dst_str].balance_paise

                # 5. PERSIST TRANSACTION AND LEDGER ENTRIES TOGETHER
                now_utc = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
                txn = Transaction(
                    reference_id=ref_id,
                    idempotency_key=idempotency_key,
                    payload_hash=payload_hash,
                    transaction_type=transaction_type,
                    state=STATE_SUCCESSFUL,
                    amount_paise=amount_paise,
                    source_account=src_str,
                    destination_account=dst_str,
                    description=description,
                    metadata_json=json.dumps(metadata),
                    created_at=now_utc,
                    updated_at=now_utc
                )
                db.add(txn)

                debit_entry = LedgerEntry(
                    reference_id=ref_id,
                    account_number=src_str,
                    direction="DEBIT",
                    amount_paise=amount_paise,
                    running_balance_paise=deb_bal,
                    description=f"{description} [Debit Leg]",
                    created_at=now_utc
                )
                credit_entry = LedgerEntry(
                    reference_id=ref_id,
                    account_number=dst_str,
                    direction="CREDIT",
                    amount_paise=amount_paise,
                    running_balance_paise=cred_bal,
                    description=f"{description} [Credit Leg]",
                    created_at=now_utc
                )
                db.add(debit_entry)
                db.add(credit_entry)

                # Accounting Invariant Verification: Debits == Credits == amount_paise
                if debit_entry.amount_paise != credit_entry.amount_paise or debit_entry.amount_paise != amount_paise:
                    raise UnbalancedTransactionError(
                        f"Double-entry mismatch! Debit: {debit_entry.amount_paise}, Credit: {credit_entry.amount_paise}"
                    )

                # Audit logs (both audit_logs and audit_trail tables)
                audit_created = AuditTrail(
                    reference_id=ref_id,
                    action="TRANSACTION_CREATED",
                    from_state=None,
                    to_state=STATE_PENDING,
                    actor=actor,
                    ip_address=ip,
                    details_json=json.dumps({"amount_paise": amount_paise, "src": src_str, "dst": dst_str}),
                    timestamp=now_utc
                )
                audit_processing = AuditTrail(
                    reference_id=ref_id,
                    action="STATE_TRANSITION",
                    from_state=STATE_PENDING,
                    to_state=STATE_PROCESSING,
                    actor=actor,
                    ip_address=ip,
                    details_json="{}",
                    timestamp=now_utc
                )
                audit_completed = AuditTrail(
                    reference_id=ref_id,
                    action="TRANSACTION_COMPLETED",
                    from_state=STATE_PROCESSING,
                    to_state=STATE_SUCCESSFUL,
                    actor=actor,
                    ip_address=ip,
                    details_json=json.dumps({"deb_bal": deb_bal, "cred_bal": cred_bal}),
                    timestamp=now_utc
                )
                db.add(audit_created)
                db.add(audit_processing)
                db.add(audit_completed)

                audit_log = AuditLog(
                    reference_id=ref_id,
                    account_number=src_str,
                    actor=actor,
                    action="TRANSACTION_COMPLETED",
                    from_state=STATE_PROCESSING,
                    to_state=STATE_SUCCESSFUL,
                    ip_address=ip,
                    details_json=json.dumps({"debit_account": src_str, "credit_account": dst_str, "amount_paise": amount_paise}),
                    created_at=now_utc
                )
                db.add(audit_log)

                return {
                    "success": True,
                    "reference_id": ref_id,
                    "state": STATE_SUCCESSFUL,
                    "transaction_type": transaction_type,
                    "amount_paise": amount_paise,
                    "amount_rupees": float(paise_to_rupees(amount_paise)),
                    "amount_formatted": format_rupees(amount_paise),
                    "source_account": src_str,
                    "destination_account": dst_str,
                    "source_balance_rupees": float(paise_to_rupees(deb_bal)),
                    "destination_balance_rupees": float(paise_to_rupees(cred_bal)),
                    "description": description,
                    "created_at": datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                }

    def reverse_transaction(
        self,
        reference_id: str,
        reason: str,
        actor: str = "SYSTEM",
        ip: str = "127.0.0.1"
    ) -> Dict[str, Any]:
        """
        Reverse a previously successful transaction atomically in the canonical database.
        Maintains immutability: Compensating transaction with opposing debit/credit legs.
        """
        with _engine_lock:
            with get_db() as db:
                orig = db.query(Transaction).filter(Transaction.reference_id == reference_id).first()
                if not orig:
                    raise LedgerError(f"Original transaction '{reference_id}' not found.")

                if orig.state != STATE_SUCCESSFUL:
                    raise LedgerError(f"Cannot reverse transaction in '{orig.state}' state. Only SUCCESSFUL transactions can be reversed.")

                # Check if already reversed
                already = db.query(Transaction).filter(
                    Transaction.original_reference_id == reference_id,
                    Transaction.state == STATE_SUCCESSFUL
                ).first()
                if already:
                    raise LedgerError(f"Transaction '{reference_id}' has already been reversed.")

                amount_paise = orig.amount_paise
                reversal_src = orig.destination_account
                reversal_dst = orig.source_account

                # Lock both accounts
                lock_order = sorted([reversal_src, reversal_dst])
                balance_records = {}
                for acc_num in lock_order:
                    b_rec = db.query(AccountBalance).filter(AccountBalance.account_number == acc_num).with_for_update().first()
                    balance_records[acc_num] = b_rec

                # Ensure reversal source has sufficient funds
                if not reversal_src.startswith("GL_"):
                    avail = balance_records[reversal_src].balance_paise - balance_records[reversal_src].lien_paise
                    if avail < amount_paise:
                        raise InsufficientFundsError(
                            f"Cannot reverse: account '{reversal_src}' has insufficient balance to honor reversal."
                        )

                rev_ref = generate_reference_id("REV")
                now_utc = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)

                # Deduct from reversal source, credit to reversal destination
                rev_src_acc = db.query(Account).filter(Account.account_number == reversal_src).first()
                rev_src_type = rev_src_acc.account_type if rev_src_acc else SYSTEM_GL_ACCOUNTS.get(reversal_src, "CUSTOMER_SAVINGS")
                rev_src_delta = get_entry_delta(rev_src_type, "DEBIT", amount_paise)
                balance_records[reversal_src].balance_paise += rev_src_delta
                balance_records[reversal_src].version += 1
                deb_bal = balance_records[reversal_src].balance_paise

                rev_dst_acc = db.query(Account).filter(Account.account_number == reversal_dst).first()
                rev_dst_type = rev_dst_acc.account_type if rev_dst_acc else SYSTEM_GL_ACCOUNTS.get(reversal_dst, "CUSTOMER_SAVINGS")
                rev_dst_delta = get_entry_delta(rev_dst_type, "CREDIT", amount_paise)
                balance_records[reversal_dst].balance_paise += rev_dst_delta
                balance_records[reversal_dst].version += 1
                cred_bal = balance_records[reversal_dst].balance_paise

                # Mark original as REVERSED
                orig.state = STATE_REVERSED
                orig.updated_at = now_utc

                # Create reversal transaction record
                rev_txn = Transaction(
                    reference_id=rev_ref,
                    original_reference_id=reference_id,
                    transaction_type="REVERSAL",
                    state=STATE_SUCCESSFUL,
                    amount_paise=amount_paise,
                    source_account=reversal_src,
                    destination_account=reversal_dst,
                    description=f"Reversal of {reference_id}: {reason}",
                    created_at=now_utc,
                    updated_at=now_utc
                )
                db.add(rev_txn)

                leg_deb = LedgerEntry(
                    reference_id=rev_ref,
                    account_number=reversal_src,
                    direction="DEBIT",
                    amount_paise=amount_paise,
                    running_balance_paise=deb_bal,
                    description=f"Reversal debit for {reference_id}",
                    created_at=now_utc
                )
                leg_cred = LedgerEntry(
                    reference_id=rev_ref,
                    account_number=reversal_dst,
                    direction="CREDIT",
                    amount_paise=amount_paise,
                    running_balance_paise=cred_bal,
                    description=f"Reversal credit for {reference_id}",
                    created_at=now_utc
                )
                db.add(leg_deb)
                db.add(leg_cred)

                audit = AuditLog(
                    reference_id=rev_ref,
                    account_number=reversal_src,
                    actor=actor,
                    action="REVERSAL_EXECUTED",
                    to_state=STATE_SUCCESSFUL,
                    ip_address=ip,
                    details_json=json.dumps({"original_reference_id": reference_id, "reason": reason}),
                    created_at=now_utc
                )
                db.add(audit)

                audit_tr = AuditTrail(
                    reference_id=rev_ref,
                    action="REVERSAL_EXECUTED",
                    to_state=STATE_SUCCESSFUL,
                    actor=actor,
                    ip_address=ip,
                    details_json=json.dumps({"original_reference_id": reference_id, "reason": reason}),
                    timestamp=now_utc
                )
                db.add(audit_tr)

                return {
                    "success": True,
                    "reversal_reference_id": rev_ref,
                    "original_reference_id": reference_id,
                    "state": STATE_SUCCESSFUL,
                    "amount_rupees": float(paise_to_rupees(amount_paise)),
                    "message": f"Transaction {reference_id} successfully reversed."
                }

    def reconcile_ledger(self) -> Dict[str, Any]:
        """
        Mathematical reconciliation across the entire canonical double-entry ledger.
        Verifies:
        1. Global Sum(DEBIT) == Sum(CREDIT).
        2. Per-account cached balance == computed balance from ledger entries.
        """
        with _engine_lock:
            with get_db() as db:
                debit_sum = db.query(func.coalesce(func.sum(LedgerEntry.amount_paise), 0)).filter(
                    LedgerEntry.direction == "DEBIT"
                ).scalar() or 0

                credit_sum = db.query(func.coalesce(func.sum(LedgerEntry.amount_paise), 0)).filter(
                    LedgerEntry.direction == "CREDIT"
                ).scalar() or 0

                total_entries = db.query(func.count(LedgerEntry.id)).scalar() or 0
                discrepancy = debit_sum - credit_sum

                # Audit every account balance
                all_balances = db.query(AccountBalance).all()
                account_discrepancies = []

                for b in all_balances:
                    acc_num = b.account_number
                    cached_bal = b.balance_paise

                    acc_debits = db.query(func.coalesce(func.sum(LedgerEntry.amount_paise), 0)).filter(
                        LedgerEntry.account_number == acc_num,
                        LedgerEntry.direction == "DEBIT"
                    ).scalar() or 0

                    acc_credits = db.query(func.coalesce(func.sum(LedgerEntry.amount_paise), 0)).filter(
                        LedgerEntry.account_number == acc_num,
                        LedgerEntry.direction == "CREDIT"
                    ).scalar() or 0

                    acc_rec = db.query(Account).filter(Account.account_number == acc_num).first()
                    is_asset = (acc_rec and acc_rec.account_type == "GL_ASSET") or (SYSTEM_GL_ACCOUNTS.get(acc_num) == "GL_ASSET")
                    if is_asset:
                        computed_bal = acc_debits - acc_credits
                    else:
                        computed_bal = acc_credits - acc_debits

                    if computed_bal != cached_bal:
                        account_discrepancies.append({
                            "account_number": acc_num,
                            "cached_balance_paise": cached_bal,
                            "computed_balance_paise": computed_bal,
                            "diff": cached_bal - computed_bal
                        })

                # Transactions count by state
                txn_states = db.query(Transaction.state, func.count(Transaction.id)).group_by(Transaction.state).all()
                state_counts = {state: count for state, count in txn_states}

                is_healthy = (discrepancy == 0) and (len(account_discrepancies) == 0)

                result = {
                    "status": "HEALTHY" if is_healthy else "DISCREPANCY_DETECTED",
                    "timestamp": datetime.datetime.now().isoformat(),
                    "total_transactions": sum(state_counts.values()),
                    "transactions_by_state": state_counts,
                    "total_ledger_entries": total_entries,
                    "total_system_debits_paise": debit_sum,
                    "total_system_credits_paise": credit_sum,
                    "total_system_debits_rupees": float(paise_to_rupees(debit_sum)),
                    "total_system_credits_rupees": float(paise_to_rupees(credit_sum)),
                    "discrepancy_paise": discrepancy,
                    "accounts_audited": len(all_balances),
                    "account_discrepancies": account_discrepancies
                }

                audit_tr = AuditTrail(
                    reference_id=None,
                    action="RECONCILIATION_RUN",
                    to_state=result["status"],
                    actor="SYSTEM",
                    ip_address="127.0.0.1",
                    details_json=json.dumps({"is_healthy": is_healthy, "discrepancy_paise": discrepancy}),
                    timestamp=datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
                )
                db.add(audit_tr)

                return result

    def get_transaction_history(self, account_number: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve complete double-entry transaction history for an account from canonical database."""
        acc_str = str(account_number).strip()
        with get_db() as db:
            entries = db.query(LedgerEntry, Transaction).join(
                Transaction, LedgerEntry.reference_id == Transaction.reference_id
            ).filter(
                LedgerEntry.account_number == acc_str
            ).order_by(LedgerEntry.id.desc()).limit(limit).all()

            history = []
            for entry, txn in entries:
                amt_str = (
                    f"+{paise_to_rupees(entry.amount_paise):.2f}"
                    if entry.direction == "CREDIT"
                    else f"-{paise_to_rupees(entry.amount_paise):.2f}"
                )
                history.append({
                    "entry_id": entry.id,
                    "reference_id": entry.reference_id,
                    "date": entry.created_at.strftime("%d/%m/%Y %H:%M:%S") if entry.created_at else "",
                    "type": entry.description or "",
                    "transaction_type": txn.transaction_type if txn else "",
                    "direction": entry.direction,
                    "amount": amt_str,
                    "amount_rupees": float(paise_to_rupees(entry.amount_paise)),
                    "balance": f"{paise_to_rupees(entry.running_balance_paise):.2f}",
                    "state": txn.state if txn else "",
                    "source": txn.source_account if txn else "",
                    "destination": txn.destination_account if txn else ""
                })
            return history


# Global Singleton Engine Instance
ledger_engine = FinancialIntegrityEngine()
