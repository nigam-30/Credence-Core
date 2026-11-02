"""
Credence Core — Transaction Dispute & Reversal Service (Phase 5)
Handles customer dispute filing, admin review, and automated double-entry ledger reversals.
"""

import json
import uuid
import datetime
from typing import Dict, Any, List, Optional

from backend.app.core.database import get_db
from backend.app.core.logging import security_logger, log_structured_event
from backend.app.models import Dispute, Transaction, Account, AuditLog, Notification
from backend.app.services.ledger import ledger_service


class DisputeService:

    def create_dispute(self, account_number: str, reference_id: str, reason: str, ip: str) -> Dict[str, Any]:
        """Customer raises a formal dispute on a past transaction."""
        acc_str = str(account_number).strip()
        ref = str(reference_id).strip()
        clean_reason = str(reason or "").strip()

        if not clean_reason:
            return {"success": False, "message": "Dispute reason is required.", "status_code": 400}

        with get_db() as db:
            txn = db.query(Transaction).filter(Transaction.reference_id == ref).first()
            if not txn:
                try:
                    import ledger
                    with ledger.ledger_engine._db_session() as conn:
                        cursor = conn.cursor()
                        cursor.execute("SELECT reference_id, transaction_type, state, amount_paise, source_account, destination_account, description FROM transactions WHERE reference_id = ?", (ref,))
                        row = cursor.fetchone()
                        if row:
                            txn = Transaction(
                                reference_id=row[0],
                                transaction_type=row[1],
                                state=row[2],
                                amount_paise=row[3],
                                source_account=row[4],
                                destination_account=row[5],
                                description=row[6]
                            )
                            db.add(txn)
                            db.commit()
                except Exception:
                    pass

            if not txn:
                return {"success": False, "message": f"Transaction '{ref}' not found.", "status_code": 404}

            if txn.source_account != acc_str and txn.destination_account != acc_str:
                return {"success": False, "message": "Cannot dispute a transaction not associated with your account.", "status_code": 403}

            if txn.state == "REVERSED":
                return {"success": False, "message": "Transaction has already been reversed.", "status_code": 400}

            # Check if active dispute already exists
            existing = db.query(Dispute).filter(
                Dispute.reference_id == ref,
                Dispute.status.in_(["SUBMITTED", "UNDER_REVIEW"])
            ).first()
            if existing:
                return {"success": False, "message": "An active dispute is already open for this transaction.", "status_code": 409}

            dispute_id = f"DSP-{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
            dispute = Dispute(
                dispute_id=dispute_id,
                reference_id=ref,
                account_number=acc_str,
                reason=clean_reason,
                disputed_amount_paise=txn.amount_paise,
                status="SUBMITTED"
            )
            db.add(dispute)

            # Audit Log
            audit = AuditLog(
                reference_id=ref,
                account_number=acc_str,
                actor=acc_str,
                action="DISPUTE_FILED",
                from_state=None,
                to_state="SUBMITTED",
                ip_address=ip,
                details_json=json.dumps({"dispute_id": dispute_id, "reason": clean_reason})
            )
            db.add(audit)

            # Customer Notification
            notif = Notification(
                account_number=acc_str,
                title="Dispute Filed Successfully",
                message=f"Dispute {dispute_id} for transaction {ref} (₹{txn.amount_paise / 100:.2f}) has been submitted for review.",
                notification_type="DISPUTE"
            )
            db.add(notif)
            db.commit()

        log_structured_event("DISPUTE_FILED", acc_str, ip, {"dispute_id": dispute_id, "reference_id": ref}, "INFO")
        return {
            "success": True,
            "message": "Dispute submitted successfully.",
            "dispute_id": dispute_id,
            "status": "SUBMITTED"
        }

    def get_account_disputes(self, account_number: str) -> List[Dict[str, Any]]:
        """List all disputes filed by a specific customer account."""
        acc_str = str(account_number).strip()
        with get_db() as db:
            disputes = db.query(Dispute).filter(Dispute.account_number == acc_str).order_by(Dispute.id.desc()).all()
            return [
                {
                    "dispute_id": d.dispute_id,
                    "reference_id": d.reference_id,
                    "account_number": d.account_number,
                    "disputed_amount_rupees": d.disputed_amount_paise / 100.0,
                    "reason": d.reason,
                    "status": d.status,
                    "resolution_notes": d.resolution_notes,
                    "created_at": d.created_at.isoformat()
                }
                for d in disputes
            ]

    def list_all_disputes(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Admin query of all platform disputes."""
        with get_db() as db:
            q = db.query(Dispute)
            if status:
                q = q.filter(Dispute.status == status)
            disputes = q.order_by(Dispute.id.desc()).all()
            return [
                {
                    "dispute_id": d.dispute_id,
                    "reference_id": d.reference_id,
                    "account_number": d.account_number,
                    "disputed_amount_rupees": d.disputed_amount_paise / 100.0,
                    "reason": d.reason,
                    "status": d.status,
                    "resolution_notes": d.resolution_notes,
                    "created_at": d.created_at.isoformat()
                }
                for d in disputes
            ]

    def resolve_dispute(
        self,
        dispute_id: str,
        action: str,  # "APPROVE_REFUND" or "REJECT"
        resolution_notes: str,
        admin_user: str,
        ip: str
    ) -> Dict[str, Any]:
        """Admin resolution of dispute with automatic ledger reversal on approval."""
        dsp_str = str(dispute_id).strip()
        act = action.strip().upper()
        clean_notes = str(resolution_notes or "").strip()

        if act not in ("APPROVE_REFUND", "REJECT"):
            return {"success": False, "message": "Action must be APPROVE_REFUND or REJECT.", "status_code": 400}

        with get_db() as db:
            dispute = db.query(Dispute).filter(Dispute.dispute_id == dsp_str).first()
            if not dispute:
                return {"success": False, "message": f"Dispute '{dsp_str}' not found.", "status_code": 404}

            if dispute.status in ("RESOLVED_REFUNDED", "REJECTED"):
                return {"success": False, "message": f"Dispute is already resolved (status: {dispute.status}).", "status_code": 400}

            prev_state = dispute.status

            if act == "APPROVE_REFUND":
                # Execute Double-Entry Ledger Reversal
                reversal_res = ledger_service.reverse(
                    reference_id=dispute.reference_id,
                    reason=f"Dispute {dsp_str} approved by admin: {clean_notes}",
                    actor=admin_user,
                    ip=ip
                )
                if not reversal_res.get("success"):
                    return {
                        "success": False,
                        "message": f"Ledger reversal failed: {reversal_res.get('message', 'Unknown error')}",
                        "status_code": 500
                    }

                dispute.status = "RESOLVED_REFUNDED"
                dispute.resolution_notes = f"Approved by {admin_user}. Reversal Reference: {reversal_res.get('reversal_reference')}. Notes: {clean_notes}"
                msg = f"Dispute '{dsp_str}' approved and full refund posted to ledger."

                # Notify customer
                notif = Notification(
                    account_number=dispute.account_number,
                    title="Dispute Approved — Refund Credited",
                    message=f"Dispute {dsp_str} for transaction {dispute.reference_id} was approved. ₹{dispute.disputed_amount_paise / 100:.2f} refunded.",
                    notification_type="REFUND"
                )
                db.add(notif)
            else:
                dispute.status = "REJECTED"
                dispute.resolution_notes = f"Rejected by {admin_user}. Notes: {clean_notes}"
                msg = f"Dispute '{dsp_str}' rejected."

                # Notify customer
                notif = Notification(
                    account_number=dispute.account_number,
                    title="Dispute Decision — Rejected",
                    message=f"Dispute {dsp_str} for transaction {dispute.reference_id} was reviewed and rejected. Notes: {clean_notes}",
                    notification_type="DISPUTE"
                )
                db.add(notif)

            dispute.updated_at = datetime.datetime.now(datetime.timezone.utc)

            # Audit Log
            audit = AuditLog(
                reference_id=dispute.reference_id,
                account_number=dispute.account_number,
                actor=admin_user,
                action=f"DISPUTE_{act}",
                from_state=prev_state,
                to_state=dispute.status,
                ip_address=ip,
                details_json=json.dumps({"dispute_id": dsp_str, "notes": clean_notes})
            )
            db.add(audit)
            final_dsp_status = dispute.status
            db.commit()

        log_structured_event(f"DISPUTE_{act}", admin_user, ip, {"dispute_id": dsp_str, "action": act}, "INFO")
        return {"success": True, "message": msg, "status": final_dsp_status}


dispute_service = DisputeService()
