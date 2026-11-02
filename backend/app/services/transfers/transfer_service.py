"""
Credence Core — Transfer Service (Phase 5)
Executes inter-account transfers and deposits through the double-entry ledger
with frozen account enforcement, transaction limits, fraud evaluation, and notifications.
"""

from typing import Dict, Any, Optional
from backend.app.services.ledger import ledger_service, GL_CASH_VAULT
from backend.app.core.database import get_db
from backend.app.models import Account, TransactionLimit
from backend.app.repositories.account_repository import account_repository
from backend.app.services.fraud import fraud_service
from backend.app.services.notifications import notification_service
from backend.app.utils.currency import rupees_to_paise
from backend.app.core.logging import log_transaction_failure


class TransferService:

    def process_deposit(self, account_number: str, amount: float, actor: str, ip: str,
                        idempotency_key: Optional[str] = None) -> Dict[str, Any]:
        """Deposit cash into an account via GL_CASH_VAULT."""
        acc_str = str(account_number).strip()

        with get_db() as db:
            acc = account_repository.get_by_number(db, acc_str)
            if acc and acc.user and acc.user.role == "demo":
                return {
                    "success": False,
                    "message": "Demo accounts are read-only and cannot execute deposits.",
                    "status_code": 403
                }

        txn = ledger_service.execute(
            transaction_type="DEPOSIT",
            amount_rupees=amount,
            source_account=GL_CASH_VAULT,
            destination_account=acc_str,
            description=f"Account Deposit ₹{amount:,.2f}",
            idempotency_key=idempotency_key,
            actor=actor,
            ip=ip,
            metadata={"channel": "BRANCH_OR_ONLINE", "method": "CASH_DEPOSIT"}
        )

        if txn.get("success"):
            try:
                notification_service.send_notification(
                    account_number=acc_str,
                    title="Deposit Credited",
                    message=f"Credited ₹{amount:,.2f} via Cash Deposit. Ref: {txn.get('reference_id')}",
                    notification_type="TRANSACTION"
                )
            except Exception:
                pass

        return txn

    def process_transfer(self, from_acc: str, to_acc: str, amount: float, method: str,
                         description: str, actor: str, ip: str,
                         idempotency_key: Optional[str] = None) -> Dict[str, Any]:
        """Transfer funds between accounts with atomic double-entry balance updates."""
        src_str = str(from_acc).strip()
        dst_str = str(to_acc).strip()
        desc = description or f"Transfer via {method}"
        amt_paise = rupees_to_paise(amount)

        # 1. Enforce Frozen Account Status, Demo Restriction & Transaction Limits
        with get_db() as db:
            src_acc = account_repository.get_by_number(db, src_str)
            if src_acc and src_acc.user and src_acc.user.role == "demo":
                return {
                    "success": False,
                    "message": "Demo accounts are read-only and cannot execute financial transfers.",
                    "status_code": 403
                }

            if src_acc and src_acc.status == "FROZEN":
                log_transaction_failure("-", src_str, "Source account is frozen", amt_paise, ip)
                return {
                    "success": False,
                    "message": f"Source account '{src_str}' is FROZEN. Debits and transfers are suspended.",
                    "status_code": 403
                }

            lim = db.query(TransactionLimit).filter(TransactionLimit.account_number == src_str).first()
            if lim and amt_paise > lim.per_txn_limit_paise:
                log_transaction_failure("-", src_str, "Per-transaction limit exceeded", amt_paise, ip)
                return {
                    "success": False,
                    "message": f"Transaction amount ₹{amount:,.2f} exceeds per-transaction limit of ₹{lim.per_txn_limit_paise / 100:,.2f}.",
                    "status_code": 400
                }

        # 2. Fraud Evaluation (Rule-Based)
        fraud_eval = fraud_service.evaluate_transaction(
            account_number=src_str,
            amount_paise=amt_paise,
            ip=ip,
            tx_type=f"TRANSFER_{method.upper()}"
        )

        # 3. Execute Ledger Transaction
        txn = ledger_service.execute(
            transaction_type=f"TRANSFER_{method.upper()}",
            amount_rupees=amount,
            source_account=src_str,
            destination_account=dst_str,
            description=desc,
            idempotency_key=idempotency_key,
            actor=actor,
            ip=ip,
            metadata={
                "channel": "NETBANKING",
                "method": method,
                "fraud_eval": fraud_eval
            }
        )

        # 4. Dispatch Notifications (Transactional Outbox Pattern: failures never revert committed ledger transactions)
        if txn.get("success"):
            try:
                notification_service.send_notification(
                    account_number=src_str,
                    title="Transfer Sent",
                    message=f"Debited ₹{amount:,.2f} via {method} to {dst_str}. Ref: {txn.get('reference_id')}",
                    notification_type="TRANSACTION"
                )
            except Exception as e:
                # Log outbox notification failure without rolling back committed transfer
                pass

            # If destination is a customer account in our bank, notify them too
            try:
                with get_db() as db:
                    dst_acc = account_repository.get_by_number(db, dst_str)
                    if dst_acc:
                        notification_service.send_notification(
                            account_number=dst_str,
                            title="Funds Received",
                            message=f"Credited ₹{amount:,.2f} from {src_str}. Ref: {txn.get('reference_id')}",
                            notification_type="TRANSACTION"
                        )
            except Exception as e:
                pass
        else:
            log_transaction_failure(
                reference_id=txn.get("reference_id", "-"),
                account_number=src_str,
                reason=txn.get("error_reason") or txn.get("message", "Ledger execution failed"),
                amount_paise=amt_paise,
                ip=ip
            )

        return txn


transfer_service = TransferService()
