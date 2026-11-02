"""
Credence Core — Admin Operations Service (Phase 5)
Provides system-wide KPIs, account state management (Freeze/Unfreeze),
audit inspection, and transaction approval processing.
"""

import json
import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy import func, text

from backend.app.core.database import get_db
from backend.app.core.logging import security_logger, log_structured_event
from backend.app.models import (
    User,
    Account,
    AccountBalance,
    Transaction,
    Loan,
    FixedDeposit,
    Investment,
    Dispute,
    AuditLog,
    Notification,
    SupportTicket
)
from backend.app.services.fraud import fraud_service
from backend.app.services.notifications import notification_service
import ledger


class AdminOperationsService:

    def get_dashboard_summary(self) -> Dict[str, Any]:
        """Aggregate bank-wide operational KPIs and metrics."""
        with get_db() as db:
            total_users = db.query(func.count(User.id)).scalar() or 0
            total_accounts = db.query(func.count(Account.id)).scalar() or 0
            active_accounts = db.query(func.count(Account.id)).filter(Account.status == "ACTIVE").scalar() or 0
            frozen_accounts = db.query(func.count(Account.id)).filter(Account.status == "FROZEN").scalar() or 0

            # Balances
            total_balance_paise = db.query(func.sum(AccountBalance.balance_paise)).scalar() or 0
            total_loans_paise = db.query(func.sum(Loan.outstanding_amount_paise)).filter(Loan.status == "ACTIVE").scalar() or 0
            total_fd_paise = db.query(func.sum(FixedDeposit.principal_amount_paise)).filter(FixedDeposit.status == "ACTIVE").scalar() or 0

            # Transactions
            total_txns = db.query(func.count(Transaction.id)).scalar() or 0
            pending_txns = db.query(func.count(Transaction.id)).filter(Transaction.state == "PENDING").scalar() or 0

            # Disputes & Tickets
            total_disputes = db.query(func.count(Dispute.id)).scalar() or 0
            pending_disputes = db.query(func.count(Dispute.id)).filter(Dispute.status.in_(["SUBMITTED", "UNDER_REVIEW"])).scalar() or 0
            open_tickets = db.query(func.count(SupportTicket.id)).filter(SupportTicket.status.in_(["OPEN", "IN_PROGRESS"])).scalar() or 0

            # Fraud Alerts
            active_alerts = fraud_service.get_alerts(limit=50)

            return {
                "success": True,
                "kpis": {
                    "total_users": total_users,
                    "total_accounts": total_accounts,
                    "active_accounts": active_accounts,
                    "frozen_accounts": frozen_accounts,
                    "total_deposits_rupees": float(total_balance_paise / 100),
                    "total_loans_rupees": float(total_loans_paise / 100),
                    "total_fixed_deposits_rupees": float(total_fd_paise / 100),
                    "total_transactions": total_txns,
                    "pending_approvals": pending_txns,
                    "total_disputes": total_disputes,
                    "pending_disputes": pending_disputes,
                    "open_support_tickets": open_tickets,
                    "active_fraud_alerts": len([a for a in active_alerts if a.get("status") == "OPEN"]),
                },
                "recent_fraud_alerts": active_alerts[:10]
            }

    def freeze_account(self, account_number: str, reason: str, admin_user: str, ip: str) -> Dict[str, Any]:
        """Freeze an account, suspending debits and outgoing mutations."""
        acc_str = str(account_number).strip()
        with get_db() as db:
            acc = db.query(Account).filter(Account.account_number == acc_str).first()
            if not acc:
                return {"success": False, "message": f"Account '{acc_str}' not found.", "status_code": 404}

            if acc.status == "FROZEN":
                return {"success": False, "message": f"Account '{acc_str}' is already frozen.", "status_code": 400}

            prev_state = acc.status
            acc.status = "FROZEN"

            # Synchronize with ledger SQLite DB accounts table
            try:
                with ledger.ledger_engine._db_session() as conn:
                    cursor = conn.cursor()
                    cursor.execute("UPDATE accounts SET status = 'FROZEN' WHERE account_number = ?", (acc_str,))
                    conn.commit()
            except Exception as e:
                security_logger.error(f"Error synchronizing ledger status for {acc_str}: {e}")

            # Audit log
            audit = AuditLog(
                account_number=acc_str,
                actor=admin_user,
                action="ACCOUNT_FROZEN",
                from_state=prev_state,
                to_state="FROZEN",
                ip_address=ip,
                details_json=json.dumps({"reason": reason, "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()})
            )
            db.add(audit)

            # Customer Notification
            notif = Notification(
                account_number=acc_str,
                title="Account Suspended (Frozen)",
                message=f"Your account {acc_str} has been temporarily frozen by bank administration. Reason: {reason}. Please contact customer support.",
                notification_type="SECURITY"
            )
            db.add(notif)
            db.commit()

        log_structured_event("ADMIN_ACCOUNT_FREEZE", admin_user, ip, {"account": acc_str, "reason": reason}, "WARNING")
        return {"success": True, "message": f"Account '{acc_str}' successfully frozen."}

    def unfreeze_account(self, account_number: str, reason: str, admin_user: str, ip: str) -> Dict[str, Any]:
        """Unfreeze an account, restoring full operational status."""
        acc_str = str(account_number).strip()
        with get_db() as db:
            acc = db.query(Account).filter(Account.account_number == acc_str).first()
            if not acc:
                return {"success": False, "message": f"Account '{acc_str}' not found.", "status_code": 404}

            if acc.status == "ACTIVE":
                return {"success": False, "message": f"Account '{acc_str}' is already active.", "status_code": 400}

            prev_state = acc.status
            acc.status = "ACTIVE"

            # Synchronize with ledger SQLite DB accounts table
            try:
                with ledger.ledger_engine._db_session() as conn:
                    cursor = conn.cursor()
                    cursor.execute("UPDATE accounts SET status = 'ACTIVE' WHERE account_number = ?", (acc_str,))
                    conn.commit()
            except Exception as e:
                security_logger.error(f"Error synchronizing ledger status for {acc_str}: {e}")

            # Audit log
            audit = AuditLog(
                account_number=acc_str,
                actor=admin_user,
                action="ACCOUNT_UNFROZEN",
                from_state=prev_state,
                to_state="ACTIVE",
                ip_address=ip,
                details_json=json.dumps({"reason": reason, "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()})
            )
            db.add(audit)

            # Customer Notification
            notif = Notification(
                account_number=acc_str,
                title="Account Reactivated",
                message=f"Your account {acc_str} has been successfully reactivated and unfrozen. Full banking services are restored.",
                notification_type="SECURITY"
            )
            db.add(notif)
            db.commit()

        log_structured_event("ADMIN_ACCOUNT_UNFREEZE", admin_user, ip, {"account": acc_str, "reason": reason}, "INFO")
        return {"success": True, "message": f"Account '{acc_str}' successfully unfrozen."}

    def get_audit_logs(
        self,
        actor: Optional[str] = None,
        action: Optional[str] = None,
        account_number: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Retrieve paginated administrative and financial audit logs."""
        with get_db() as db:
            q = db.query(AuditLog)
            if actor:
                q = q.filter(AuditLog.actor.ilike(f"%{actor}%"))
            if action:
                q = q.filter(AuditLog.action == action)
            if account_number:
                q = q.filter(AuditLog.account_number == account_number)

            total = q.count()
            logs = q.order_by(AuditLog.id.desc()).offset(offset).limit(limit).all()

            return {
                "success": True,
                "total": total,
                "logs": [
                    {
                        "id": log.id,
                        "reference_id": log.reference_id,
                        "account_number": log.account_number,
                        "actor": log.actor,
                        "action": log.action,
                        "from_state": log.from_state,
                        "to_state": log.to_state,
                        "ip_address": log.ip_address,
                        "details": json.loads(log.details_json) if log.details_json else {},
                        "created_at": log.created_at.isoformat()
                    }
                    for log in logs
                ]
            }

    def get_pending_approvals(self) -> List[Dict[str, Any]]:
        """List transactions awaiting administrative approval."""
        with get_db() as db:
            txns = db.query(Transaction).filter(Transaction.state == "PENDING").order_by(Transaction.id.desc()).all()
            return [
                {
                    "reference_id": t.reference_id,
                    "idempotency_key": t.idempotency_key,
                    "transaction_type": t.transaction_type,
                    "source_account": t.source_account,
                    "destination_account": t.destination_account,
                    "amount_rupees": t.amount_paise / 100.0,
                    "description": t.description,
                    "created_at": t.created_at.isoformat()
                }
                for t in txns
            ]

    def process_approval(self, reference_id: str, action: str, reason: str, admin_user: str, ip: str) -> Dict[str, Any]:
        """Approve or Reject a pending transaction."""
        ref = str(reference_id).strip()
        act = action.strip().upper()
        if act not in ("APPROVE", "REJECT"):
            return {"success": False, "message": "Action must be APPROVE or REJECT.", "status_code": 400}

        with get_db() as db:
            txn = db.query(Transaction).filter(Transaction.reference_id == ref).first()
            if not txn:
                return {"success": False, "message": f"Transaction '{ref}' not found.", "status_code": 404}

            if txn.state != "PENDING":
                return {"success": False, "message": f"Transaction '{ref}' is not in PENDING state (current: {txn.state}).", "status_code": 400}

            if act == "APPROVE":
                txn.state = "SUCCESSFUL"
                msg = f"Transaction '{ref}' approved and executed."
            else:
                txn.state = "FAILED"
                txn.error_reason = f"Rejected by administrator {admin_user}: {reason}"
                msg = f"Transaction '{ref}' rejected."

            txn.updated_at = datetime.datetime.now(datetime.timezone.utc)

            # Audit Log
            audit = AuditLog(
                reference_id=ref,
                account_number=txn.source_account,
                actor=admin_user,
                action=f"TXN_APPROVAL_{act}",
                from_state="PENDING",
                to_state=txn.state,
                ip_address=ip,
                details_json=json.dumps({"reason": reason, "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()})
            )
            db.add(audit)
            final_txn_state = txn.state
            db.commit()

        log_structured_event(f"TXN_APPROVAL_{act}", admin_user, ip, {"reference_id": ref, "reason": reason}, "INFO")
        return {"success": True, "message": msg, "state": final_txn_state}


admin_service = AdminOperationsService()
