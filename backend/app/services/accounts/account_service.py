"""
Credence Core — Account Service
Handles account creation, details inspection, profile updates, and settings.
"""

import secrets
import datetime
from typing import Dict, Any, List, Optional
from backend.app.core.database import get_db
from backend.app.core.security import hash_password, hash_pin, verify_password, mask_card
from backend.app.schemas.validators import validate_email, validate_pan, ValidationError
from backend.app.models import User, Account, AccountBalance, Card, UPIProfile
from backend.app.repositories.account_repository import account_repository
from backend.app.repositories.user_repository import user_repository
from backend.app.utils.currency import rupees_to_paise, paise_to_rupees


class AccountService:
    def get_account_details(self, account_number: str) -> Optional[Dict[str, Any]]:
        """Retrieve full account details for an authenticated user."""
        acc_str = str(account_number or "").strip()
        with get_db() as db:
            acc = account_repository.get_by_number(db, acc_str)
            if not acc:
                return None
            user = acc.user
            bal_rec = acc.balance_record
            card = acc.cards[0] if acc.cards else None
            fd = acc.fixed_deposits[0] if acc.fixed_deposits else None
            loan = acc.loans[0] if acc.loans else None
            upi = acc.upi_profile

            bal_rupees = float(bal_rec.balance_paise / 100) if bal_rec else 0.0
            fd_rupees = float(fd.principal_amount_paise / 100) if fd else 0.0
            loan_rupees = float(loan.outstanding_amount_paise / 100) if loan else 0.0

            card_info = None
            masked_card_num = ""
            if card:
                masked_card_num = mask_card(card.card_number_masked)
                card_info = {
                    "cardNumber": masked_card_num,
                    "nameOnCard": user.name if user else "Cardholder",
                    "expiry": card.expiry_month_year,
                    "company": card.card_network,
                    "status": card.status
                }

            return {
                "account_number": acc_str,
                "name": user.name if user else "Bank Customer",
                "email": user.email if user else "",
                "dob": user.dob if user else "",
                "address": user.address if user else "",
                "pan": user.pan if user else "",
                "employment_type": user.employment_type if user else "Salaried",
                "customer_id": user.customer_id if user else "",
                "balance": f"{bal_rupees:.2f}",
                "fixed_deposit": f"{fd_rupees:.2f}",
                "loan_amount": f"{loan_rupees:.2f}",
                "fd_tenure": str(fd.tenure_months) if fd else "12",
                "card": card_info,
                "card_number": masked_card_num,
                "expiry": card.expiry_month_year if card else "",
                "hasDebitCard": bool(card),
                "upi_id": upi.upi_id if upi else "",
                "role": user.role if user else "user",
                "status": acc.status
            }

    def create_account(self, name: str, deposit: float, debit_opt: str, pin: str,
                       upi_pin: Optional[str] = None, password: Optional[str] = None,
                       email: Optional[str] = None, pan: Optional[str] = None,
                       account_type: str = "Savings Account") -> Dict[str, Any]:
        """Create a new bank account with relational persistence and Argon2id hashing."""
        with get_db() as db:
            # Generate unique 14-digit account number using cryptographically secure randomness
            for _ in range(10):
                # Generates a 14-digit number starting with 4 (Credence prefix)
                suffix = secrets.randbelow(10**13)
                acc_no = f"4{suffix:013d}"
                if not account_repository.get_by_number(db, acc_no):
                    break
            else:
                raise RuntimeError("Failed to allocate a unique account number after multiple attempts.")

            # Customer ID generated cryptographically independent of account number
            cid = f"CUST-{secrets.token_hex(4).upper()}"
            if not password:
                raise ValueError("Password is required and must meet security criteria.")
            pwd_hash = hash_password(password)
            p_hash = hash_pin(pin) if pin else None

            # Enforce proper KYC validation on email and PAN
            valid_email = None
            if email:
                valid_email = validate_email(email)
            valid_pan = None
            if pan:
                valid_pan = validate_pan(pan)

            # Create User
            user = User(
                customer_id=cid,
                name=name,
                email=valid_email,
                pan=valid_pan,
                role="user",
                password_hash=pwd_hash,
                pin_hash=p_hash,
            )
            db.add(user)
            db.flush()

            # Create Account
            acc = Account(
                account_number=acc_no,
                user_id=user.id,
                account_type="CUSTOMER_SAVINGS",
                status="ACTIVE",
            )
            db.add(acc)
            db.flush()

            # Create Balance initialized to 0
            deposit_paise = int(round(deposit * 100))
            bal = AccountBalance(
                account_number=acc_no,
                balance_paise=0,
                lien_paise=0,
            )
            db.add(bal)
            db.commit()

            # Post initial deposit through double-entry ledger if deposit > 0
            if deposit > 0:
                from backend.app.services.ledger.ledger_service import ledger_service, GL_CASH_VAULT
                ledger_service.execute(
                    transaction_type="DEPOSIT",
                    amount_rupees=deposit,
                    source_account=GL_CASH_VAULT,
                    destination_account=acc_no,
                    description="Initial Account Opening Deposit",
                    actor="CUSTOMER_ONBOARDING",
                    ip="127.0.0.1",
                    metadata={"channel": "ONBOARDING", "initial_deposit": True}
                )

            # Create Card if opted
            card_info = None
            if debit_opt.lower() == "y":
                card_num = f"4092 8819 2401 {acc_no[-4:]}"
                exp = "10/30"
                card = Card(
                    account_number=acc_no,
                    card_type="DEBIT",
                    card_number_masked=card_num,
                    card_network="Visa",
                    expiry_month_year=exp,
                    pin_hash=p_hash,
                    status="ACTIVE",
                )
                db.add(card)
                card_info = {
                    "card_number": card_num,
                    "expiry": exp,
                    "company": "Visa"
                }

            return {
                "success": True,
                "account_number": acc_no,
                "customer_id": cid,
                "account_type": account_type,
                "name": name,
                "balance": deposit,
                "card": card_info,
                "message": f"Account created successfully with initial deposit of INR {deposit:.2f}."
            }

    def list_all_accounts(self) -> List[Dict[str, Any]]:
        """List all retail customer accounts for administrative views."""
        with get_db() as db:
            accounts = account_repository.list_customer_accounts(db)
            results = []
            for a in accounts:
                bal_rec = a.balance_record
                u = a.user
                fd = a.fixed_deposits[0] if a.fixed_deposits else None
                loan = a.loans[0] if a.loans else None
                results.append({
                    "account_number": a.account_number,
                    "name": u.name if u else "Customer",
                    "balance": float(bal_rec.balance_paise / 100) if bal_rec else 0.0,
                    "loanAmount": float(loan.outstanding_amount_paise / 100) if loan else 0.0,
                    "fixedDeposit": float(fd.principal_amount_paise / 100) if fd else 0.0,
                })
            return results


account_service = AccountService()
