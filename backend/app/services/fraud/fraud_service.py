"""
Credence Core — Fraud & Risk Engine (Phase 5 / Phase 6.3 Hardening)
Rule-based detection engine for:
1. Unusual transaction amounts (vs. 30-day baseline or >= ₹200,000)
2. Repeated failed authentication attempts
3. High transaction velocity (> 4 transactions in 5 minutes)
4. Unusual transaction patterns (off-hours activity or balance drain > 80%)
5. Multiple failed PIN attempts

Enforces the critical policy:
'Do not automatically block legitimate customers solely based on an unverified risk score.'
Transactions are scored, flagged, and persisted to PostgreSQL for administrative review
without obstructing legitimate commerce.
"""

import time
import datetime
import json
from typing import Dict, Any, Tuple, Optional, List
from collections import defaultdict

from backend.app.core.database import get_db
from backend.app.core.financial_policy import FinancialPolicy
from backend.app.models import Account, Transaction, AccountBalance, AuditLog, Notification
from models import FraudAlert
from backend.app.core.logging import security_logger, log_structured_event
from backend.app.core.redis_client import get_redis_client
import security


class FraudDetectionService:
    def __init__(self):
        # account_number -> list of timestamp floats (local fallback if Redis unavailable)
        self.tx_history: Dict[str, List[float]] = defaultdict(list)
        self.pin_failures: Dict[str, List[float]] = defaultdict(list)

    def record_pin_failure(self, account_number: str, ip: str):
        """Record a failed PIN attempt with distributed Redis support."""
        now = time.time()
        redis_client = get_redis_client()
        if redis_client:
            try:
                key = f"fraud:pin_fails:{account_number}"
                redis_client.rpush(key, str(now))
                redis_client.expire(key, 3600)
            except Exception:
                pass

        self.pin_failures[account_number].append(now)
        cutoff = now - 3600
        self.pin_failures[account_number] = [ts for ts in self.pin_failures[account_number] if ts > cutoff]

    def evaluate_transaction(
        self,
        account_number: str,
        amount_paise: int,
        ip: str,
        tx_type: str
    ) -> Dict[str, Any]:
        """
        Evaluate transaction against centralized financial policy fraud rules.
        Persists generated fraud alerts to database for worker survival.
        """
        now = time.time()
        risk_score = 0
        risk_flags = []

        # ─── RULE 1: UNUSUAL TRANSACTION AMOUNTS ───
        if amount_paise >= FinancialPolicy.HIGH_VALUE_FRAUD_THRESHOLD_PAISE:
            risk_score += 40
            risk_flags.append("HIGH_VALUE_THRESHOLD_EXCEEDED")

        # Baseline comparison against past 30 days
        with get_db() as db:
            past_txns = db.query(Transaction).filter(
                Transaction.source_account == account_number,
                Transaction.state == "SUCCESSFUL"
            ).order_by(Transaction.id.desc()).limit(20).all()

            if past_txns:
                avg_paise = sum(t.amount_paise for t in past_txns) / len(past_txns)
                if amount_paise > (avg_paise * 5) and amount_paise > 2500000:
                    risk_score += 35
                    risk_flags.append("UNUSUAL_AMOUNT_VS_BASELINE")

        # ─── RULE 2: REPEATED FAILED AUTHENTICATION ───
        failed_auth_record = security.FAILED_ATTEMPTS_STORE.get(str(account_number), {})
        auth_failures = failed_auth_record.get("count", 0)
        if auth_failures >= 2:
            risk_score += 25
            risk_flags.append(f"RECENT_AUTH_FAILURES_{auth_failures}")

        # ─── RULE 3: HIGH TRANSACTION VELOCITY (REDIS / DB / MEMORY) ───
        redis_client = get_redis_client()
        velocity_count = 0
        if redis_client:
            try:
                v_key = f"fraud:velocity:{account_number}"
                pipe = redis_client.pipeline()
                cutoff = now - FinancialPolicy.FRAUD_VELOCITY_WINDOW_SECONDS
                pipe.zremrangebyscore(v_key, 0, cutoff)
                pipe.zadd(v_key, {str(now): now})
                pipe.zcard(v_key)
                pipe.expire(v_key, FinancialPolicy.FRAUD_VELOCITY_WINDOW_SECONDS + 60)
                res = pipe.execute()
                velocity_count = res[2]
            except Exception:
                pass

        if velocity_count == 0:
            history = self.tx_history[account_number]
            cutoff = now - FinancialPolicy.FRAUD_VELOCITY_WINDOW_SECONDS
            history = [ts for ts in history if ts > cutoff]
            self.tx_history[account_number] = history
            if len(history) >= FinancialPolicy.FRAUD_VELOCITY_MAX_TXNS:
                velocity_count = len(history)
            self.tx_history[account_number].append(now)

        if velocity_count >= FinancialPolicy.FRAUD_VELOCITY_MAX_TXNS:
            risk_score += 30
            risk_flags.append(f"HIGH_VELOCITY_SPIKE_{velocity_count}_IN_5M")

        # ─── RULE 4: UNUSUAL TRANSACTION PATTERNS ───
        current_hour = datetime.datetime.now().hour
        if 2 <= current_hour <= 5 and amount_paise > 1000000:  # > ₹10,000
            risk_score += 20
            risk_flags.append("OFF_HOURS_HIGH_VALUE")

        # Severe balance drain (> 80% balance outgoing in single transaction)
        with get_db() as db:
            bal_rec = db.query(AccountBalance).filter(AccountBalance.account_number == account_number).first()
            if bal_rec and bal_rec.balance_paise > 0:
                drain_pct = (amount_paise / bal_rec.balance_paise) * 100
                if drain_pct >= float(FinancialPolicy.FRAUD_BALANCE_DRAIN_PCT * 100) and amount_paise > 5000000:
                    risk_score += 25
                    risk_flags.append(f"SEVERE_BALANCE_DRAIN_{drain_pct:.1f}%")

        # ─── RULE 5: MULTIPLE FAILED PIN ATTEMPTS ───
        pin_fails = len(self.pin_failures.get(account_number, []))
        if pin_fails >= 2:
            risk_score += 30
            risk_flags.append(f"MULTIPLE_PIN_FAILURES_{pin_fails}")

        risk_score = min(risk_score, 100)

        # ─── PERSISTENT FRAUD ALERT GENERATION ───
        if risk_flags:
            alert_id = f"FRAUD-{int(now)}-{account_number[-4:]}"
            try:
                with get_db() as db:
                    fa = FraudAlert(
                        alert_id=alert_id,
                        account_number=account_number,
                        amount_paise=amount_paise,
                        tx_type=tx_type,
                        risk_score=risk_score,
                        risk_flags=json.dumps(risk_flags),
                        ip_address=ip,
                        status="OPEN"
                    )
                    db.add(fa)
                    db.commit()
            except Exception as e:
                security_logger.error(f"Failed to persist fraud alert: {e}")

            log_structured_event(
                event_type="FRAUD_ALERT",
                actor=account_number,
                ip=ip,
                details={"risk_score": risk_score, "flags": risk_flags, "amount_paise": amount_paise},
                level="WARNING"
            )

        requires_approval = risk_score >= 80 or amount_paise >= FinancialPolicy.DEFAULT_DAILY_LIMIT_PAISE

        return {
            "is_allowed": True,
            "risk_score": risk_score,
            "risk_flags": risk_flags,
            "requires_approval": requires_approval,
            "summary": "Risk evaluation clean" if not risk_flags else f"Flagged with: {', '.join(risk_flags)}"
        }

    def get_alerts(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve recent fraud monitoring alerts from database for admin dashboard."""
        try:
            with get_db() as db:
                alerts = db.query(FraudAlert).order_by(FraudAlert.id.desc()).limit(limit).all()
                out = []
                for a in alerts:
                    flags = []
                    try:
                        flags = json.loads(a.risk_flags)
                    except Exception:
                        flags = [a.risk_flags]
                    out.append({
                        "id": a.alert_id,
                        "account_number": a.account_number,
                        "amount_paise": a.amount_paise,
                        "amount_rupees": a.amount_paise / 100.0,
                        "tx_type": a.tx_type,
                        "risk_score": a.risk_score,
                        "risk_flags": flags,
                        "ip": a.ip_address,
                        "timestamp": a.created_at.isoformat() if a.created_at else "",
                        "status": a.status,
                        "resolution_action": a.resolution_action,
                        "resolved_by": a.resolved_by,
                        "resolved_at": a.resolved_at.isoformat() if a.resolved_at else None
                    })
                return out
        except Exception as e:
            security_logger.warning(f"Error querying fraud alerts: {e}")
            return []

    def resolve_alert(self, alert_id: str, action: str, admin_user: str) -> bool:
        """Resolve or dismiss a fraud alert in persistent storage."""
        try:
            with get_db() as db:
                alert = db.query(FraudAlert).filter(FraudAlert.alert_id == alert_id).first()
                if alert:
                    alert.status = "RESOLVED"
                    alert.resolution_action = action
                    alert.resolved_by = admin_user
                    alert.resolved_at = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
                    db.commit()
                    return True
        except Exception as e:
            security_logger.error(f"Error resolving fraud alert {alert_id}: {e}")
        return False


fraud_service = FraudDetectionService()
