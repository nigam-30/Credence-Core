"""
Credence Core — Application Factory
Initializes modular Flask application, database bindings, security middleware, and routes.
"""

__version__ = "1.0.0"

import os
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix
from backend.app.core.config import get_config, ProductionConfig
from backend.app.core.database import init_db
from backend.app.middleware import apply_security_headers, register_error_handlers
from backend.app.middleware.metrics_middleware import register_metrics_middleware
from backend.app.api import register_blueprints


def create_app(config_class=None) -> Flask:
    """Construct and configure the Flask application instance."""
    resolved_config = config_class or get_config()
    app = Flask(__name__)
    app.config.from_object(resolved_config)

    # In production, enforce secret validation
    if app.config.get("FLASK_ENV") == "production":
        ProductionConfig.validate_secrets()

    # Configure trusted reverse proxy headers (X-Forwarded-For, X-Forwarded-Proto, etc.)
    trusted_proxies = os.environ.get("TRUSTED_PROXIES", "1")
    if trusted_proxies != "0" or app.config.get("FLASK_ENV") == "production":
        proxy_count = int(os.environ.get("TRUSTED_PROXIES_COUNT", "1"))
        app.wsgi_app = ProxyFix(
            app.wsgi_app,
            x_for=proxy_count,
            x_proto=proxy_count,
            x_host=proxy_count,
            x_prefix=proxy_count
        )

    # Initialize database tables
    try:
        init_db()
    except Exception as e:
        if app.config.get("FLASK_ENV") == "production":
            raise RuntimeError(f"FATAL: Production database initialization failed: {e}") from e
        app.logger.warning(f"Database table initialization notice: {e}")

    # Register centralized error handlers & metrics middleware
    register_error_handlers(app)
    register_metrics_middleware(app)

    # Register response middleware (security headers, CSP, CORS)
    app.after_request(apply_security_headers)

    # Register all modular route Blueprints
    register_blueprints(app)

    return app
