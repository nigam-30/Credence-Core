"""
Credence Core — API Package
Registers all modular Blueprints.
"""

from flask import Flask
from backend.app.api.auth_routes import auth_bp
from backend.app.api.account_routes import account_bp
from backend.app.api.transfer_routes import transfer_bp
from backend.app.api.payment_routes import payment_bp
from backend.app.api.card_routes import card_bp
from backend.app.api.investment_routes import investment_bp
from backend.app.api.loan_routes import loan_bp
from backend.app.api.upi_routes import upi_bp
from backend.app.api.ledger_routes import ledger_bp
from backend.app.api.statement_routes import statement_bp
from backend.app.api.settings_routes import settings_bp
from backend.app.api.admin_routes import admin_bp
from backend.app.api.dispute_routes import dispute_bp
from backend.app.api.beneficiary_routes import beneficiary_bp
from backend.app.api.notification_routes import notification_bp
from backend.app.api.support_routes import support_bp
from backend.app.api.docs_routes import docs_bp
from backend.app.api.frontend_routes import frontend_bp
from backend.app.api.health_routes import health_bp


def register_blueprints(app: Flask):
    """Register all API and web controller Blueprints."""
    app.register_blueprint(health_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(account_bp)
    app.register_blueprint(transfer_bp)
    app.register_blueprint(payment_bp)
    app.register_blueprint(card_bp)
    app.register_blueprint(investment_bp)
    app.register_blueprint(loan_bp)
    app.register_blueprint(upi_bp)
    app.register_blueprint(ledger_bp)
    app.register_blueprint(statement_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(dispute_bp)
    app.register_blueprint(beneficiary_bp)
    app.register_blueprint(notification_bp)
    app.register_blueprint(support_bp)
    app.register_blueprint(docs_bp)
    app.register_blueprint(frontend_bp)
