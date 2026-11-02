"""
Credence Core — Payment Service
Handles utility bill payments and point-of-sale debit card payments.
"""

from typing import Dict, Any, Optional
from backend.app.services.ledger import ledger_service, GL_BILL_PAYMENT_CLEARING, GL_MERCHANT_SETTLEMENT


class PaymentService:
    def process_bill_payment(
        self,
        account_number: str,
        biller_name: str,
        category: str,
        amount: float,
        consumer_no: str,
        payment_method: str,
        actor: str,
        ip: str,
        idempotency_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """Pay utility bill to clearing escrow."""
        acc_str = str(account_number).strip()
        from backend.app.core.database import get_db
        from backend.app.repositories.account_repository import account_repository
        with get_db() as db:
            acc = account_repository.get_by_number(db, acc_str)
            if acc and acc.user and acc.user.role == "demo":
                return {
                    "success": False,
                    "message": "Demo accounts are read-only and cannot execute payments.",
                    "status_code": 403
                }

        txn = ledger_service.execute(
            transaction_type=f"BILL_PAY_{category.upper()}",
            amount_rupees=amount,
            source_account=acc_str,
            destination_account=GL_BILL_PAYMENT_CLEARING,
            description=f"{biller_name} ({consumer_no}) - {category}",
            idempotency_key=idempotency_key,
            actor=actor,
            ip=ip,
            metadata={"biller": biller_name, "category": category, "consumer_number": consumer_no, "method": payment_method}
        )
        return txn

    def process_debit_card_payment(
        self,
        account_number: str,
        merchant: str,
        amount: float,
        actor: str,
        ip: str,
        idempotency_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """Process debit card transaction at merchant terminal."""
        acc_str = str(account_number).strip()
        from backend.app.core.database import get_db
        from backend.app.repositories.account_repository import account_repository
        with get_db() as db:
            acc = account_repository.get_by_number(db, acc_str)
            if acc and acc.user and acc.user.role == "demo":
                return {
                    "success": False,
                    "message": "Demo accounts are read-only and cannot execute card payments.",
                    "status_code": 403
                }

        txn = ledger_service.execute(
            transaction_type="DEBIT_CARD_POS",
            amount_rupees=amount,
            source_account=acc_str,
            destination_account=GL_MERCHANT_SETTLEMENT,
            description=f"Debit Card Purchase at {merchant}",
            idempotency_key=idempotency_key,
            actor=actor,
            ip=ip,
            metadata={"merchant": merchant, "channel": "POS_TERMINAL"}
        )
        return txn


payment_service = PaymentService()
