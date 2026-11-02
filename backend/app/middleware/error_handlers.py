"""
Credence Core — Centralized Exception & Error Handling
Standardizes error JSON structures and prevents sensitive stack traces from leaking to clients.
"""

from flask import Flask, jsonify, request
from backend.app.schemas.validators import ValidationError
from backend.app.utils.currency import InvalidAmountError
from backend.app.core.logging import security_logger, log_error_event
import ledger


def register_error_handlers(app: Flask):
    """Register centralized error handlers on Flask application."""

    @app.errorhandler(ValidationError)
    def handle_validation_error(e):
        return jsonify({
            "success": False,
            "error_type": "VALIDATION_ERROR",
            "message": str(e)
        }), 400

    @app.errorhandler(InvalidAmountError)
    def handle_amount_error(e):
        return jsonify({
            "success": False,
            "error_type": "INVALID_AMOUNT",
            "message": str(e)
        }), 400

    @app.errorhandler(ledger.InsufficientFundsError)
    def handle_insufficient_funds(e):
        return jsonify({
            "success": False,
            "error_type": "INSUFFICIENT_FUNDS",
            "message": str(e)
        }), 400

    @app.errorhandler(ledger.LimitExceededError)
    def handle_limit_exceeded(e):
        return jsonify({
            "success": False,
            "error_type": "LIMIT_EXCEEDED",
            "message": str(e)
        }), 400

    @app.errorhandler(ledger.DuplicateTransactionError)
    def handle_duplicate_transaction(e):
        return jsonify({
            "success": False,
            "error_type": "DUPLICATE_TRANSACTION",
            "message": str(e)
        }), 409

    @app.errorhandler(ledger.IdempotencyConflictError)
    def handle_idempotency_conflict(e):
        return jsonify({
            "success": False,
            "error_type": "IDEMPOTENCY_CONFLICT",
            "message": str(e)
        }), 409

    @app.errorhandler(ledger.AccountNotFoundError)
    def handle_account_not_found(e):
        return jsonify({
            "success": False,
            "error_type": "NOT_FOUND",
            "message": str(e)
        }), 404

    @app.errorhandler(400)
    def handle_bad_request(e):
        return jsonify({
            "success": False,
            "error_type": "BAD_REQUEST",
            "message": getattr(e, "description", "Malformed request.")
        }), 400

    @app.errorhandler(403)
    def handle_forbidden(e):
        return jsonify({
            "success": False,
            "error_type": "FORBIDDEN",
            "message": getattr(e, "description", "Access denied: Unauthorized.")
        }), 403

    @app.errorhandler(404)
    def handle_not_found(e):
        if request.path.startswith("/api/"):
            return jsonify({
                "success": False,
                "error_type": "NOT_FOUND",
                "message": "API route not found."
            }), 404
        return "Page not found", 404

    @app.errorhandler(500)
    def handle_internal_error(e):
        security_logger.error(f"Internal server error on {request.path}: {e}", exc_info=True)
        log_error_event("INTERNAL_SERVER_ERROR", str(e), exc=e if isinstance(e, Exception) else None, details={"path": request.path, "method": request.method})
        return jsonify({
            "success": False,
            "error_type": "INTERNAL_SERVER_ERROR",
            "message": "An internal server error occurred. Please contact bank administration."
        }), 500
