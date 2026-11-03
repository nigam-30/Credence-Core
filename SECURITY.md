# Credence Core Security Policy

## 1. Overview
Credence Core employs institutional-grade security controls designed to emulate real-world core banking safeguards. This document outlines our vulnerability disclosure process, threat model, and cryptographic guarantees.

## 2. Supported Versions
Only the latest release version on the `main` branch receives active security updates and vulnerability patches.

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

## 3. Reporting a Vulnerability
If you discover a security vulnerability in Credence Core, please report it responsibly:
- **Email**: Send details to `security@credence.bank` (or project maintainers via private GitHub security advisory).
- **Details to Include**:
  - Description of the vulnerability and attack vector.
  - Minimal reproducible example or HTTP request trace.
  - Affected endpoint(s) or module(s).
  - Remediation recommendations (if known).
- Please **do not** open public GitHub issues for security vulnerabilities until an advisory and fix have been published.
- Maintainers aim to acknowledge reports within 48 hours and provide a fix timeline within 7 days.

## 4. Security Architecture & Controls

### 4.1 Cryptographic Standards
- **Password & PIN Hashing**: Implemented with **Argon2id** (`m=65536, t=2, p=2`) with zero plaintext storage and zero legacy fallback.
- **MFA Secrets**: Multi-factor authentication secrets are AES-256-GCM encrypted at rest using a dedicated `MFA_ENCRYPTION_KEY`.
- **Session Tokens**: Cryptographically secure, high-entropy tokens stored server-side in PostgreSQL with strict 30-minute idle expiration and automatic rotation upon privilege escalation.

### 4.2 Financial Integrity
- **Integer Arithmetic**: All monetary transactions are recorded and calculated strictly in integer subunits (paise) using `Decimal` with banker's rounding (`ROUND_HALF_EVEN`), eliminating floating-point errors.
- **Double-Entry Bookkeeping**: Strict immutable debit/credit balancing across balanced ledger accounts with mathematical zero-discrepancy guarantees.
- **Concurrency & Idempotency**: Pessimistic database row locks (`SELECT FOR UPDATE`) and payload-fingerprinted idempotency keys prevent race conditions, double spending, and replay attacks.

### 4.3 Web Security
- **Defense in Depth**: Automated CSRF synchronizer tokens, strict Content-Security-Policy (CSP), `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, and `Strict-Transport-Security`.
- **BOLA / IDOR Prevention**: Context-aware ownership authorization ensures clients can only access resources belonging to their verified identity.
- **Distributed Rate Limiting**: Redis-backed leaky-bucket rate limiters on all public authentication, transfer, and sensitive management routes with automatic IP and account lockouts.

## 5. Educational Simulator Disclaimer
Credence Core is an educational simulation environment. It does not connect to real central payment switches (NPCI, SWIFT, Fedwire) and must never be used with real-world financial credentials.
