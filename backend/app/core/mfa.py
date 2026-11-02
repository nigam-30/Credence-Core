"""
Credence Core — Multi-Factor Authentication (MFA / TOTP) Cryptographic Engine
Implements RFC 6238 Time-Based One-Time Passwords (TOTP), AES-256-GCM encryption at rest,
explicit key versioning, controlled key rotation, single-use recovery code hashes,
and TOTP time-step replay prevention.
"""

import os
import hmac
import hashlib
import struct
import time
import base64
import secrets
import json
from typing import List, Tuple, Optional, Any
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from backend.app.core.config import Config

CURRENT_KEY_VERSION = "v1"

# In-memory tracking of recent user-timestep acceptances to prevent replay
# user_id -> set of accepted timesteps (pruned periodically)
_ACCEPTED_TIMESTEPS = {}


def validate_mfa_encryption_key(key: str) -> None:
    """Validate that the MFA encryption key has sufficient cryptographic entropy."""
    if not key or not str(key).strip():
        raise ValueError("MFA_ENCRYPTION_KEY is required and cannot be empty.")
    clean = str(key).strip()
    if len(clean) < 32:
        raise ValueError("MFA_ENCRYPTION_KEY must contain at least 32 characters (256-bit entropy).")
    if clean in {
        "credence_fallback_secret_key_prod_32chars",
        "CREDENCE_CORE_ENTERPRISE_SECRET_KEY_PROD_2026",
        "change-me-to-a-secure-cryptographic-random-key-in-production",
        "secret", "secret_key", "password"
    }:
        raise ValueError("MFA_ENCRYPTION_KEY matches a known insecure default key.")


def _get_encryption_key(version: str = CURRENT_KEY_VERSION, custom_key: Optional[str] = None) -> bytes:
    """
    Derive a 256-bit encryption key strictly from dedicated MFA_ENCRYPTION_KEY.
    Zero silent fallback to SECRET_KEY.
    """
    if custom_key:
        validate_mfa_encryption_key(custom_key)
        return hashlib.sha256(custom_key.encode("utf-8")).digest()

    key_str = os.environ.get(f"MFA_ENCRYPTION_KEY_{version.upper()}") or os.environ.get("MFA_ENCRYPTION_KEY", "")
    if not key_str and hasattr(Config, "MFA_ENCRYPTION_KEY"):
        key_str = Config.MFA_ENCRYPTION_KEY or ""

    is_prod = os.environ.get("FLASK_ENV") == "production"
    if not key_str:
        if is_prod:
            raise RuntimeError("FATAL: Production MFA_ENCRYPTION_KEY is missing. Startup aborted.")
        # Ephemeral dev key for local test/dev isolation only
        key_str = "dev_mfa_ephemeral_key_min_32_chars_testing_only!"

    validate_mfa_encryption_key(key_str)
    return hashlib.sha256(key_str.encode("utf-8")).digest()


def encrypt_mfa_secret(plain_secret: str, version: str = CURRENT_KEY_VERSION) -> str:
    """
    Encrypt a TOTP secret using AES-256-GCM with explicit key version prefix.
    Payload format: {version}:{base64(nonce[12] + ciphertext)}
    """
    if not plain_secret:
        return ""
    key = _get_encryption_key(version=version)
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plain_secret.encode("utf-8"), None)
    payload = nonce + ciphertext
    b64_payload = base64.b64encode(payload).decode("ascii")
    return f"{version}:{b64_payload}"


def decrypt_mfa_secret(encrypted_secret: str) -> str:
    """
    Decrypt an encrypted TOTP secret from database, parsing key version header.
    Supports backward compatibility with legacy unversioned payloads.
    """
    if not encrypted_secret:
        return ""

    version = CURRENT_KEY_VERSION
    raw_payload = encrypted_secret
    if ":" in encrypted_secret:
        parts = encrypted_secret.split(":", 1)
        version = parts[0]
        raw_payload = parts[1]

    key = _get_encryption_key(version=version)
    aesgcm = AESGCM(key)
    payload = base64.b64decode(raw_payload.encode("ascii"))
    nonce = payload[:12]
    ciphertext = payload[12:]
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return plaintext.decode("utf-8")


def reencrypt_mfa_secret(encrypted_secret: str, new_key: str, new_version: str = "v2") -> str:
    """
    Decrypt an existing MFA secret and re-encrypt it under a new key and version identifier.
    Used for scheduled safe key rotation procedures without user re-enrollment.
    """
    plaintext = decrypt_mfa_secret(encrypted_secret)
    if not plaintext:
        return ""
    validate_mfa_encryption_key(new_key)
    key_bytes = hashlib.sha256(new_key.encode("utf-8")).digest()
    aesgcm = AESGCM(key_bytes)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    b64_payload = base64.b64encode(nonce + ciphertext).decode("ascii")
    return f"{new_version}:{b64_payload}"


def generate_mfa_secret() -> str:
    """Generate a random 160-bit Base32 secret string (RFC 6238 compliant)."""
    random_bytes = secrets.token_bytes(20)
    return base64.b32encode(random_bytes).decode("ascii").rstrip("=")


def get_totp_uri(secret: str, account_name: str, issuer: str = "Credence Bank") -> str:
    """Construct an RFC 6238 otpauth provisioning URI compatible with Google Authenticator and Authy."""
    encoded_issuer = issuer.replace(" ", "%20")
    encoded_account = account_name.replace(" ", "%20")
    return f"otpauth://totp/{encoded_issuer}:{encoded_account}?secret={secret}&issuer={encoded_issuer}&algorithm=SHA1&digits=6&period=30"


def generate_totp_code(secret: str, for_time: Optional[float] = None) -> str:
    """Generate a 6-digit TOTP code for a given secret at the specified timestamp."""
    t = for_time if for_time is not None else time.time()
    secret_clean = secret.strip().upper()
    missing_padding = len(secret_clean) % 8
    if missing_padding:
        secret_clean += "=" * (8 - missing_padding)

    key = base64.b32decode(secret_clean, casefold=True)
    counter = int(t // 30)
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code_int = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return f"{code_int % 1000000:06d}"


def verify_totp_code(secret: str, code: str, window: int = 1) -> bool:
    """
    Verify incoming 6-digit TOTP code against secret.
    Allows clock drift of ±window time steps (default 30 seconds).
    """
    clean_code = str(code or "").strip()
    if not clean_code or len(clean_code) != 6 or not clean_code.isdigit():
        return False

    now = time.time()
    for drift in range(-window, window + 1):
        target_time = now + (drift * 30)
        expected = generate_totp_code(secret, for_time=target_time)
        if hmac.compare_digest(clean_code, expected):
            return True
    return False


def verify_totp_code_with_replay_prevention(
    secret: str, code: str, user_id: int, window: int = 1
) -> Tuple[bool, Optional[str]]:
    """
    Verify incoming 6-digit TOTP code and strictly prevent replay of the same time-step.
    Returns (is_valid, error_reason).
    """
    clean_code = str(code or "").strip()
    if not clean_code or len(clean_code) != 6 or not clean_code.isdigit():
        return False, "Invalid TOTP format. Code must be 6 digits."

    now = time.time()
    current_step = int(now // 30)

    matched_step = None
    for drift in range(-window, window + 1):
        step = current_step + drift
        expected = generate_totp_code(secret, for_time=step * 30)
        if hmac.compare_digest(clean_code, expected):
            matched_step = step
            break

    if matched_step is None:
        return False, "Invalid verification code."

    # Check for replay attack within active window
    user_key = int(user_id)
    if user_key not in _ACCEPTED_TIMESTEPS:
        _ACCEPTED_TIMESTEPS[user_key] = set()

    # Prune old timesteps older than 10 minutes
    cutoff_step = current_step - 20
    _ACCEPTED_TIMESTEPS[user_key] = {s for s in _ACCEPTED_TIMESTEPS[user_key] if s >= cutoff_step}

    if matched_step in _ACCEPTED_TIMESTEPS[user_key]:
        return False, "This verification code has already been used. Please wait 30 seconds for a new code."

    _ACCEPTED_TIMESTEPS[user_key].add(matched_step)
    return True, None


def generate_recovery_codes(count: int = 8) -> Tuple[List[str], List[str]]:
    """
    Generate one-time backup recovery codes.
    Returns (plain_codes, hashed_codes).
    Only the secure SHA-256 hashes are ever stored in the database.
    """
    plain_codes = []
    hashed_codes = []
    for _ in range(count):
        part1 = secrets.token_hex(2).upper()
        part2 = secrets.token_hex(2).upper()
        part3 = secrets.token_hex(2).upper()
        code = f"{part1}-{part2}-{part3}"
        plain_codes.append(code)
        hashed_codes.append(hashlib.sha256(code.encode("utf-8")).hexdigest())
    return plain_codes, hashed_codes


def verify_and_consume_recovery_code(code: str, stored_hashes_json: Any) -> Tuple[bool, Optional[str]]:
    """
    Verify a one-time recovery code against stored hashes and immediately burn it upon match.
    Returns (is_valid, updated_hashes_json).
    """
    if not code or not stored_hashes_json:
        return False, stored_hashes_json

    if isinstance(stored_hashes_json, list):
        hashes = list(stored_hashes_json)
    else:
        try:
            hashes = json.loads(stored_hashes_json)
            if not isinstance(hashes, list):
                return False, stored_hashes_json
        except Exception:
            return False, stored_hashes_json

    clean_code = str(code).strip().upper()
    target_hash = hashlib.sha256(clean_code.encode("utf-8")).hexdigest()

    for idx, h in enumerate(hashes):
        if hmac.compare_digest(h, target_hash):
            hashes.pop(idx)
            return True, json.dumps(hashes) if not isinstance(stored_hashes_json, list) else hashes

    return False, stored_hashes_json
