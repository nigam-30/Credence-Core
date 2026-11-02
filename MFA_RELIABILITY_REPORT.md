# Credence Core — MFA Reliability & Cryptographic Report
**Multi-Worker TOTP Replay Prevention, Key Versioning & Atomic Recovery Codes**

> **Educational Project Notice:**
> Credence Core is an educational banking simulator and architectural demonstrator. This report documents multi-factor authentication implementations for educational and engineering evaluation purposes.

---

## 1. Multi-Worker TOTP Replay Prevention Architecture

In high-concurrency production deployments where Gunicorn spawns multiple independent worker processes, process-local memory dictionaries fail to prevent replay attacks across workers. An attacker could intercept a valid TOTP code and submit it concurrently to two separate workers, having both accept the single time-step.

### Persistent Conditional Updates in Phase 6.3

Credence Core implements a two-tier persistent atomic verification model in `backend/app/core/mfa.py`:

```
Client TOTP Submission
         │
         ▼
[1. Distributed Redis Check] ──> Key: `totp_step:{user_id}:{matched_step}`
                                 Command: SET key "1" NX EX 120
                                 Result: Atomic mutex across cluster
         │
         ▼ (Passes)
[2. Database Row-Locking]   ──> Table: `users`
                                 Query: SELECT last_totp_step FROM users WHERE id = :id FOR UPDATE
                                 Check: IF matched_step <= last_totp_step -> REJECT
                                 Update: UPDATE users SET last_totp_step = :matched_step
                                 Commit transaction
```

### Concurrency Handling Invariants:
1. **Clock Drift Tolerance:** The server evaluates time-steps in the window `[-1, 0, +1]` (±30 seconds) relative to the server's current timestamp.
2. **Monotonic Step Ordering:** A code is accepted if and only if `matched_step > last_totp_step`. Any duplicate submission in the same 30-second window (or an older step) is rejected immediately.
3. **Pessimistic Row Locking (`FOR UPDATE`):** When two workers process requests for the same user concurrently, the second worker blocks until the first completes its transaction, observing the updated `last_totp_step` and safely rejecting the second attempt.
4. **Process Cache Fallback:** If the database record is in an uncommitted state (such as during transient unit testing), the engine falls back to a thread-safe local set with automated TTL eviction.

---

## 2. Cryptographic Key Management & Entropy Validation

MFA secrets are encrypted at rest using AES-256-GCM authenticated encryption.

### Entropy Verification Model:
1. **Decoded Entropy Check:** Raw keys provided via `MFA_ENCRYPTION_KEY` are analyzed for true binary entropy. If the key is provided as a Base64 string, it is decoded to ensure it represents at least 32 bytes (256 bits) of cryptographic entropy. Superficial string lengths (e.g. 32 ASCII characters like `"12345678901234567890123456789012"`) are rejected if they lack sufficient randomness.
2. **Fail-Fast Startup:** In `production` environment mode, if `MFA_ENCRYPTION_KEY` is missing or fails entropy validation, the application aborts startup immediately with a fatal configuration error. Silent fallback to `SECRET_KEY` is strictly prohibited.

### Key Versioning & Controlled Rotation:
Ciphertext envelopes follow an explicit versioned layout:
```
v1:<iv_hex>:<tag_hex>:<ciphertext_hex>
```
- Future key rotations introduce `v2:` envelopes.
- Decryption functions inspect the prefix to select the appropriate decryption key from a key keyring (`MFA_KEY_RING`).
- A controlled administrative re-encryption function allows existing `v1:` secrets to be decrypted and re-encrypted as `v2:` without requiring users to re-enroll authenticator apps.

---

## 3. Atomic Single-Use Recovery Code Model

When MFA is enabled, Credence Core generates 8 cryptographically secure recovery codes.

### Security Invariants:
1. **Never Stored in Plaintext:** Recovery codes are hashed with SHA-256 before being committed to the database.
2. **Atomic Single-Use Consumption:**
   - Verification computes the SHA-256 hash of the entered recovery code.
   - Using an atomic transaction, the engine locates the matching hash in `User.mfa_recovery_codes_hashes`.
   - If found, the hash is immediately deleted from the JSON array and committed in the same database transaction.
   - If two concurrent requests present the same recovery code, database row locking ensures only the first can match and delete it; the second will fail to find the hash and be rejected.
3. **Audit Trail Without Code Leakage:** Audit logs record the event `MFA_RECOVERY_CODE_CONSUMED` with timestamp, user ID, and IP address, but never record the recovery code or its hash.
