"""
Credence Core — Web UI & Static Frontend Routes
Serves the consolidated responsive banking dashboard and client scripts.
"""

import os
from flask import Blueprint, send_from_directory, redirect, session, request
from bs4 import BeautifulSoup
from backend.app.core.config import Config

frontend_bp = Blueprint("frontend_bp", __name__)


def send_ui_file(filename: str):
    base_dir = Config.BASE_DIR
    filepath = os.path.join(base_dir, filename)
    if not os.path.exists(filepath):
        filepath = os.path.join(base_dir, "ui_code", filename)
    if not os.path.exists(filepath):
        filepath = filename

    with open(filepath, 'r', encoding='utf-8') as f:
        html = f.read()
    soup = BeautifulSoup(html, 'html.parser')
    existing_script = soup.find("script", src="/app.js")
    if not existing_script and soup.body:
        script_tag = soup.new_tag("script", src="/app.js")
        soup.body.append(script_tag)
    return str(soup)


@frontend_bp.route("/")
@frontend_bp.route("/index")
def index():
    return send_ui_file("code.html")


@frontend_bp.route("/dashboard")
def dashboard():
    token = request.cookies.get("session_token") or session.get("session_token")
    if not token:
        session.clear()
        return redirect("/?auth_required=true")

    try:
        from database import get_db
        from models import SessionRecord
        import hashlib, datetime
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        with get_db() as db:
            s_rec = db.query(SessionRecord).filter(
                (SessionRecord.session_token_hash == token_hash) | (SessionRecord.session_id == token)
            ).first()
            now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
            if not s_rec or not s_rec.is_active or s_rec.expires_at <= now:
                session.clear()
                return redirect("/?auth_required=true")
    except Exception:
        pass

    return send_ui_file("code(1).html")


@frontend_bp.route("/account")
@frontend_bp.route("/accounts")
@frontend_bp.route("/upi")
@frontend_bp.route("/loan")
@frontend_bp.route("/loans")
@frontend_bp.route("/transactions")
@frontend_bp.route("/history")
@frontend_bp.route("/analytics")
@frontend_bp.route("/reports")
@frontend_bp.route("/statement")
@frontend_bp.route("/settings")
@frontend_bp.route("/invest")
@frontend_bp.route("/investments")
@frontend_bp.route("/sip")
@frontend_bp.route("/ipo")
@frontend_bp.route("/mutualfunds")
@frontend_bp.route("/fd")
@frontend_bp.route("/fds")
@frontend_bp.route("/transfer")
@frontend_bp.route("/pay")
@frontend_bp.route("/services")
@frontend_bp.route("/cards")
@frontend_bp.route("/card")
def banking_views():
    if not session.get("user_id"):
        return redirect("/?auth_required=true")
    return send_ui_file("code(1).html")


@frontend_bp.route("/app.js")
def serve_app_js():
    base_dir = Config.BASE_DIR
    target_dir = base_dir if os.path.exists(os.path.join(base_dir, "app.js")) else (
        os.path.join(base_dir, "ui_code") if os.path.exists(os.path.join(base_dir, "ui_code", "app.js")) else base_dir
    )
    response = send_from_directory(target_dir, "app.js", mimetype="application/javascript")
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response
