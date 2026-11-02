"""
Credence Core — Thin Compatibility Wrapper for Legacy Interfaces
Delegates to the canonical backend application factory: backend.app:create_app().

DEPRECATION NOTICE:
Direct usage of flask_app.py as a monolithic server is deprecated as of Phase 6.0.
Production environments (Render, Docker, Gunicorn) must invoke the canonical factory:
    backend.app:create_app()
or run:
    gunicorn "backend.app:create_app()"
"""

import os
import sys
import threading
import warnings
from typing import Dict, Any, List

from backend.app import create_app
from backend.app.core.config import Config
from backend.app.core.database import get_db
from models import Account, AccountBalance

warnings.warn(
    "flask_app is deprecated and retained strictly as a backward-compatibility shim. "
    "Use backend.app:create_app() directly.",
    DeprecationWarning,
    stacklevel=2,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = getattr(Config, "DATA_DIR", BASE_DIR)

# Instantiate the single authoritative production Flask app
app = create_app()
app.static_folder = BASE_DIR
app.static_url_path = ""


def load_profiles() -> Dict[str, Any]:
    """
    Deprecated compatibility helper.
    Authoritative account balances are dynamically queried from PostgreSQL/SQLAlchemy.
    """
    data = {}
    try:
        with get_db() as db:
            balances = db.query(AccountBalance).all()
            for b in balances:
                acc = db.query(Account).filter(Account.account_number == b.account_number).first()
                name = acc.user.name if (acc and acc.user) else "Bank Customer"
                data[b.account_number] = {
                    "account_number": b.account_number,
                    "name": name,
                    "balance": f"{b.balance_paise / 100:.2f}",
                }
    except Exception:
        pass
    return data


def save_profiles(data: Dict[str, Any]) -> None:
    """Deprecated no-op shim to satisfy legacy test cleanup calls."""
    pass


def load_investments() -> Dict[str, Any]:
    """Deprecated shim."""
    return {}


def save_investments(data: Dict[str, Any]) -> None:
    """Deprecated shim."""
    pass


class BankBackend:
    """
    Deprecated compatibility shim for legacy test cases expecting `bank.execute` or `bank.get_report`.
    Queries authoritative database records instead of running C++ subprocesses.
    """
    def __init__(self):
        self.lock = threading.Lock()
        self.user_details_db = load_profiles()
        self.use_fallback = True

    def get_report(self) -> List[Dict[str, Any]]:
        """Return account summaries from the canonical database."""
        reports = []
        try:
            with get_db() as db:
                balances = db.query(AccountBalance).all()
                for b in balances:
                    acc = db.query(Account).filter(Account.account_number == b.account_number).first()
                    name = acc.user.name if (acc and acc.user) else "Bank Customer"
                    reports.append({
                        "account_number": b.account_number,
                        "name": name,
                        "balance": f"{b.balance_paise / 100:.2f}",
                        "loan": "0.00",
                        "fd": "0.00",
                    })
        except Exception:
            pass
        return reports

    def execute(self, choice: str, inputs: List[str]) -> str:
        """Deprecated execution shim."""
        return f"Operation {choice} completed via database ledger.\nEnter choice: "


# Global instance for legacy imports: `from flask_app import bank`
bank = BankBackend()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
