"""
Credence Core — Currency & Monetary Utilities
Enforces integer paise precision and rejects NaN, infinite, negative, or fractional sub-paise amounts.
"""

from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
from typing import Any


class InvalidAmountError(ValueError):
    """Raised when an amount is invalid, zero, negative, NaN or Infinite."""
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

    exponent = dec.as_tuple().exponent
    if exponent < -2:
        raise InvalidAmountError("Amount cannot specify fractional sub-paise (more than 2 decimal places).")

    paise = int((dec * Decimal("100")).to_integral_value(rounding=ROUND_HALF_EVEN))
    if paise <= 0:
        raise InvalidAmountError("Amount in paise must be positive integer.")

    return paise


def safe_rupees_to_paise(val: Any) -> int:
    """Safe conversion allowing 0 (e.g. for initial balance checks or zero fee calculations)."""
    if val is None:
        return 0
    clean = str(val).replace('₹', '').replace(',', '').strip()
    if not clean or clean.lower() in ('nan', 'inf', '-inf'):
        return 0
    try:
        dec = Decimal(clean)
        if dec < Decimal("0"):
            return 0
        return int((dec * Decimal("100")).to_integral_value(rounding=ROUND_HALF_EVEN))
    except Exception:
        return 0


def paise_to_rupees(paise: int) -> Decimal:
    """Convert integer paise to Decimal rupees with 2 decimal places."""
    return (Decimal(paise) / Decimal(100)).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)


def format_rupees(paise: int) -> str:
    """Format paise into INR rupee string."""
    return f"₹{paise_to_rupees(paise):,.2f}"
