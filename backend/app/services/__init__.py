"""
Credence Core — Services Package
"""

from backend.app.services.authentication import auth_service, AuthenticationService
from backend.app.services.accounts import account_service, AccountService
from backend.app.services.ledger import ledger_service, LedgerService
from backend.app.services.transfers import transfer_service, TransferService
from backend.app.services.payments import payment_service, PaymentService
from backend.app.services.investments import investment_service, InvestmentService
from backend.app.services.loans import loan_service, LoanService
from backend.app.services.cards import card_service, CardService
from backend.app.services.statements import statement_service, StatementService
from backend.app.services.notifications import notification_service, NotificationService
from backend.app.services.fraud import fraud_service, FraudDetectionService
from backend.app.services.admin import admin_service, AdminOperationsService
from backend.app.services.disputes import dispute_service, DisputeService
from backend.app.services.beneficiaries import beneficiary_service, BeneficiaryService
from backend.app.services.support import support_service, SupportService
from backend.app.services.analytics import analytics_service, AnalyticsService

__all__ = [
    "auth_service",
    "AuthenticationService",
    "account_service",
    "AccountService",
    "ledger_service",
    "LedgerService",
    "transfer_service",
    "TransferService",
    "payment_service",
    "PaymentService",
    "investment_service",
    "InvestmentService",
    "loan_service",
    "LoanService",
    "card_service",
    "CardService",
    "statement_service",
    "StatementService",
    "notification_service",
    "NotificationService",
    "fraud_service",
    "FraudDetectionService",
    "admin_service",
    "AdminOperationsService",
    "dispute_service",
    "DisputeService",
    "beneficiary_service",
    "BeneficiaryService",
    "support_service",
    "SupportService",
    "analytics_service",
    "AnalyticsService",
]
