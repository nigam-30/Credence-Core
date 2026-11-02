"""
Credence Core — Centralized Input Validation & Schemas
Validates parameters, formatting, ranges, and types for all API endpoints.
"""

import re
from decimal import Decimal
from typing import Dict, Any, Tuple, Optional


class ValidationError(ValueError):
    """Raised when an API request payload fails schema validation."""
    pass


def validate_account_number(acc_no: Any) -> str:
    """Validate standard 14-digit account number format (or allowed system accounts)."""
    val = str(acc_no or "").strip()
    if val in ("99999999999999", "999999"):
        return val
    if not re.match(r"^\d{14}$", val):
        raise ValidationError(f"Invalid account number '{val}'. Must be exactly 14 digits.")
    return val


def validate_pin(pin: Any, allow_6_digit: bool = False) -> str:
    """Validate 4-digit (or 6-digit for UPI) numeric PIN."""
    val = str(pin or "").strip()
    pattern = r"^\d{4}(\d{2})?$" if allow_6_digit else r"^\d{4}$"
    if not re.match(pattern, val):
        msg = "PIN must be 4 or 6 digits." if allow_6_digit else "PIN must be exactly 4 digits."
        raise ValidationError(msg)
    return val


def validate_password_strength(password: Any) -> str:
    """Validate password strength (minimum 8 chars, letters and numbers)."""
    val = str(password or "").strip()
    if len(val) < 8 or not re.search(r"[a-zA-Z]", val) or not re.search(r"\d", val):
        raise ValidationError("Password must be at least 8 characters long and contain both letters and digits.")
    return val

validate_password = validate_password_strength


def validate_amount(amount: Any, min_amount: float = 1.0) -> Decimal:
    """Validate monetary amount strictly."""
    if amount is None:
        raise ValidationError("Amount is required.")
    clean = str(amount).replace('₹', '').replace(',', '').strip()
    if not clean or clean.lower() in ('nan', 'inf', '-inf', 'infinity'):
        raise ValidationError("Invalid numeric amount format.")
    try:
        dec = Decimal(clean)
    except Exception:
        raise ValidationError(f"Invalid monetary numeric amount: '{amount}'")

    if dec <= Decimal("0"):
        raise ValidationError("Amount must be strictly greater than zero.")
    if dec < Decimal(str(min_amount)):
        raise ValidationError(f"Minimum amount allowed is ₹{min_amount:,.2f}.")
    return dec


def validate_email(email: Any) -> Optional[str]:
    """Validate email format."""
    if not email:
        return None
    val = str(email).strip().lower()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", val):
        raise ValidationError("Invalid email address format.")
    return val


def validate_pan(pan: Any) -> Optional[str]:
    """Validate Indian PAN format (5 letters, 4 digits, 1 letter)."""
    if not pan:
        return None
    val = str(pan).strip().upper()
    if not re.match(r"^[A-Z]{5}[0-9]{4}[A-Z]$", val):
        raise ValidationError("Invalid PAN format (expected e.g. ABCDE1234F).")
    return val


def validate_upi_id(upi_id: Any) -> str:
    """Validate UPI virtual address format."""
    val = str(upi_id or "").strip().lower()
    if not re.match(r"^[a-zA-Z0-9.\-_]{2,49}@[a-zA-Z0-9]{2,49}$", val):
        raise ValidationError("Invalid UPI ID format (expected user@provider).")
    return val
