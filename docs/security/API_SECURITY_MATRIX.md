# API SECURITY & ACCESS CONTROL MATRIX

> **SIMULATOR NOTICE:** Credence Core is an educational banking system simulator.

---

## 1. ENDPOINT SECURITY ARCHITECTURE

All API mutations enforce four defensive perimeters:
1. **Authentication:** Authenticated session validated against canonical PostgreSQL `sessions` record on every request.
2. **CSRF Protection:** Synchronizer token pattern via `X-CSRF-Token` header on all mutating methods (`POST`, `PUT`, `DELETE`, `PATCH`).
3. **Authorization & BOLA / IDOR:** Resource ownership verified via `verify_account_ownership()` or `require_role()`.
4. **Rate Limiting:** IP and account-level sliding-window rate limiting.

---

## 2. API SECURITY MATRIX

| HTTP Method | Route Endpoint | Required Role | CSRF Guard | Rate Limit | IDOR / BOLA Guard | Demo Restriction |
|---|---|---|---|---|---|---|
| `POST` | `/api/login` | Public | Optional | 30 req / min | N/A | Full Login |
| `POST` | `/api/mfa/verify` | Public (Ticket) | Optional | 5 req / 5 min | Validates challenge ticket | Read-only session if demo |
| `POST` | `/api/demo_login` | Public | Optional | 10 req / min | Configured accounts only | Assigned `demo` role |
| `POST` | `/api/logout` | Authenticated | Optional | None | Invalidates caller session | N/A |
| `POST` | `/api/account/verify_pin` | Authenticated | Required | 5 req / 5 min | Owns account only | Allowed |
| `GET` | `/api/account/<acc_no>` | Authenticated | N/A | 60 req / min | `verify_account_ownership` | Read-only |
| `POST` | `/api/transfer` | Authenticated | Required | 15 req / min | Checks caller ownership | **Blocked (403)** |
| `POST` | `/api/deposit` | Authenticated | Required | 15 req / min | Checks caller ownership | **Blocked (403)** |
| `POST` | `/api/pay_bill` | Authenticated | Required | 15 req / min | Checks caller ownership | **Blocked (403)** |
| `POST` | `/api/create_fd` | Authenticated | Required | 15 req / min | Checks caller ownership | **Blocked (403)** |
| `POST` | `/api/invest/gold_buy` | Authenticated | Required | 15 req / min | Checks caller ownership | **Blocked (403)** |
| `POST` | `/api/loan/apply` | Authenticated | Required | 15 req / min | Checks caller ownership | **Blocked (403)** |
| `GET` | `/api/admin/dashboard` | Admin Only | N/A | 30 req / min | Database role check | **Blocked (403)** |
| `POST` | `/api/admin/accounts/<acc_no>/freeze` | Admin Only | Required | 30 req / min | Database role check | **Blocked (403)** |
| `POST` | `/api/execute` | Admin Only | Required | 30 req / min | Database role check | **Blocked (403)** |

---

## 3. SECURITY HEADERS IMPLEMENTED

Every HTTP response emits:
- `Content-Security-Policy`: Restricts script and object evaluation.
- `X-Frame-Options: DENY`: Clickjacking prevention.
- `X-Content-Type-Options: nosniff`: MIME-sniffing prevention.
- `Strict-Transport-Security`: HSTS enabled in production (`max-age=31536000; includeSubDomains`).
- `Cache-Control: no-store, no-cache, must-revalidate`: Prevents sensitive banking data caching.
