"""
Credence Core — Repositories Package
"""

from backend.app.repositories.user_repository import user_repository, UserRepository
from backend.app.repositories.account_repository import account_repository, AccountRepository
from backend.app.repositories.transaction_repository import transaction_repository, TransactionRepository
from backend.app.repositories.investment_repository import investment_repository, InvestmentRepository
from backend.app.repositories.card_repository import card_repository, CardRepository
from backend.app.repositories.loan_repository import loan_repository, LoanRepository

__all__ = [
    "user_repository",
    "UserRepository",
    "account_repository",
    "AccountRepository",
    "transaction_repository",
    "TransactionRepository",
    "investment_repository",
    "InvestmentRepository",
    "card_repository",
    "CardRepository",
    "loan_repository",
    "LoanRepository",
]
