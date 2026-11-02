"""
Credence Core — Notification Controller (Phase 5)
Provides in-app notification inbox, read acknowledgments, and deletion.
"""

from flask import Blueprint, request, jsonify, session
from backend.app.middleware.auth_middleware import login_required
from backend.app.middleware.csrf_middleware import verify_csrf_request
from backend.app.services.notifications import notification_service

notification_bp = Blueprint("notification_bp", __name__)


@notification_bp.route("/api/notifications", methods=["GET"])
@login_required
def list_notifications():
    """List in-app notifications for authenticated account with unread count."""
    acc_no = session.get("user_id")
    limit = min(int(request.args.get("limit", 50)), 100)
    data = notification_service.list_notifications(acc_no, limit=limit)
    return jsonify({"success": True, **data})


@notification_bp.route("/api/notifications/read", methods=["POST"])
@login_required
def mark_read():
    """Mark all or specific notification as read."""
    csrf_err = verify_csrf_request()
    if csrf_err:
        return csrf_err

    acc_no = session.get("user_id")
    req = request.get_json(silent=True) or {}
    notif_id = req.get("notification_id")
    if notif_id is not None:
        try:
            notif_id = int(notif_id)
        except Exception:
            notif_id = None

    res = notification_service.mark_as_read(acc_no, notif_id)
    return jsonify(res)


@notification_bp.route("/api/notifications/<int:notif_id>", methods=["DELETE"])
@login_required
def delete_notification(notif_id):
    """Delete a notification."""
    csrf_err = verify_csrf_request()
    if csrf_err:
        return csrf_err

    acc_no = session.get("user_id")
    res = notification_service.delete_notification(acc_no, notif_id)
    status_code = res.get("status_code", 200)
    return jsonify(res), status_code
