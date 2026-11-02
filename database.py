"""
Credence Core — Database Engine & Connection Management
Supports PostgreSQL with connection pooling and transaction isolation,
with strictly controlled fallback for local development only.
"""

import os
import re
import logging
import threading
from contextlib import contextmanager
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session
from sqlalchemy.pool import QueuePool, StaticPool

logger = logging.getLogger("credence.database")


def mask_database_url(url: str) -> str:
    """Mask sensitive username:password in database URLs for safe logging."""
    if not url:
        return ""
    return re.sub(r"://([^:@/]+):([^@/]+)@", r"://\1:***@", url)


# Environment configuration
FLASK_ENV = os.environ.get("FLASK_ENV", "development").lower()
IS_PRODUCTION = (FLASK_ENV == "production")
RAW_DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

# Normalize Heroku/Render postgres:// to postgresql+psycopg2://
if RAW_DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = RAW_DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)
elif RAW_DATABASE_URL.startswith("postgresql://") and "+psycopg2" not in RAW_DATABASE_URL:
    DATABASE_URL = RAW_DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)
elif RAW_DATABASE_URL:
    DATABASE_URL = RAW_DATABASE_URL
else:
    if IS_PRODUCTION:
        raise RuntimeError(
            "FATAL: In production, DATABASE_URL must be explicitly configured with a PostgreSQL connection string. "
            "Automatic fallback to SQLite is forbidden in production."
        )
    DEFAULT_DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "credence_core.db")
    DATABASE_URL = f"sqlite:///{DEFAULT_DB_FILE}"

IS_POSTGRES = DATABASE_URL.startswith("postgresql")

if IS_PRODUCTION and not IS_POSTGRES:
    raise RuntimeError(
        "FATAL: In production, DATABASE_URL must be a PostgreSQL connection string. "
        "SQLite is not permitted in production."
    )


def get_db_url() -> str:
    return DATABASE_URL


# Create Engine with connection pooling and transaction isolation
engine_kwargs = {"echo": False}

if IS_POSTGRES:
    engine_kwargs.update({
        "poolclass": QueuePool,
        "pool_size": 10,
        "max_overflow": 20,
        "pool_timeout": 30,
        "pool_recycle": 1800,
        "pool_pre_ping": True,
        "isolation_level": "READ COMMITTED"
    })
else:
    # SQLite configuration
    engine_kwargs.update({
        "connect_args": {"check_same_thread": False, "timeout": 30.0}
    })

try:
    engine = create_engine(DATABASE_URL, **engine_kwargs)
    # Validate connection immediately
    if IS_POSTGRES:
        with engine.connect() as conn:
            pass
        logger.info(f"Connected to PostgreSQL database successfully at {mask_database_url(DATABASE_URL)}.")
except Exception as e:
    masked_url = mask_database_url(DATABASE_URL)
    if IS_PRODUCTION:
        raise RuntimeError(
            f"FATAL: Could not connect to configured production database ({masked_url}): {e}. "
            "Production startup aborted. Automatic fallback to SQLite is forbidden."
        ) from e
    logger.warning(f"Could not connect to {masked_url}: {e}. Falling back to SQLite for local development.")
    DEFAULT_DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "credence_core.db")
    DATABASE_URL = f"sqlite:///{DEFAULT_DB_FILE}"
    IS_POSTGRES = False
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False, "timeout": 30.0})

# Enforce foreign key constraints and WAL mode on SQLite
if not IS_POSTGRES:
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.execute("PRAGMA journal_mode = WAL;")
        cursor.execute("PRAGMA busy_timeout = 5000;")
        cursor.close()

# Session Factory
SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
SessionLocal = scoped_session(SessionFactory)

# Declarative Base for models
Base = declarative_base()


_session_depth = threading.local()


@contextmanager
def get_db():
    """
    Transactional database session context manager.
    Supports nested calls safely: only commits and closes at the outermost level.
    """
    if not hasattr(_session_depth, "depth"):
        _session_depth.depth = 0

    session = SessionLocal()
    _session_depth.depth += 1
    try:
        yield session
        if _session_depth.depth == 1:
            session.commit()
        else:
            session.flush()
    except Exception:
        session.rollback()
        raise
    finally:
        _session_depth.depth -= 1
        if _session_depth.depth == 0:
            SessionLocal.remove()


def get_db_session():
    """Direct session generator for Flask request dependencies."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables defined in models if not yet existing and ensure column migrations."""
    from models import Base
    Base.metadata.create_all(bind=engine)

    # Ensure newly added columns exist in existing database schemas
    from sqlalchemy import inspect, text
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    with engine.connect() as conn:
        if "transactions" in tables:
            txn_cols = {c["name"] for c in inspector.get_columns("transactions")}
            if "payload_hash" not in txn_cols:
                try:
                    conn.execute(text("ALTER TABLE transactions ADD COLUMN payload_hash VARCHAR(64)"))
                    conn.commit()
                except Exception:
                    pass

        if "users" in tables:
            user_cols = {c["name"] for c in inspector.get_columns("users")}
            user_additions = [
                ("mfa_enabled", "BOOLEAN DEFAULT 0"),
                ("mfa_secret", "VARCHAR(255)"),
                ("mfa_recovery_codes", "TEXT"),
                ("mfa_enrolled_at", "DATETIME"),
            ]
            for col_name, col_def in user_additions:
                if col_name not in user_cols:
                    try:
                        conn.execute(text(f"ALTER TABLE users ADD COLUMN {col_name} {col_def}"))
                        conn.commit()
                    except Exception:
                        pass

        if "sessions" in tables:
            sess_cols = {c["name"] for c in inspector.get_columns("sessions")}
            sess_additions = [
                ("session_token_hash", "VARCHAR(64)"),
                ("role", "VARCHAR(20) DEFAULT 'user'"),
                ("is_demo", "BOOLEAN DEFAULT 0"),
                ("csrf_token", "VARCHAR(128)"),
                ("last_active_at", "DATETIME"),
            ]
            for col_name, col_def in sess_additions:
                if col_name not in sess_cols:
                    try:
                        conn.execute(text(f"ALTER TABLE sessions ADD COLUMN {col_name} {col_def}"))
                        conn.commit()
                    except Exception:
                        pass


def drop_db():
    """Drop all tables defined in models (for testing/reset)."""
    from models import Base
    Base.metadata.drop_all(bind=engine)
