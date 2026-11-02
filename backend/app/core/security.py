"""
Credence Core — Core Security Functions
Provides Argon2id hashing, PIN verification, CSRF token validation,
session security, and account lockout tracking.
"""

import security as root_security

hash_password = root_security.hash_password
verify_password = root_security.verify_password
hash_pin = root_security.hash_pin
verify_pin = root_security.verify_pin
migrate_user_profiles_security = root_security.migrate_user_profiles_security
is_account_locked = root_security.is_account_locked
record_failed_attempt = root_security.record_failed_attempt
reset_failed_attempts = root_security.reset_failed_attempts
generate_csrf_token = root_security.generate_csrf_token
validate_csrf = root_security.validate_csrf
csrf_protect = root_security.csrf_protect
login_required = root_security.login_required
require_role = root_security.require_role
verify_account_ownership = root_security.verify_account_ownership
check_ip_rate_limit = root_security.check_ip_rate_limit
rate_limit = root_security.rate_limit
def mask_pan(pan: str) -> str:
    pan_str = str(pan or "").strip()
    if len(pan_str) >= 4:
        return f"{pan_str[:2]}XXXXXX{pan_str[-2:]}"
    return "XXXXXXXXXX"

def mask_card(card: str) -> str:
    card_str = str(card or "").replace(" ", "").replace("-", "")
    if len(card_str) >= 4:
        return f"•••• •••• •••• {card_str[-4:]}"
    return "•••• •••• •••• 1234"

def sanitize_text(val: any, max_len: int = 150, max_length: int = None) -> str:
    limit = max_length if max_length is not None else max_len
    return root_security.sanitize_string(val, max_len=limit)
get_session_token_from_request = root_security.get_session_token_from_request
log_auth_success = root_security.log_auth_success
log_auth_failure = root_security.log_auth_failure
log_auth_lockout = root_security.log_auth_lockout
log_authz_failure = root_security.log_authz_failure
log_pin_failure = root_security.log_pin_failure
log_sensitive_operation = root_security.log_sensitive_op
security_logger = root_security.security_logger
