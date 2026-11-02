"""
Credence Core — SQLAlchemy Database Models (Phase 3)
18 Relational modules with foreign keys, indexes, and database-level constraints.
"""

import datetime
from sqlalchemy import (
    Column, Integer, BigInteger, String, Text, Boolean, Numeric, DateTime,
    ForeignKey, CheckConstraint, Index, UniqueConstraint
)
from sqlalchemy.orm import relationship
from database import Base


# ════════════ 1. USERS ════════════
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(String(32), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(120), unique=True, nullable=True, index=True)
    dob = Column(String(20), nullable=True)
    address = Column(String(255), nullable=True)
    pan = Column(String(10), unique=True, nullable=True, index=True)
    employment_type = Column(String(50), default="Salaried")
    monthly_income_paise = Column(BigInteger, default=0)
    cibil_score = Column(Integer, default=750)
    password_hash = Column(String(255), nullable=True)
    pin_hash = Column(String(255), nullable=True)
    role = Column(String(20), default="user", nullable=False)
    is_2fa_enabled = Column(Boolean, default=False, nullable=False)
    mfa_enabled = Column(Boolean, default=False, nullable=False)
    mfa_secret = Column(String(255), nullable=True)
    mfa_recovery_codes = Column(Text, nullable=True)
    mfa_enrolled_at = Column(DateTime, nullable=True)
    last_totp_step = Column(BigInteger, default=0, nullable=False)
    notifications_enabled = Column(Boolean, default=True, nullable=False)
    status = Column(String(20), default="ACTIVE", nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    # Relationships
    accounts = relationship("Account", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("SessionRecord", back_populates="user", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("status IN ('ACTIVE', 'SUSPENDED', 'LOCKED')", name="chk_user_status"),
        CheckConstraint("role IN ('user', 'admin', 'compliance')", name="chk_user_role"),
    )


# ════════════ 2. ACCOUNTS ════════════
class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_number = Column(String(32), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    account_type = Column(String(50), nullable=False, default="CUSTOMER_SAVINGS")
    currency = Column(String(3), default="INR", nullable=False)
    status = Column(String(20), default="ACTIVE", nullable=False)
    daily_transfer_limit_paise = Column(BigInteger, default=50000000, nullable=False)  # ₹5,00,000
    daily_transferred_paise = Column(BigInteger, default=0, nullable=False)
    last_limit_reset_date = Column(String(20), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="accounts")
    balance_record = relationship("AccountBalance", back_populates="account", uselist=False, cascade="all, delete-orphan")
    cards = relationship("Card", back_populates="account", cascade="all, delete-orphan")
    upi_profile = relationship("UPIProfile", back_populates="account", uselist=False, cascade="all, delete-orphan")
    fixed_deposits = relationship("FixedDeposit", back_populates="account", cascade="all, delete-orphan")
    loans = relationship("Loan", back_populates="account", cascade="all, delete-orphan")
    investment = relationship("Investment", back_populates="account", uselist=False, cascade="all, delete-orphan")
    sips = relationship("SIP", back_populates="account", cascade="all, delete-orphan")
    ipo_applications = relationship("IPOApplication", back_populates="account", cascade="all, delete-orphan")
    recurring_deposits = relationship("RecurringDeposit", back_populates="account", cascade="all, delete-orphan")
    beneficiaries = relationship("Beneficiary", back_populates="account", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="account", cascade="all, delete-orphan")
    disputes = relationship("Dispute", back_populates="account", cascade="all, delete-orphan")
    support_tickets = relationship("SupportTicket", back_populates="account", cascade="all, delete-orphan")
    transaction_limit = relationship("TransactionLimit", back_populates="account", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("status IN ('ACTIVE', 'FROZEN', 'CLOSED')", name="chk_account_status"),
    )


# ════════════ 3. ACCOUNT BALANCES ════════════
class AccountBalance(Base):
    __tablename__ = "account_balances"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_number = Column(String(32), ForeignKey("accounts.account_number", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    balance_paise = Column(BigInteger, default=0, nullable=False)
    lien_paise = Column(BigInteger, default=0, nullable=False)
    version = Column(Integer, default=1, nullable=False)  # Optimistic concurrency locking
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    account = relationship("Account", back_populates="balance_record")

    __table_args__ = (
        CheckConstraint("lien_paise >= 0", name="chk_lien_non_negative"),
    )


# ════════════ 4. TRANSACTIONS ════════════
class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    reference_id = Column(String(64), unique=True, nullable=False, index=True)
    idempotency_key = Column(String(128), unique=True, nullable=True, index=True)
    payload_hash = Column(String(64), nullable=True, index=True)
    transaction_type = Column(String(50), nullable=False, index=True)
    state = Column(String(20), nullable=False, index=True)
    amount_paise = Column(BigInteger, nullable=False)
    source_account = Column(String(32), nullable=False, index=True)
    destination_account = Column(String(32), nullable=False, index=True)
    description = Column(Text, nullable=True)
    metadata_json = Column(Text, nullable=True)
    error_reason = Column(Text, nullable=True)
    original_reference_id = Column(String(64), ForeignKey("transactions.reference_id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    # Relationships
    ledger_entries = relationship("LedgerEntry", back_populates="transaction", cascade="all, delete-orphan")
    disputes = relationship("Dispute", back_populates="transaction")

    __table_args__ = (
        CheckConstraint("state IN ('PENDING', 'PROCESSING', 'SUCCESSFUL', 'FAILED', 'REVERSED')", name="chk_transaction_state"),
        CheckConstraint("amount_paise > 0", name="chk_positive_txn_amount"),
    )


# ════════════ 5. LEDGER ENTRIES (Double-Entry Legs) ════════════
class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    reference_id = Column(String(64), ForeignKey("transactions.reference_id", ondelete="CASCADE"), nullable=False, index=True)
    account_number = Column(String(32), ForeignKey("accounts.account_number", ondelete="RESTRICT"), nullable=False, index=True)
    direction = Column(String(10), nullable=False)  # DEBIT or CREDIT
    amount_paise = Column(BigInteger, nullable=False)
    running_balance_paise = Column(BigInteger, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False, index=True)

    transaction = relationship("Transaction", back_populates="ledger_entries")

    __table_args__ = (
        CheckConstraint("direction IN ('DEBIT', 'CREDIT')", name="chk_entry_direction"),
        CheckConstraint("amount_paise > 0", name="chk_entry_positive_amount"),
    )


# ════════════ 6. CARDS ════════════
class Card(Base):
    __tablename__ = "cards"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_number = Column(String(32), ForeignKey("accounts.account_number", ondelete="CASCADE"), nullable=False, index=True)
    card_type = Column(String(20), default="DEBIT", nullable=False)  # DEBIT, CREDIT, VIRTUAL
    card_number_masked = Column(String(24), nullable=False)
    card_network = Column(String(20), default="Visa")
    expiry_month_year = Column(String(10), nullable=False)
    pin_hash = Column(String(255), nullable=True)
    cvv_hash = Column(String(255), nullable=True)
    credit_limit_paise = Column(BigInteger, default=0)
    status = Column(String(20), default="ACTIVE", nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    account = relationship("Account", back_populates="cards")

    __table_args__ = (
        CheckConstraint("status IN ('ACTIVE', 'BLOCKED', 'EXPIRED')", name="chk_card_status"),
        CheckConstraint("card_type IN ('DEBIT', 'CREDIT', 'VIRTUAL')", name="chk_card_type"),
    )


# ════════════ 7. UPI PROFILES ════════════
class UPIProfile(Base):
    __tablename__ = "upi_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_number = Column(String(32), ForeignKey("accounts.account_number", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    upi_id = Column(String(100), unique=True, nullable=False, index=True)
    upi_pin_hash = Column(String(255), nullable=True)
    status = Column(String(20), default="ACTIVE", nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    account = relationship("Account", back_populates="upi_profile")

    __table_args__ = (
        CheckConstraint("status IN ('ACTIVE', 'SUSPENDED')", name="chk_upi_status"),
    )


# ════════════ 8. FIXED DEPOSITS ════════════
class FixedDeposit(Base):
    __tablename__ = "fixed_deposits"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_number = Column(String(32), ForeignKey("accounts.account_number", ondelete="CASCADE"), nullable=False, index=True)
    reference_id = Column(String(64), nullable=True)
    principal_amount_paise = Column(BigInteger, nullable=False)
    interest_rate_pct = Column(Numeric(5, 2), default=7.50, nullable=False)
    tenure_months = Column(Integer, nullable=False)
    maturity_amount_paise = Column(BigInteger, nullable=False)
    maturity_date = Column(String(30), nullable=True)
    status = Column(String(20), default="ACTIVE", nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    account = relationship("Account", back_populates="fixed_deposits")

    __table_args__ = (
        CheckConstraint("status IN ('ACTIVE', 'LIQUIDATED', 'MATURED')", name="chk_fd_status"),
        CheckConstraint("principal_amount_paise > 0", name="chk_fd_positive_principal"),
    )


# ════════════ 9. LOANS ════════════
class Loan(Base):
    __tablename__ = "loans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    loan_id = Column(String(32), unique=True, nullable=False, index=True)
    account_number = Column(String(32), ForeignKey("accounts.account_number", ondelete="CASCADE"), nullable=False, index=True)
    reference_id = Column(String(64), nullable=True)
    loan_type = Column(String(50), default="Personal Loan", nullable=False)
    principal_amount_paise = Column(BigInteger, nullable=False)
    outstanding_amount_paise = Column(BigInteger, nullable=False)
    interest_rate_pct = Column(Numeric(5, 2), default=8.50, nullable=False)
    tenure_months = Column(Integer, default=24)
    monthly_emi_paise = Column(BigInteger, default=0)
    status = Column(String(20), default="ACTIVE", nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    account = relationship("Account", back_populates="loans")

    __table_args__ = (
        CheckConstraint("status IN ('ACTIVE', 'CLOSED', 'DEFAULTED')", name="chk_loan_status"),
        CheckConstraint("principal_amount_paise > 0", name="chk_loan_positive_principal"),
    )


# ════════════ 10. INVESTMENTS (Gold & Portfolio) ════════════
class Investment(Base):
    __tablename__ = "investments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_number = Column(String(32), ForeignKey("accounts.account_number", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    gold_grams = Column(Numeric(10, 4), default=0.0, nullable=False)
    gold_total_invested_paise = Column(BigInteger, default=0, nullable=False)
    gold_avg_buy_price_paise = Column(BigInteger, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    account = relationship("Account", back_populates="investment")


# ════════════ 11. SIPS ════════════
class SIP(Base):
    __tablename__ = "sips"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sip_id = Column(String(32), unique=True, nullable=False, index=True)
    account_number = Column(String(32), ForeignKey("accounts.account_number", ondelete="CASCADE"), nullable=False, index=True)
    fund_id = Column(String(50), nullable=False)
    fund_name = Column(String(150), nullable=False)
    category = Column(String(50), default="Large Cap")
    investment_type = Column(String(30), default="Monthly SIP")
    monthly_amount_paise = Column(BigInteger, nullable=False)
    sip_day = Column(Integer, default=5)
    invested_amount_paise = Column(BigInteger, nullable=False)
    current_value_paise = Column(BigInteger, nullable=False)
    units = Column(Numeric(10, 3), default=0.0)
    nav = Column(Numeric(10, 2), default=100.0)
    status = Column(String(20), default="Active", nullable=False)
    start_date = Column(String(20), nullable=True)
    next_date = Column(String(20), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    account = relationship("Account", back_populates="sips")

    __table_args__ = (
        CheckConstraint("status IN ('Active', 'Paused', 'Redeemed')", name="chk_sip_status"),
    )


# ════════════ 12. IPO APPLICATIONS ════════════
class IPOApplication(Base):
    __tablename__ = "ipo_applications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    app_no = Column(String(64), unique=True, nullable=False, index=True)
    reference_id = Column(String(64), nullable=True)
    account_number = Column(String(32), ForeignKey("accounts.account_number", ondelete="CASCADE"), nullable=False, index=True)
    ipo_id = Column(String(50), nullable=False)
    company = Column(String(150), nullable=False)
    symbol = Column(String(50), nullable=False)
    shares = Column(Integer, nullable=False)
    lots = Column(Integer, default=1, nullable=False)
    bid_price_paise = Column(BigInteger, nullable=False)
    amount_blocked_paise = Column(BigInteger, nullable=False)
    demat_id = Column(String(50), nullable=True)
    status = Column(String(50), default="Application Submitted", nullable=False)
    applied_date = Column(String(20), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    account = relationship("Account", back_populates="ipo_applications")


# ════════════ 13. RECURRING DEPOSITS ════════════
class RecurringDeposit(Base):
    __tablename__ = "recurring_deposits"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rd_id = Column(String(32), unique=True, nullable=False, index=True)
    reference_id = Column(String(64), nullable=True)
    account_number = Column(String(32), ForeignKey("accounts.account_number", ondelete="CASCADE"), nullable=False, index=True)
    monthly_amount_paise = Column(BigInteger, nullable=False)
    tenure_months = Column(Integer, default=12, nullable=False)
    interest_rate_pct = Column(Numeric(5, 2), default=7.10, nullable=False)
    installments_paid = Column(Integer, default=1, nullable=False)
    total_deposited_paise = Column(BigInteger, nullable=False)
    maturity_amount_paise = Column(BigInteger, nullable=False)
    status = Column(String(20), default="Active", nullable=False)
    start_date = Column(String(20), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    account = relationship("Account", back_populates="recurring_deposits")


# ════════════ 14. BENEFICIARIES ════════════
class Beneficiary(Base):
    __tablename__ = "beneficiaries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_number = Column(String(32), ForeignKey("accounts.account_number", ondelete="CASCADE"), nullable=False, index=True)
    beneficiary_name = Column(String(100), nullable=False)
    beneficiary_account_number = Column(String(32), nullable=False)
    ifsc_code = Column(String(20), default="CRDN0001001", nullable=False)
    transfer_type = Column(String(20), default="IMPS", nullable=False)
    status = Column(String(20), default="ACTIVE", nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    account = relationship("Account", back_populates="beneficiaries")

    __table_args__ = (
        UniqueConstraint("account_number", "beneficiary_account_number", name="uq_account_beneficiary"),
    )


# ════════════ 15. SESSIONS ════════════
class SessionRecord(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(128), unique=True, nullable=False, index=True)
    session_token_hash = Column(String(64), unique=True, nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    account_number = Column(String(32), nullable=False, index=True)
    role = Column(String(20), default="user", nullable=False)
    is_demo = Column(Boolean, default=False, nullable=False)
    csrf_token = Column(String(128), nullable=True)
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    last_active_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="sessions")


# ════════════ 16. AUDIT LOGS ════════════
class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    reference_id = Column(String(64), nullable=True, index=True)
    account_number = Column(String(32), nullable=True, index=True)
    actor = Column(String(50), default="SYSTEM", nullable=False)
    action = Column(String(50), nullable=False, index=True)
    from_state = Column(String(20), nullable=True)
    to_state = Column(String(20), nullable=True)
    ip_address = Column(String(50), nullable=True)
    details_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False, index=True)


class AuditTrail(Base):
    __tablename__ = "audit_trail"

    audit_id = Column(Integer, primary_key=True, autoincrement=True)
    reference_id = Column(String(64), nullable=True, index=True)
    action = Column(String(100), nullable=False)
    from_state = Column(String(20), nullable=True)
    to_state = Column(String(20), nullable=True)
    actor = Column(String(50), default="SYSTEM")
    ip_address = Column(String(50), nullable=True)
    details_json = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)


# ════════════ 17. NOTIFICATIONS ════════════
class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_number = Column(String(32), ForeignKey("accounts.account_number", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(150), nullable=False)
    message = Column(Text, nullable=False)
    notification_type = Column(String(30), default="TRANSACTION", nullable=False)
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False, index=True)

    account = relationship("Account", back_populates="notifications")


# ════════════ 18. DISPUTES ════════════
class Dispute(Base):
    __tablename__ = "disputes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dispute_id = Column(String(32), unique=True, nullable=False, index=True)
    reference_id = Column(String(64), ForeignKey("transactions.reference_id", ondelete="RESTRICT"), nullable=False, index=True)
    account_number = Column(String(32), ForeignKey("accounts.account_number", ondelete="CASCADE"), nullable=False, index=True)
    reason = Column(Text, nullable=False)
    disputed_amount_paise = Column(BigInteger, nullable=False)
    status = Column(String(30), default="SUBMITTED", nullable=False)
    resolution_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    account = relationship("Account", back_populates="disputes")
    transaction = relationship("Transaction", back_populates="disputes")

    __table_args__ = (
        CheckConstraint("status IN ('SUBMITTED', 'UNDER_REVIEW', 'RESOLVED_REFUNDED', 'REJECTED')", name="chk_dispute_status"),
    )


# ════════════ 19. SUPPORT TICKETS ════════════
class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticket_id = Column(String(32), unique=True, nullable=False, index=True)
    account_number = Column(String(32), ForeignKey("accounts.account_number", ondelete="CASCADE"), nullable=False, index=True)
    subject = Column(String(200), nullable=False)
    category = Column(String(50), default="GENERAL", nullable=False)
    priority = Column(String(20), default="MEDIUM", nullable=False)
    status = Column(String(20), default="OPEN", nullable=False)
    message = Column(Text, nullable=False)
    admin_response = Column(Text, nullable=True)
    resolved_by = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    account = relationship("Account", back_populates="support_tickets")

    __table_args__ = (
        CheckConstraint("status IN ('OPEN', 'IN_PROGRESS', 'RESOLVED', 'CLOSED')", name="chk_ticket_status"),
        CheckConstraint("priority IN ('LOW', 'MEDIUM', 'HIGH', 'URGENT')", name="chk_ticket_priority"),
    )


# ════════════ 20. TRANSACTION LIMITS ════════════
class TransactionLimit(Base):
    __tablename__ = "transaction_limits"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_number = Column(String(32), ForeignKey("accounts.account_number", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    daily_limit_paise = Column(BigInteger, default=50000000, nullable=False)        # Default ₹500,000.00
    per_txn_limit_paise = Column(BigInteger, default=10000000, nullable=False)      # Default ₹100,000.00
    approval_threshold_paise = Column(BigInteger, default=5000000, nullable=False)  # Default ₹50,000.00
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    account = relationship("Account", back_populates="transaction_limit")

# ════════════ 21. FRAUD ALERTS ════════════
class FraudAlert(Base):
    __tablename__ = "fraud_alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    alert_id = Column(String(64), unique=True, nullable=False, index=True)
    account_number = Column(String(32), ForeignKey("accounts.account_number", ondelete="CASCADE"), nullable=False, index=True)
    amount_paise = Column(BigInteger, nullable=False)
    tx_type = Column(String(50), nullable=False)
    risk_score = Column(Integer, nullable=False)
    risk_flags = Column(Text, nullable=False)
    ip_address = Column(String(50), nullable=True)
    status = Column(String(20), default="OPEN", nullable=False, index=True)
    resolution_action = Column(String(50), nullable=True)
    resolved_by = Column(String(50), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False, index=True)

    account = relationship("Account")

    __table_args__ = (
        CheckConstraint("status IN ('OPEN', 'INVESTIGATING', 'RESOLVED', 'DISMISSED')", name="chk_fraud_alert_status"),
    )
