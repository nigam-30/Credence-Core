# Credence Core — Fraud Detection Engine Report
**Centralized Policy Thresholds, Non-Blocking Evaluation & Persistent Alert Workflows**

> **Educational Project Notice:**
> Credence Core is an educational banking simulation platform and architectural demonstrator. This report documents risk analysis and fraud heuristics for engineering design purposes.

---

## 1. Centralized Policy Constants & Rationales

All operational thresholds for risk evaluation and fraud detection are centralized within `backend/app/core/financial_policy.py` (`FinancialPolicy`). Hardcoded numbers in arbitrary service files have been eradicated.

| Policy Constant | Default Value | Technical & Financial Rationale |
| :--- | :---: | :--- |
| `HIGH_VALUE_FRAUD_THRESHOLD_PAISE` | `20,000,000` (₹2,00,000.00) | Flags exceptionally large transfers for supervisory auditing while permitting standard retail banking operations. |
| `FRAUD_VELOCITY_WINDOW_SECONDS` | `300` (5 minutes) | Standard temporal window for detecting automated bot activity or credential stuffing bursts. |
| `FRAUD_VELOCITY_MAX_TXNS` | `4` | Maximum allowable transactions within the 5-minute velocity window before raising high-frequency risk flags. |
| `FRAUD_BALANCE_DRAIN_PCT` | `0.80` (80%) | Flags transactions that liquidate more than 80% of an account's total available liquidity. |
| `FRAUD_MAX_PIN_FAILURES` | `3` | Triggers a security freeze flag after 3 consecutive invalid PIN verification attempts within the velocity window. |

---

## 2. Non-Blocking Evaluation Principle

A fundamental requirement in commercial-grade banking systems is that automated fraud detection must not blindly block legitimate customer transactions without human or operational review:

1. **Advisory Risk Scoring:** The fraud engine calculates an aggregate risk score `[0 - 100]` and attaches diagnostic risk flags (`HIGH_VALUE_THRESHOLD_EXCEEDED`, `RAPID_TRANSACTION_BURST`, `SUSPICIOUS_BALANCE_DRAIN`).
2. **Execution Independence:** If the transaction passes double-entry balance and authorization checks, the ledger transaction is permitted to execute, preventing false-positive lockouts during critical customer payments.
3. **Audit & Escalation:** Simultaneously, an alert is dispatched to the compliance logging subsystem and saved to the relational database for administrative resolution.

---

## 3. Transaction Velocity & Balance-Drain Algorithms

### Transaction Velocity Evaluation:
```python
def check_velocity(account_number: str, window_seconds: int = 300, max_count: int = 4) -> bool:
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(seconds=window_seconds)
    recent_count = db.query(func.count(Transaction.id)).filter(
        Transaction.source_account == account_number,
        Transaction.created_at >= cutoff,
        Transaction.state == "SUCCESSFUL"
    ).scalar() or 0
    return recent_count >= max_count
```

### Balance-Drain Calculation:
```python
def check_balance_drain(current_balance_paise: int, transfer_amount_paise: int, threshold_pct: Decimal = Decimal("0.80")) -> bool:
    if current_balance_paise <= 0:
        return False
    drain_ratio = Decimal(transfer_amount_paise) / Decimal(current_balance_paise)
    return drain_ratio >= threshold_pct
```

---

## 4. Persistent Alert Creation & Resolution Workflow

In Phase 6.3, transient in-memory alert lists were replaced by the `FraudAlert` relational database model (`models.py`):

### Database Schema:
- `alert_id` (VARCHAR(64), Primary Key): Unique cryptographically generated identifier (`ALERT-XXXXXXXXXXXX`).
- `account_number` (VARCHAR(20), Indexed): Account under review.
- `amount_paise` (BIGINT): Financial value involved.
- `risk_score` (INTEGER): Calculated heuristic risk score.
- `risk_flags` (JSON): Array of specific rule violations.
- `status` (VARCHAR(20)): `OPEN`, `RESOLVED`, or `DISMISSED`.
- `resolved_by` (VARCHAR(50)): Identity of the reviewing compliance officer.
- `resolution_notes` (TEXT): Audit justification for alert disposition.
- `created_at` / `updated_at`: Immutable timestamps.

### Administrative Resolution API:
Supervisory personnel review open alerts via `POST /api/admin/fraud/resolve`:
```json
{
  "alert_id": "ALERT-8F9E123C",
  "resolution": "APPROVED_BY_ADMIN",
  "notes": "Customer confirmed intent via out-of-band telephone verification."
}
```
This guarantees an immutable audit trail for compliance oversight while preventing memory leaks or state loss on server restarts.
