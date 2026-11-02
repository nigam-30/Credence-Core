"""
Credence Core — Customer Support Ticket Service (Phase 5)
Handles customer support ticket creation, tracking, administrative replies, and resolution.
"""

import uuid
import datetime
from typing import Dict, Any, List, Optional

from backend.app.core.database import get_db
from backend.app.models import SupportTicket, Notification, AuditLog
from backend.app.core.logging import security_logger, log_structured_event


class SupportService:

    def create_ticket(
        self,
        account_number: str,
        subject: str,
        category: str,
        priority: str,
        message: str,
        ip: str = "127.0.0.1"
    ) -> Dict[str, Any]:
        """Customer opens a new support inquiry ticket."""
        acc_str = str(account_number).strip()
        sub = str(subject or "").strip()
        msg = str(message or "").strip()
        cat = str(category or "GENERAL").strip().upper()
        prio = str(priority or "MEDIUM").strip().upper()

        if not sub:
            return {"success": False, "message": "Ticket subject is required.", "status_code": 400}
        if not msg:
            return {"success": False, "message": "Ticket description message is required.", "status_code": 400}

        if cat not in ("TRANSACTION", "ACCOUNT", "CARDS", "LOANS", "INVESTMENTS", "SECURITY", "GENERAL"):
            cat = "GENERAL"
        if prio not in ("LOW", "MEDIUM", "HIGH", "URGENT"):
            prio = "MEDIUM"

        ticket_id = f"TKT-{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

        with get_db() as db:
            ticket = SupportTicket(
                ticket_id=ticket_id,
                account_number=acc_str,
                subject=sub,
                category=cat,
                priority=prio,
                status="OPEN",
                message=msg
            )
            db.add(ticket)

            # Notification
            notif = Notification(
                account_number=acc_str,
                title="Support Ticket Created",
                message=f"Your support ticket {ticket_id} ('{sub}') has been logged. Our priority support desk is reviewing it.",
                notification_type="SUPPORT"
            )
            db.add(notif)
            db.commit()

        log_structured_event("SUPPORT_TICKET_CREATED", acc_str, ip, {"ticket_id": ticket_id, "priority": prio}, "INFO")
        return {
            "success": True,
            "message": "Support ticket created successfully.",
            "ticket_id": ticket_id,
            "status": "OPEN"
        }

    def get_customer_tickets(self, account_number: str) -> List[Dict[str, Any]]:
        """List all support tickets for an account."""
        acc_str = str(account_number).strip()
        with get_db() as db:
            tickets = db.query(SupportTicket).filter(
                SupportTicket.account_number == acc_str
            ).order_by(SupportTicket.id.desc()).all()

            return [
                {
                    "ticket_id": t.ticket_id,
                    "subject": t.subject,
                    "category": t.category,
                    "priority": t.priority,
                    "status": t.status,
                    "message": t.message,
                    "admin_response": t.admin_response,
                    "resolved_by": t.resolved_by,
                    "created_at": t.created_at.isoformat(),
                    "updated_at": t.updated_at.isoformat()
                }
                for t in tickets
            ]

    def list_all_tickets(
        self,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Admin view of all support tickets with optional filtering."""
        with get_db() as db:
            q = db.query(SupportTicket)
            if status:
                q = q.filter(SupportTicket.status == status.upper())
            if priority:
                q = q.filter(SupportTicket.priority == priority.upper())
            if category:
                q = q.filter(SupportTicket.category == category.upper())

            tickets = q.order_by(SupportTicket.id.desc()).all()
            return [
                {
                    "ticket_id": t.ticket_id,
                    "account_number": t.account_number,
                    "subject": t.subject,
                    "category": t.category,
                    "priority": t.priority,
                    "status": t.status,
                    "message": t.message,
                    "admin_response": t.admin_response,
                    "resolved_by": t.resolved_by,
                    "created_at": t.created_at.isoformat(),
                    "updated_at": t.updated_at.isoformat()
                }
                for t in tickets
            ]

    def reply_ticket(
        self,
        ticket_id: str,
        response_text: str,
        new_status: str,
        admin_user: str,
        ip: str
    ) -> Dict[str, Any]:
        """Admin responds to customer ticket and updates its resolution status."""
        tkt_str = str(ticket_id).strip()
        clean_resp = str(response_text or "").strip()
        status_str = str(new_status or "IN_PROGRESS").strip().upper()

        if status_str not in ("OPEN", "IN_PROGRESS", "RESOLVED", "CLOSED"):
            status_str = "IN_PROGRESS"

        with get_db() as db:
            ticket = db.query(SupportTicket).filter(SupportTicket.ticket_id == tkt_str).first()
            if not ticket:
                return {"success": False, "message": f"Support ticket '{tkt_str}' not found.", "status_code": 404}

            ticket.admin_response = clean_resp
            ticket.status = status_str
            ticket.resolved_by = admin_user
            ticket.updated_at = datetime.datetime.now(datetime.timezone.utc)

            # Notify customer
            notif = Notification(
                account_number=ticket.account_number,
                title=f"Support Ticket Update ({ticket.status})",
                message=f"Update on ticket {tkt_str} ('{ticket.subject}'): {clean_resp}",
                notification_type="SUPPORT"
            )
            db.add(notif)

            # Audit Log
            audit = AuditLog(
                account_number=ticket.account_number,
                actor=admin_user,
                action="SUPPORT_TICKET_REPLY",
                from_state=None,
                to_state=ticket.status,
                ip_address=ip,
                details_json=f'{{"ticket_id": "{tkt_str}", "status": "{status_str}"}}'
            )
            db.add(audit)
            db.commit()

        log_structured_event("SUPPORT_TICKET_REPLY", admin_user, ip, {"ticket_id": tkt_str, "status": status_str}, "INFO")
        return {"success": True, "message": f"Ticket '{tkt_str}' updated to {status_str}.", "status": status_str}


support_service = SupportService()
