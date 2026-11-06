"""
Credence Core — Investment Service
Handles Digital Gold buy/sell, Mutual Fund SIPs, IPO applications (ASBA),
Fixed Deposits (FDs), and Recurring Deposits (RDs).
"""

import datetime
from decimal import Decimal
from typing import Dict, Any, List, Optional
from backend.app.core.database import get_db
from backend.app.models import Investment, SIP, IPOApplication, RecurringDeposit, FixedDeposit
from backend.app.services.ledger import (
    ledger_service,
    GL_INVESTMENT_ESCROW,
    GL_GOLD_VAULT_CLEARING,
    GL_FIXED_DEPOSIT_RESERVE,
    GL_ASBA_IPO_ESCROW,
)
from backend.app.utils.currency import rupees_to_paise
from backend.app.core.financial_policy import FinancialPolicy
from backend.app.repositories.account_repository import account_repository


class InvestmentService:
    def get_user_investments(self, account_number: str) -> Dict[str, Any]:
        """Fetch all investments (SIPs, IPOs, RDs, Gold) for an account."""
        acc_str = str(account_number).strip()
        with get_db() as db:
            inv = db.query(Investment).filter(Investment.account_number == acc_str).first()
            sips = db.query(SIP).filter(SIP.account_number == acc_str).all()
            ipos = db.query(IPOApplication).filter(IPOApplication.account_number == acc_str).all()
            rds = db.query(RecurringDeposit).filter(RecurringDeposit.account_number == acc_str).all()

            return {
                "sips": [
                    {
                        "id": s.sip_id,
                        "fund_id": s.fund_id,
                        "fund_name": s.fund_name,
                        "category": s.category,
                        "type": s.investment_type,
                        "monthly_amount": s.monthly_amount_paise / 100,
                        "sip_day": s.sip_day,
                        "invested_amount": s.invested_amount_paise / 100,
                        "current_value": s.current_value_paise / 100,
                        "units": float(s.units or 0.0),
                        "nav": float(s.nav or 100.0),
                        "status": s.status,
                        "start_date": s.start_date,
                        "next_date": s.next_date
                    }
                    for s in sips
                ],
                "ipos": [
                    {
                        "app_no": i.app_no,
                        "ipo_id": i.ipo_id,
                        "company": i.company,
                        "symbol": i.symbol,
                        "shares": i.shares,
                        "price": i.bid_price_paise / 100,
                        "amount": i.amount_blocked_paise / 100,
                        "status": i.status
                    }
                    for i in ipos
                ],
                "rds": [
                    {
                        "id": r.rd_id,
                        "monthly_amount": r.monthly_amount_paise / 100,
                        "tenure_months": r.tenure_months,
                        "interest_rate": float(r.interest_rate_pct),
                        "total_deposited": r.total_deposited_paise / 100,
                        "maturity_amount": r.maturity_amount_paise / 100,
                        "status": r.status,
                        "start_date": r.start_date
                    }
                    for r in rds
                ],
                "gold": {
                    "grams": float(inv.gold_grams if inv else 0.0),
                    "avg_buy_price": (inv.gold_avg_buy_price_paise / 100) if inv else 7620.50,
                    "total_invested": (inv.gold_total_invested_paise / 100) if inv else 0.0,
                    "current_rate": 7620.50,
                    "current_value": round(float(inv.gold_grams if inv else 0.0) * 7620.50, 2),
                    "returns_pct": 0.0
                }
            }

    def buy_gold(self, account_number: str, amount: float, actor: str, ip: str,
                 idempotency_key: Optional[str] = None) -> Dict[str, Any]:
        """Buy digital gold and update vault records."""
        acc_str = str(account_number).strip()
        with get_db() as db:
            acc = account_repository.get_by_number(db, acc_str)
            if acc and acc.user and acc.user.role == "demo":
                raise ValueError("Demo accounts are read-only and cannot purchase investments.")

        gold_rate = float(FinancialPolicy.get_gold_rate_rupees())
        grams_bought = round(amount / gold_rate, 4)

        txn = ledger_service.execute(
            transaction_type="DIGITAL_GOLD_PURCHASE",
            amount_rupees=amount,
            source_account=acc_str,
            destination_account=GL_GOLD_VAULT_CLEARING,
            description=f"24K Digital Gold Purchase ({grams_bought}g @ ₹{gold_rate:,.2f}/g)",
            idempotency_key=idempotency_key,
            actor=actor,
            ip=ip,
            metadata={"grams": grams_bought, "rate": gold_rate}
        )

        with get_db() as db:
            inv = db.query(Investment).filter(Investment.account_number == acc_str).first()
            amt_paise = rupees_to_paise(amount)
            if not inv:
                inv = Investment(
                    account_number=acc_str,
                    gold_grams=grams_bought,
                    gold_total_invested_paise=amt_paise,
                    gold_avg_buy_price_paise=rupees_to_paise(gold_rate)
                )
                db.add(inv)
            else:
                inv.gold_grams = float(inv.gold_grams) + grams_bought
                inv.gold_total_invested_paise += amt_paise
            db.commit()

        return txn

    def sell_gold(self, account_number: str, grams: float, actor: str, ip: str,
                  idempotency_key: Optional[str] = None) -> Dict[str, Any]:
        """Sell digital gold holdings and credit proceeds to account."""
        acc_str = str(account_number).strip()
        if grams <= 0:
            raise ValueError("Gold grams must be greater than zero.")
        if grams > 10000:
            raise ValueError("Exceeds maximum allowable gold sale quantity.")

        with get_db() as db:
            acc = account_repository.get_by_number(db, acc_str)
            if acc and acc.user and acc.user.role == "demo":
                raise ValueError("Demo accounts are read-only and cannot sell investments.")

            inv = db.query(Investment).filter(Investment.account_number == acc_str).first()
            current_grams = float(inv.gold_grams or 0.0) if inv else 0.0
            if current_grams < grams:
                raise ValueError(f"Insufficient digital gold holdings. Available: {current_grams:.4f}g, requested: {grams:.4f}g.")

        gold_rate = float(FinancialPolicy.get_gold_rate_rupees())
        amount = round(grams * gold_rate, 2)

        txn = ledger_service.execute(
            transaction_type="DIGITAL_GOLD_SALE",
            amount_rupees=amount,
            source_account=GL_GOLD_VAULT_CLEARING,
            destination_account=acc_str,
            description=f"24K Digital Gold Sale ({grams:.4f}g @ ₹{gold_rate:,.2f}/g)",
            idempotency_key=idempotency_key,
            actor=actor,
            ip=ip,
            metadata={"grams": grams, "rate": gold_rate}
        )

        with get_db() as db:
            inv = db.query(Investment).filter(Investment.account_number == acc_str).first()
            if inv:
                old_grams = float(inv.gold_grams)
                inv.gold_grams = max(0.0, old_grams - grams)
                if old_grams > 0:
                    fraction = min(1.0, grams / old_grams)
                    inv.gold_total_invested_paise = max(0, int(inv.gold_total_invested_paise * (1.0 - fraction)))
                db.commit()

        return {"txn": txn, "grams": grams, "rate": gold_rate, "amount": amount}

    def update_sip_status(self, account_number: str, sip_id: str, action: str) -> Dict[str, Any]:
        """Update status of a SIP (pause, resume, cancel/redeem)."""
        acc_str = str(account_number).strip()
        action_map = {
            "pause": "Paused",
            "resume": "Active",
            "cancel": "Redeemed",
            "redeem": "Redeemed",
        }
        target_status = action_map.get(str(action).lower())
        if not target_status:
            raise ValueError(f"Invalid SIP action '{action}'. Permitted actions: pause, resume, cancel.")

        with get_db() as db:
            sip = db.query(SIP).filter(SIP.sip_id == sip_id).first()
            if not sip:
                raise ValueError(f"SIP with ID '{sip_id}' not found.")
            if sip.account_number != acc_str:
                raise PermissionError("Access denied: You do not own this SIP.")

            sip.status = target_status
            db.commit()
            return {"sip_id": sip_id, "status": target_status}

    def create_sip(self, account_number: str, fund_id: str, fund_name: str, category: str,
                   monthly_amount: float, sip_day: int, actor: str, ip: str,
                   idempotency_key: Optional[str] = None) -> Dict[str, Any]:
        """Create new monthly SIP plan."""
        acc_str = str(account_number).strip()
        with get_db() as db:
            acc = account_repository.get_by_number(db, acc_str)
            if acc and acc.user and acc.user.role == "demo":
                raise ValueError("Demo accounts are read-only and cannot establish SIP investments.")

        txn = ledger_service.execute(
            transaction_type="SIP_INSTALLMENT",
            amount_rupees=monthly_amount,
            source_account=acc_str,
            destination_account=GL_INVESTMENT_ESCROW,
            description=f"Mutual Fund Monthly SIP - {fund_name}",
            idempotency_key=idempotency_key,
            actor=actor,
            ip=ip,
            metadata={"fund_id": fund_id, "fund_name": fund_name}
        )

        with get_db() as db:
            sip_id = f"SIP-{random_digits(4)}"
            amt_paise = rupees_to_paise(monthly_amount)
            nav = 104.20
            units = round(monthly_amount / nav, 3)
            today = datetime.date.today()
            next_month = (today + datetime.timedelta(days=30)).strftime("%d/%m/%Y")

            sip = SIP(
                sip_id=sip_id,
                account_number=acc_str,
                fund_id=fund_id,
                fund_name=fund_name,
                category=category,
                investment_type="Monthly SIP",
                monthly_amount_paise=amt_paise,
                sip_day=sip_day,
                invested_amount_paise=amt_paise,
                current_value_paise=amt_paise,
                units=units,
                nav=nav,
                status="Active",
                start_date=today.strftime("%d/%m/%Y"),
                next_date=next_month
            )
            db.add(sip)
            db.commit()

        return {"txn": txn, "sip_id": sip_id}

    def get_investment_performance(self, account_number: str) -> Dict[str, Any]:
        """Generate consolidated investment portfolio valuation and asset class performance."""
        acc_str = str(account_number).strip()
        LIVE_GOLD_RATE_PER_G = 7250.0  # ₹7,250.00 / gram

        with get_db() as db:
            inv = db.query(Investment).filter(Investment.account_number == acc_str).first()
            sips = db.query(SIP).filter(SIP.account_number == acc_str, SIP.status == "Active").all()
            fds = db.query(FixedDeposit).filter(FixedDeposit.account_number == acc_str, FixedDeposit.status == "ACTIVE").all()
            rds = db.query(RecurringDeposit).filter(RecurringDeposit.account_number == acc_str, RecurringDeposit.status == "Active").all()
            ipos = db.query(IPOApplication).filter(IPOApplication.account_number == acc_str).all()

            # 1. Gold Performance
            gold_grams = float(inv.gold_grams or 0.0) if inv else 0.0
            gold_invested_rupees = float(inv.gold_total_invested_paise or 0) / 100.0 if inv else 0.0
            gold_current_val = gold_grams * LIVE_GOLD_RATE_PER_G
            gold_pnl = gold_current_val - gold_invested_rupees
            gold_pnl_pct = (gold_pnl / gold_invested_rupees * 100.0) if gold_invested_rupees > 0 else 0.0

            # 2. Mutual Fund SIPs
            sip_invested = sum(s.invested_amount_paise for s in sips) / 100.0
            sip_current = sum(s.current_value_paise for s in sips) / 100.0
            sip_pnl = sip_current - sip_invested
            sip_pnl_pct = (sip_pnl / sip_invested * 100.0) if sip_invested > 0 else 0.0

            # 3. Fixed Deposits
            fd_principal = sum(f.principal_amount_paise for f in fds) / 100.0
            fd_maturity = sum(f.maturity_amount_paise for f in fds) / 100.0
            fd_interest_accrued = fd_maturity - fd_principal

            # 4. Recurring Deposits
            rd_deposited = sum(r.total_deposited_paise for r in rds) / 100.0
            rd_maturity = sum(r.maturity_amount_paise for r in rds) / 100.0

            # 5. IPO ASBA Blocked
            ipo_blocked = sum(i.amount_blocked_paise for i in ipos if "Submitted" in i.status or "Allotted" in i.status) / 100.0

            # Total Portfolio
            total_invested = gold_invested_rupees + sip_invested + fd_principal + rd_deposited + ipo_blocked
            total_current_value = gold_current_val + sip_current + fd_maturity + rd_maturity + ipo_blocked
            total_pnl = total_current_value - total_invested
            total_pnl_pct = (total_pnl / total_invested * 100.0) if total_invested > 0 else 0.0

            # Allocation percentages
            allocations = []
            if total_current_value > 0:
                allocations = [
                    {"asset_class": "Digital Gold (24K)", "value_rupees": round(gold_current_val, 2), "percentage": round(gold_current_val / total_current_value * 100, 1)},
                    {"asset_class": "Mutual Funds (Equity)", "value_rupees": round(sip_current, 2), "percentage": round(sip_current / total_current_value * 100, 1)},
                    {"asset_class": "Fixed Deposits (FD)", "value_rupees": round(fd_maturity, 2), "percentage": round(fd_maturity / total_current_value * 100, 1)},
                    {"asset_class": "Recurring Deposits (RD)", "value_rupees": round(rd_maturity, 2), "percentage": round(rd_maturity / total_current_value * 100, 1)},
                    {"asset_class": "IPO Applications", "value_rupees": round(ipo_blocked, 2), "percentage": round(ipo_blocked / total_current_value * 100, 1)}
                ]

            return {
                "success": True,
                "summary": {
                    "total_invested_rupees": round(total_invested, 2),
                    "total_current_value_rupees": round(total_current_value, 2),
                    "total_pnl_rupees": round(total_pnl, 2),
                    "total_return_pct": round(total_pnl_pct, 2)
                },
                "gold": {
                    "grams_held": round(gold_grams, 4),
                    "invested_rupees": round(gold_invested_rupees, 2),
                    "current_valuation_rupees": round(gold_current_val, 2),
                    "live_rate_per_gram": LIVE_GOLD_RATE_PER_G,
                    "unrealized_pnl_rupees": round(gold_pnl, 2),
                    "pnl_pct": round(gold_pnl_pct, 2)
                },
                "mutual_funds": {
                    "active_sips_count": len(sips),
                    "invested_rupees": round(sip_invested, 2),
                    "current_valuation_rupees": round(sip_current, 2),
                    "unrealized_pnl_rupees": round(sip_pnl, 2),
                    "pnl_pct": round(sip_pnl_pct, 2)
                },
                "fixed_income": {
                    "active_fds_count": len(fds),
                    "fd_principal_rupees": round(fd_principal, 2),
                    "fd_maturity_rupees": round(fd_maturity, 2),
                    "fd_accrued_interest_rupees": round(fd_interest_accrued, 2),
                    "active_rds_count": len(rds),
                    "rd_deposited_rupees": round(rd_deposited, 2),
                    "rd_maturity_rupees": round(rd_maturity, 2)
                },
                "asset_allocation": allocations
            }


def random_digits(n: int) -> str:
    import random
    return "".join(str(random.randint(0, 9)) for _ in range(n))


investment_service = InvestmentService()
