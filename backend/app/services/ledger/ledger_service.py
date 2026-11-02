"""
Credence Core — Ledger Service
Interfaces with the double-entry Financial Integrity Engine for atomic operations,
idempotency, reversals, and reconciliation.
"""

from typing import Dict, Any, Optional
import ledger as root_ledger

ledger_engine = root_ledger.ledger_engine
GL_CASH_VAULT = root_ledger.GL_CASH_VAULT
GL_CLEARING_ESCROW = root_ledger.GL_CLEARING_ESCROW
GL_BILL_PAYMENT_CLEARING = root_ledger.GL_BILL_PAYMENT_CLEARING
GL_MERCHANT_SETTLEMENT = root_ledger.GL_MERCHANT_SETTLEMENT
GL_INVESTMENT_ESCROW = root_ledger.GL_INVESTMENT_ESCROW
GL_GOLD_VAULT_CLEARING = root_ledger.GL_GOLD_VAULT_CLEARING
GL_LOAN_PRINCIPAL = root_ledger.GL_LOAN_PRINCIPAL
GL_FIXED_DEPOSIT_RESERVE = root_ledger.GL_FIXED_DEPOSIT_RESERVE
GL_ASBA_IPO_ESCROW = root_ledger.GL_ASBA_IPO_ESCROW


class LedgerService:
    @staticmethod
    def execute(
        transaction_type: str,
        amount_rupees: Any,
        source_account: str,
        destination_account: str,
        description: str,
        idempotency_key: Optional[str] = None,
        actor: str = "SYSTEM",
        ip: str = "127.0.0.1",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        return ledger_engine.execute_transaction(
            transaction_type=transaction_type,
            amount_rupees=amount_rupees,
            source_account=source_account,
            destination_account=destination_account,
            description=description,
            idempotency_key=idempotency_key,
            actor=actor,
            ip=ip,
            metadata=metadata
        )

    @staticmethod
    def reverse(reference_id: str, reason: str, actor: str = "ADMIN", ip: str = "127.0.0.1") -> Dict[str, Any]:
        return ledger_engine.reverse_transaction(reference_id, reason, actor, ip)

    @staticmethod
    def reconcile() -> Dict[str, Any]:
        return ledger_engine.reconcile_ledger()

    @staticmethod
    def get_history(account_number: str) -> list:
        return ledger_engine.get_transaction_history(account_number)


ledger_service = LedgerService()
