"""
Credence Core — Beneficiary Management Service (Phase 5)
Handles registration, listing, deletion, and quick transfers for verified beneficiaries.
"""

from typing import Dict, Any, List, Optional
from backend.app.core.database import get_db
from backend.app.models import Beneficiary, Account
from backend.app.schemas.validators import validate_account_number, ValidationError
from backend.app.services.transfers import transfer_service


class BeneficiaryService:

    def list_beneficiaries(self, account_number: str) -> List[Dict[str, Any]]:
        """List all active beneficiaries for an account."""
        acc_str = str(account_number).strip()
        with get_db() as db:
            bens = db.query(Beneficiary).filter(
                Beneficiary.account_number == acc_str,
                Beneficiary.status == "ACTIVE"
            ).order_by(Beneficiary.beneficiary_name.asc()).all()

            return [
                {
                    "id": b.id,
                    "beneficiary_name": b.beneficiary_name,
                    "beneficiary_account_number": b.beneficiary_account_number,
                    "ifsc_code": b.ifsc_code,
                    "transfer_type": b.transfer_type,
                    "created_at": b.created_at.isoformat()
                }
                for b in bens
            ]

    def add_beneficiary(
        self,
        account_number: str,
        beneficiary_name: str,
        beneficiary_account_number: str,
        ifsc_code: str = "CRDN0001001",
        transfer_type: str = "IMPS"
    ) -> Dict[str, Any]:
        """Register a new payee beneficiary."""
        acc_str = str(account_number).strip()
        name = str(beneficiary_name or "").strip()
        ben_acc = str(beneficiary_account_number or "").strip()
        ifsc = str(ifsc_code or "CRDN0001001").strip().upper()
        xfer_type = str(transfer_type or "IMPS").strip().upper()

        if not name or len(name) < 2:
            return {"success": False, "message": "Beneficiary name must be at least 2 characters.", "status_code": 400}

        try:
            ben_acc = validate_account_number(ben_acc)
        except ValidationError as e:
            return {"success": False, "message": str(e), "status_code": 400}

        if ben_acc == acc_str:
            return {"success": False, "message": "Cannot register your own account as a beneficiary.", "status_code": 400}

        if xfer_type not in ("IMPS", "NEFT", "RTGS", "UPI"):
            xfer_type = "IMPS"

        with get_db() as db:
            existing = db.query(Beneficiary).filter(
                Beneficiary.account_number == acc_str,
                Beneficiary.beneficiary_account_number == ben_acc
            ).first()

            if existing:
                if existing.status == "ACTIVE":
                    return {"success": False, "message": "Beneficiary is already registered.", "status_code": 409}
                else:
                    existing.status = "ACTIVE"
                    existing.beneficiary_name = name
                    existing.ifsc_code = ifsc
                    existing.transfer_type = xfer_type
                    db.commit()
                    return {"success": True, "message": "Beneficiary reactivated successfully.", "id": existing.id}

            ben = Beneficiary(
                account_number=acc_str,
                beneficiary_name=name,
                beneficiary_account_number=ben_acc,
                ifsc_code=ifsc,
                transfer_type=xfer_type,
                status="ACTIVE"
            )
            db.add(ben)
            db.commit()
            return {"success": True, "message": "Beneficiary registered successfully.", "id": ben.id}

    def delete_beneficiary(self, account_number: str, beneficiary_id: int) -> Dict[str, Any]:
        """Delete or deactivate a beneficiary."""
        acc_str = str(account_number).strip()
        with get_db() as db:
            ben = db.query(Beneficiary).filter(
                Beneficiary.id == beneficiary_id,
                Beneficiary.account_number == acc_str
            ).first()

            if not ben:
                return {"success": False, "message": "Beneficiary not found.", "status_code": 404}

            db.delete(ben)
            db.commit()
            return {"success": True, "message": "Beneficiary removed successfully."}

    def quick_transfer(
        self,
        from_acc: str,
        beneficiary_id: int,
        amount: float,
        actor: str,
        ip: str,
        idempotency_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """One-click transfer to a pre-registered beneficiary."""
        acc_str = str(from_acc).strip()
        with get_db() as db:
            ben = db.query(Beneficiary).filter(
                Beneficiary.id == beneficiary_id,
                Beneficiary.account_number == acc_str,
                Beneficiary.status == "ACTIVE"
            ).first()

            if not ben:
                return {"success": False, "message": "Beneficiary not found or inactive.", "status_code": 404}

            to_acc = ben.beneficiary_account_number
            method = ben.transfer_type
            desc = f"Quick Transfer to {ben.beneficiary_name}"

        return transfer_service.process_transfer(
            from_acc=acc_str,
            to_acc=to_acc,
            amount=amount,
            method=method,
            description=desc,
            actor=actor,
            ip=ip,
            idempotency_key=idempotency_key
        )


beneficiary_service = BeneficiaryService()
