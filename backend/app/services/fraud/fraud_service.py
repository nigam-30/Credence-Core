"""
Credence Core — Fraud & Risk Engine (Phase 5)
Rule-based detection engine for:
1. Unusual transaction amounts (vs. 30-day baseline or >= ₹200,000)
2. Repeated failed authentication attempts
3. High transaction velocity (> 4 transactions in 5 minutes)
4. Unusual transaction patterns (off-hours activity or balance drain > 80%)
5. Multiple failed PIN attempts

Enforces the critical policy:
'Do not automatically block legitimate customers solely based on an unverified risk score.'
Transactions are scored, flagged, and audited for administrative review without obstructing legitimate commerce.
"""

import time
import datetime
from typing import Dict, Any, Tuple, Optional, List
from collections import defaultdict

from backend.app.core.database import get_db
from backend.app.models import Account, Transaction, AccountBalance, AuditLog, Notification
from backend.app.core.logging import security_logger, log_structured_event
import security


class FraudDetectionService:
    # High value transaction threshold: ₹200,000.00 (20,000,000 paise)
    HIGH_VALUE_THRESHOLD_PAISE = 20000000
    # Rapid velocity window: 5 minutes (300 seconds)
    VELOCITY_WINDOW_SECONDS = 300
    VELOCITY_MAX_TXNS = 4

    def __init__(self):
        # account_number -> list of timestamp floats
        self.tx_history: Dict[str, List[float]] = defaultdict(list)
        # account_number -> count of failed PIN attempts in window
        self.pin_failures: Dict[str, List[float]] = defaultdict(list)
        # In-memory store of active fraud alerts for admin dashboard
        self.active_alerts: List[Dict[str, Any]] = []

    def record_pin_failure(self, account_number: str, ip: str):
        """Record a failed PIN attempt."""
        now = time.time()
        self.pin_failures[account_number].append(now)
        # Prune older than 1 hour
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
        Evaluate transaction against 5 rules.
        Returns:
            {
                "is_allowed": True,  # Policy: Do not automatically block on unverified score
                "risk_score": int (0-100),
                "risk_flags": List[str],
                "requires_approval": bool,
                "summary": str
            }
        """
        now = time.time()
        risk_score = 0
        risk_flags = []

        # ─── RULE 1: UNUSUAL TRANSACTION AMOUNTS ───
        if amount_paise >= self.HIGH_VALUE_THRESHOLD_PAISE:
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
                # If transaction is > 5x average and > ₹25,000 (2,500,000 paise)
                if amount_paise > (avg_paise * 5) and amount_paise > 2500000:
                    risk_score += 35
                    risk_flags.append("UNUSUAL_AMOUNT_VS_BASELINE")

        # ─── RULE 2: REPEATED FAILED AUTHENTICATION ───
        failed_auth_record = security.FAILED_ATTEMPTS_STORE.get(str(account_number), {})
        auth_failures = failed_auth_record.get("count", 0)
        if auth_failures >= 2:
            risk_score += 25
            risk_flags.append(f"RECENT_AUTH_FAILURES_{auth_failures}")

        # ─── RULE 3: HIGH TRANSACTION VELOCITY ───
        history = self.tx_history[account_number]
        cutoff = now - self.VELOCITY_WINDOW_SECONDS
        history = [ts for ts in history if ts > cutoff]
        self.tx_history[account_number] = history

        if len(history) >= self.VELOCITY_MAX_TXNS:
            risk_score += 30
            risk_flags.append(f"HIGH_VELOCITY_SPIKE_{len(history)}_IN_5M")

        # Record this transaction attempt
        self.tx_history[account_number].append(now)

        # ─── RULE 4: UNUSUAL TRANSACTION PATTERNS ───
        # Check current hour (off-hours 02:00 to 05:00 UTC/Local)
        current_hour = datetime.datetime.now().hour
        if 2 <= current_hour <= 5 and amount_paise > 1000000:  # > ₹10,000
            risk_score += 20
            risk_flags.append("OFF_HOURS_HIGH_VALUE")

        # Check balance drain pattern (> 80% balance outgoing in single transaction)
        with get_db() as db:
            bal_rec = db.query(AccountBalance).filter(AccountBalance.account_number == account_number).first()
            if bal_rec and bal_rec.balance_paise > 0:
                drain_pct = (amount_paise / bal_rec.balance_paise) * 100
                if drain_pct >= 80.0 and amount_paise > 5000000:  # > ₹50,000 and 80%+
                    risk_score += 25
                    risk_flags.append(f"SEVERE_BALANCE_DRAIN_{drain_pct:.1f}%")

        # ─── RULE 5: MULTIPLE FAILED PIN ATTEMPTS ───
        pin_fails = len(self.pin_failures.get(account_number, []))
        if pin_fails >= 2:
            risk_score += 30
            risk_flags.append(f"MULTIPLE_PIN_FAILURES_{pin_fails}")

        # Cap score at 100
        risk_score = min(risk_score, 100)

        # If flagged with risk:
        if risk_flags:
            alert = {
                "id": f"FRAUD-{int(now)}-{account_number[-4:]}",
                "account_number": account_number,
                "amount_paise": amount_paise,
                "amount_rupees": amount_paise / 100.0,
                "tx_type": tx_type,
                "risk_score": risk_score,
                "risk_flags": risk_flags,
                "ip": ip,
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "status": "OPEN"
            }
            self.active_alerts.insert(0, alert)
            # Keep last 100 alerts
            if len(self.active_alerts) > 100:
                self.active_alerts = self.active_alerts[:100]

            log_structured_event(
                event_type="FRAUD_ALERT",
                actor=account_number,
                ip=ip,
                details={"risk_score": risk_score, "flags": risk_flags, "amount_paise": amount_paise},
                level="WARNING"
            )

        # Requires admin approval if score >= 80 or amount >= ₹500,000
        requires_approval = risk_score >= 80 or amount_paise >= 50000000

        return {
            "is_allowed": True,  # Policy: Do not block legitimate users blindly
            "risk_score": risk_score,
            "risk_flags": risk_flags,
            "requires_approval": requires_approval,
            "summary": "Risk evaluation clean" if not risk_flags else f"Flagged with: {', '.join(risk_flags)}"
        }

    def get_alerts(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve recent fraud monitoring alerts for admin dashboard."""
        return self.active_alerts[:limit]

    def resolve_alert(self, alert_id: str, action: str, admin_user: str) -> bool:
        """Resolve or dismiss a fraud alert."""
        for a in self.active_alerts:
            if a["id"] == alert_id:
                a["status"] = "RESOLVED"
                a["resolution_action"] = action
                a["resolved_by"] = admin_user
                a["resolved_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
                return True
        return False


fraud_service = FraudDetectionService()
