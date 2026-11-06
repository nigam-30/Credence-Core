"""
Credence Core — Authentication Service
Manages authentication, PostgreSQL server-side session establishment, session rotation,
server-side revocation on logout, MFA challenge verification, and restricted demo logins.
"""

import time
import secrets
import hashlib
import hmac
import datetime
import json
from typing import Dict, Any, Optional, Tuple
from flask import session, request
from backend.app.core.config import Config
from backend.app.core.database import get_db
from models import SessionRecord
from backend.app.core.security import (
    verify_password,
    is_account_locked,
    record_failed_attempt,
    reset_failed_attempts,
    log_auth_success,
    log_auth_failure,
    log_auth_lockout,
    get_session_token_from_request,
    check_ip_rate_limit,
)
from backend.app.core.mfa import (
    decrypt_mfa_secret,
    verify_totp_code,
    verify_totp_code_with_replay_prevention,
    verify_and_consume_recovery_code,
)
from backend.app.repositories.user_repository import user_repository
from backend.app.repositories.account_repository import account_repository


def create_server_session(db, user, account_number: str, role: str, is_demo: bool, ip: str) -> Dict[str, str]:
    """
    Perform session rotation and create an active session record in the canonical database.
    Invalidates any previous active sessions for this account.
    """
    acc_str = str(account_number).strip()
    # Invalidate previous active sessions (Session Rotation)
    db.query(SessionRecord).filter(
        SessionRecord.account_number == acc_str,
        SessionRecord.is_active == True
    ).update({"is_active": False})

    # Generate cryptographically secure tokens
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    csrf_token = secrets.token_hex(32)

    now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    expires_at = now + datetime.timedelta(minutes=30)

    # Ensure role is safe (demo can never be admin)
    assigned_role = "demo" if is_demo else (role or "user")
    if is_demo and assigned_role == "admin":
        assigned_role = "demo"

    s_rec = SessionRecord(
        session_id=raw_token,
        session_token_hash=token_hash,
        user_id=user.id if user else 0,
        account_number=acc_str,
        role=assigned_role,
        is_demo=is_demo,
        csrf_token=csrf_token,
        ip_address=ip,
        user_agent=request.headers.get("User-Agent", "")[:250] if request else "",
        is_active=True,
        expires_at=expires_at,
        created_at=now,
        last_active_at=now
    )
    db.add(s_rec)
    db.commit()

    # Update Flask session storage
    session.clear()
    session["session_token"] = raw_token
    session["user_id"] = acc_str
    session["role"] = assigned_role
    session["is_demo"] = is_demo
    session["csrf_token"] = csrf_token
    session.permanent = True

    return {
        "session_token": raw_token,
        "csrf_token": csrf_token,
        "role": assigned_role
    }


def generate_mfa_ticket(user_id: int, account_number: str) -> str:
    """Generate a tamper-evident temporary MFA challenge ticket."""
    ts = int(time.time())
    payload = f"{user_id}:{account_number}:{ts}"
    sig = hmac.new(Config.SECRET_KEY.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}:{sig}"


def verify_mfa_ticket(ticket: str) -> Optional[Tuple[int, str]]:
    """Validate MFA challenge ticket and enforce 5-minute timeout."""
    try:
        parts = str(ticket).split(":")
        if len(parts) != 4:
            return None
        u_id_str, acc_no, ts_str, sig = parts
        payload = f"{u_id_str}:{acc_no}:{ts_str}"
        expected_sig = hmac.new(Config.SECRET_KEY.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
        if not secrets.compare_digest(sig, expected_sig):
            return None
        ts = int(ts_str)
        if time.time() - ts > 300:  # 5 minutes expiration
            return None
        return int(u_id_str), acc_no
    except Exception:
        return None


class AuthenticationService:
    def authenticate_user(self, account_number: str, password: str, ip: str) -> Dict[str, Any]:
        """Authenticate user by account number and password with brute-force lockout and MFA challenge."""
        acc_str = str(account_number or "").strip()

        # Check lockout
        is_locked, remaining = is_account_locked(acc_str)
        if is_locked:
            log_auth_lockout(acc_str, ip, remaining)
            return {
                "success": False,
                "message": f"Account is temporarily locked due to too many failed attempts. Try again in {remaining} seconds.",
                "status_code": 429
            }

        with get_db() as db:
            acc = account_repository.get_by_number(db, acc_str)
            if not acc or not acc.user:
                locked, lockout_sec = record_failed_attempt(acc_str, ip)
                log_auth_failure(acc_str, ip, "Invalid credentials")
                if locked:
                    return {
                        "success": False,
                        "message": f"Account is temporarily locked due to too many failed attempts. Try again in {lockout_sec} seconds.",
                        "status_code": 429
                    }
                return {
                    "success": False,
                    "message": "Invalid account number or password.",
                    "status_code": 401
                }

            user = acc.user
            if not user.password_hash or not verify_password(user.password_hash, password):
                locked, lockout_sec = record_failed_attempt(acc_str, ip)
                log_auth_failure(acc_str, ip, "Invalid credentials")
                if locked:
                    return {
                        "success": False,
                        "message": f"Account is temporarily locked due to too many failed attempts. Try again in {lockout_sec} seconds.",
                        "status_code": 429
                    }
                return {
                    "success": False,
                    "message": "Invalid account number or password.",
                    "status_code": 401
                }

            # Check if user requires MFA challenge
            if getattr(user, "mfa_enabled", False):
                ticket = generate_mfa_ticket(user.id, acc_str)
                return {
                    "success": True,
                    "mfa_required": True,
                    "mfa_ticket": ticket,
                    "message": "Two-factor authentication code required.",
                    "status_code": 200
                }

            # Authentication successful: Rotate session and persist to PostgreSQL
            reset_failed_attempts(acc_str)
            sess_data = create_server_session(
                db=db,
                user=user,
                account_number=acc_str,
                role=user.role or "user",
                is_demo=False,
                ip=ip
            )

            log_auth_success(acc_str, ip)
            return {
                "success": True,
                "session_token": sess_data["session_token"],
                "csrf_token": sess_data["csrf_token"],
                "message": "Login successful.",
                "user": {
                    "account_number": acc_str,
                    "name": user.name,
                    "role": user.role,
                    "email": user.email,
                    "customer_id": user.customer_id
                },
                "status_code": 200
            }

    def verify_mfa_login(self, mfa_ticket: str, totp_code: Optional[str], recovery_code: Optional[str], ip: str) -> Dict[str, Any]:
        """Verify second factor (TOTP code or recovery code) to complete login."""
        verified = verify_mfa_ticket(mfa_ticket)
        if not verified:
            return {
                "success": False,
                "message": "Invalid or expired MFA challenge ticket. Please sign in again.",
                "status_code": 401
            }
        user_id, acc_str = verified

        # Rate-limit MFA verification attempts (5 per 5 minutes)
        if not check_ip_rate_limit(f"mfa_verify:{acc_str}:{ip}", max_requests=5, window_seconds=300):
            return {
                "success": False,
                "message": "Too many failed MFA verification attempts. Please wait 5 minutes before retrying.",
                "status_code": 429
            }

        with get_db() as db:
            from models import User
            user = db.query(User).filter(User.id == user_id).first()
            if not user or not user.mfa_enabled:
                return {"success": False, "message": "User not found or MFA not configured.", "status_code": 401}

            code_valid = False
            error_reason = "Invalid authentication code or recovery code."
            if totp_code:
                plain_secret = decrypt_mfa_secret(user.mfa_secret)
                if plain_secret:
                    ok, replay_err = verify_totp_code_with_replay_prevention(plain_secret, str(totp_code).strip(), user.id)
                    if ok:
                        code_valid = True
                    elif replay_err:
                        error_reason = replay_err

            elif recovery_code:
                ok, updated_codes = verify_and_consume_recovery_code(str(recovery_code).strip(), user.mfa_recovery_codes)
                if ok:
                    user.mfa_recovery_codes = updated_codes
                    db.commit()
                    code_valid = True

            if not code_valid:
                return {"success": False, "message": error_reason, "status_code": 401}

            # Complete session establishment
            reset_failed_attempts(acc_str)
            sess_data = create_server_session(
                db=db,
                user=user,
                account_number=acc_str,
                role=user.role or "user",
                is_demo=False,
                ip=ip
            )

            log_auth_success(acc_str, ip)
            return {
                "success": True,
                "session_token": sess_data["session_token"],
                "csrf_token": sess_data["csrf_token"],
                "message": "MFA verification successful. Welcome back.",
                "user": {
                    "account_number": acc_str,
                    "name": user.name,
                    "role": user.role,
                    "email": user.email,
                    "customer_id": user.customer_id
                },
                "status_code": 200
            }

    def authenticate_demo(self, account_number: str, ip: str) -> Dict[str, Any]:
        """
        Handle demo login strictly for explicitly configured demo accounts.
        Enforces read-only permissions and guarantees no administrative privileges.
        """
        acc_str = str(account_number or "").strip()
        configured_demos = Config.CONFIGURED_DEMO_ACCOUNTS

        if not configured_demos:
            log_auth_failure(acc_str, ip, "Demo logins disabled: no accounts configured")
            return {
                "success": False,
                "message": "Demo login is disabled: no demo accounts are provisioned in this environment.",
                "status_code": 403
            }

        # Reject public arbitrary demo login attempts
        if acc_str not in configured_demos:
            log_auth_failure(acc_str, ip, "Arbitrary demo login attempt rejected")
            return {
                "success": False,
                "message": "Arbitrary demo logins are disabled. Only explicitly configured demo accounts are permitted.",
                "status_code": 403
            }

        with get_db() as db:
            acc = account_repository.get_by_number(db, acc_str)
            if not acc or not acc.user:
                return {
                    "success": False,
                    "message": "Configured demo account not found.",
                    "status_code": 404
                }
            user = acc.user

            # Rotate session and establish read-only demo session in PostgreSQL
            sess_data = create_server_session(
                db=db,
                user=user,
                account_number=acc_str,
                role="demo",
                is_demo=True,
                ip=ip
            )

            log_auth_success(acc_str, ip)
            return {
                "success": True,
                "session_token": sess_data["session_token"],
                "csrf_token": sess_data["csrf_token"],
                "message": "Demo login successful. Session is read-only.",
                "user": {
                    "account_number": acc_str,
                    "name": user.name,
                    "role": "demo",
                    "email": user.email,
                    "customer_id": user.customer_id,
                    "is_demo": True
                },
                "status_code": 200
            }

    def logout_user(self, ip: str) -> Dict[str, Any]:
        """Invalidate server session in PostgreSQL (actual server-side revocation)."""
        token = get_session_token_from_request()
        acc = session.get("user_id")
        with get_db() as db:
            if token:
                token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
                db.query(SessionRecord).filter(
                    (SessionRecord.session_token_hash == token_hash) | (SessionRecord.session_id == token)
                ).update({"is_active": False}, synchronize_session=False)
            if acc:
                db.query(SessionRecord).filter(
                    SessionRecord.account_number == str(acc)
                ).update({"is_active": False}, synchronize_session=False)
            db.commit()

        session.clear()
        return {
            "success": True,
            "message": "Signed out successfully.",
            "status_code": 200
        }


auth_service = AuthenticationService()
