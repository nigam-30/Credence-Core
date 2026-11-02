"""
Credence Core — Centralized Versioned Financial Policy
Single authoritative source for interest rates, transaction limits, commodity pricing,
fee schedules, and financial calculation invariants.
Auditable, versioned, and configurable via environment overrides.
"""

import os
from decimal import Decimal, ROUND_HALF_EVEN
from typing import Dict, Any


class FinancialPolicy:
    """
    Versioned financial policies and business invariants.
    Policy Version: 2026.2.0 (Phase 6.2 Hardening)
    """
    POLICY_VERSION = "2026.2.0"
    POLICY_ENGINE_VERSION = "2026.3.0"

    # Default Transaction Limits (INR)
    DEFAULT_DAILY_LIMIT_PAISE = 50000000          # ₹5,00,000.00
    DEFAULT_PER_TXN_LIMIT_PAISE = 10000000        # ₹1,00,000.00
    DEFAULT_APPROVAL_THRESHOLD_PAISE = 5000000    # ₹50,000.00
    HIGH_VALUE_FRAUD_THRESHOLD_PAISE = 20000000   # ₹2,00,000.00

    # Fraud Detection & Risk Parameters (Centralized)
    FRAUD_VELOCITY_WINDOW_SECONDS = 300           # 5 minutes
    FRAUD_VELOCITY_MAX_TXNS = 4                   # Max 4 transactions in 5 minutes
    FRAUD_BALANCE_DRAIN_PCT = Decimal("0.80")     # Flag if withdrawal > 80% of balance
    FRAUD_MAX_PIN_FAILURES = 3                    # Flag after 3 failed PIN attempts in window
    FRAUD_SCORE_ALERT_THRESHOLD = 50              # Alert generated if risk score >= 50
    FRAUD_SCORE_MANUAL_REVIEW_THRESHOLD = 75      # Require administrative approval if score >= 75

    # Interest Rates (Annualized Percentage)
    SAVINGS_INTEREST_RATE_PCT = Decimal("3.50")
    FD_RATES_BY_TENURE = {
        6: Decimal("5.75"),
        12: Decimal("6.50"),
        24: Decimal("7.00"),
        36: Decimal("7.25"),
        60: Decimal("7.50"),
    }
    DEFAULT_FD_INTEREST_RATE_PCT = Decimal("6.50")
    RD_INTEREST_RATE_PCT = Decimal("6.25")
    PERSONAL_LOAN_INTEREST_RATE_PCT = Decimal("10.50")

    # Reference Commodity Rates (Paise per unit)
    # Configurable via environment with safe defaults
    _raw_gold = os.environ.get("LIVE_GOLD_RATE_PER_GRAM_PAISE", "762050")
    GOLD_RATE_PER_GRAM_PAISE = int(_raw_gold) if _raw_gold.isdigit() else 762050  # ₹7,620.50 / gram

    _raw_silver = os.environ.get("LIVE_SILVER_RATE_PER_KG_PAISE", "9245000")
    SILVER_RATE_PER_KG_PAISE = int(_raw_silver) if _raw_silver.isdigit() else 9245000  # ₹92,450.00 / kg

    # Pre-approved Credit Limits
    PREAPPROVED_CREDIT_LIMIT_STANDARD_PAISE = 10000000  # ₹1,00,000.00
    PREAPPROVED_CREDIT_LIMIT_PREMIUM_PAISE = 20000000   # ₹2,00,000.00

    @classmethod
    def get_fd_rate(cls, tenure_months: int) -> Decimal:
        """Resolve interest rate based on tenure."""
        return cls.FD_RATES_BY_TENURE.get(tenure_months, cls.DEFAULT_FD_INTEREST_RATE_PCT)

    @classmethod
    def get_fd_interest_rate(cls, tenure_months: int) -> Decimal:
        """Alias for get_fd_rate."""
        return cls.get_fd_rate(tenure_months)

    @classmethod
    def calculate_fd_maturity(cls, principal_paise: int, tenure_months: int) -> int:
        """Calculate maturity amount using integer paise arithmetic."""
        rate = cls.get_fd_rate(tenure_months)
        # Maturity = Principal * (1 + rate * tenure / (12 * 100))
        numerator = Decimal(principal_paise) * (Decimal("1") + (rate * Decimal(tenure_months) / Decimal("1200")))
        return int(numerator.to_integral_value(rounding=ROUND_HALF_EVEN))

    @classmethod
    def get_gold_rate_rupees(cls) -> Decimal:
        """Return gold rate per gram in Rupees."""
        return (Decimal(cls.GOLD_RATE_PER_GRAM_PAISE) / Decimal("100")).quantize(Decimal("0.01"))

    @classmethod
    def get_silver_rate_rupees(cls) -> Decimal:
        """Return silver rate per kg in Rupees."""
        return (Decimal(cls.SILVER_RATE_PER_KG_PAISE) / Decimal("100")).quantize(Decimal("0.01"))

    @classmethod
    def to_audit_dict(cls) -> Dict[str, Any]:
        """Export current policy configuration for audit trails."""
        return {
            "policy_version": cls.POLICY_VERSION,
            "default_daily_limit_rupees": cls.DEFAULT_DAILY_LIMIT_PAISE / 100.0,
            "default_per_txn_limit_rupees": cls.DEFAULT_PER_TXN_LIMIT_PAISE / 100.0,
            "gold_rate_rupees": float(cls.get_gold_rate_rupees()),
            "fd_default_rate_pct": float(cls.DEFAULT_FD_INTEREST_RATE_PCT),
            "loan_rate_pct": float(cls.PERSONAL_LOAN_INTEREST_RATE_PCT),
        }
