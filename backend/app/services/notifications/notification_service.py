"""
Credence Core — Notification Service (Phase 5)
Dispatches user alerts, transaction receipts, security warnings, and manages read states.
"""

from typing import List, Dict, Any, Optional
from backend.app.core.database import get_db
from backend.app.models import Notification


class NotificationService:

    def send_notification(
        self,
        account_number: str,
        title: str,
        message: str,
        notification_type: str = "TRANSACTION"
    ) -> Dict[str, Any]:
        """Create and dispatch a new in-app notification."""
        acc_str = str(account_number).strip()
        with get_db() as db:
            notif = Notification(
                account_number=acc_str,
                title=str(title).strip(),
                message=str(message).strip(),
                notification_type=str(notification_type).strip().upper(),
                is_read=False
            )
            db.add(notif)
            db.commit()
            return {
                "id": notif.id,
                "account_number": acc_str,
                "title": notif.title,
                "message": notif.message,
                "type": notif.notification_type,
                "is_read": False,
                "created_at": notif.created_at.isoformat()
            }

    def list_notifications(self, account_number: str, limit: int = 50) -> Dict[str, Any]:
        """List notifications for an account with unread count."""
        acc_str = str(account_number).strip()
        with get_db() as db:
            items = db.query(Notification).filter(
                Notification.account_number == acc_str
            ).order_by(Notification.id.desc()).limit(limit).all()

            unread_count = db.query(Notification).filter(
                Notification.account_number == acc_str,
                Notification.is_read == False
            ).count()

            return {
                "unread_count": unread_count,
                "notifications": [
                    {
                        "id": n.id,
                        "title": n.title,
                        "message": n.message,
                        "type": n.notification_type,
                        "is_read": n.is_read,
                        "date": n.created_at.strftime("%d/%m/%Y %H:%M:%S"),
                        "created_at": n.created_at.isoformat()
                    }
                    for n in items
                ]
            }

    def mark_as_read(self, account_number: str, notification_id: Optional[int] = None) -> Dict[str, Any]:
        """Mark specific notification or all notifications as read."""
        acc_str = str(account_number).strip()
        with get_db() as db:
            q = db.query(Notification).filter(Notification.account_number == acc_str)
            if notification_id:
                q = q.filter(Notification.id == notification_id)
            updated = q.update({"is_read": True}, synchronize_session=False)
            db.commit()
            return {"success": True, "marked_read_count": updated}

    def delete_notification(self, account_number: str, notification_id: int) -> Dict[str, Any]:
        """Delete a notification."""
        acc_str = str(account_number).strip()
        with get_db() as db:
            notif = db.query(Notification).filter(
                Notification.id == notification_id,
                Notification.account_number == acc_str
            ).first()
            if not notif:
                return {"success": False, "message": "Notification not found.", "status_code": 404}
            db.delete(notif)
            db.commit()
            return {"success": True, "message": "Notification deleted."}


notification_service = NotificationService()
