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
from urllib.parse import urlparse
from sqlalchemy import create_engine, event, text
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
IS_TESTING = (FLASK_ENV == "testing")
RAW_DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

PROD_MARKERS = ["prod", "production", "live", "rds.amazonaws.com", "neon.tech", "supabase.co"]


DEFAULT_TEST_PG_HOST_ALLOWLIST = {
    "localhost",
    "127.0.0.1",
    "::1",
    "postgres-test",
    "pg-test",
    "test-postgres",
    "test-db",
    "db-test",
    "test-pg",
    "ci-postgres",
    "host.docker.internal",
}


def get_test_pg_host_allowlist() -> set:
    """Retrieve the set of explicitly approved PostgreSQL test hostnames/IPs."""
    allowed = set(DEFAULT_TEST_PG_HOST_ALLOWLIST)
    custom = os.environ.get("TEST_PG_HOST_ALLOWLIST", "") or os.environ.get("ALLOWED_TEST_PG_HOSTS", "")
    if custom:
        for h in custom.split(","):
            cleaned = h.strip().lower()
            if cleaned:
                allowed.add(cleaned)
    return allowed


def normalize_database_url(url: str) -> str:
    """
    Deterministically normalize database connection URLs for safe comparison:
    - Strips authentication credentials
    - Canonicalizes scheme (e.g., postgres:// and postgresql+psycopg2:// -> postgresql://)
    - Resolves realpaths and lowercases paths for SQLite
    - Lowercases hostnames and applies default ports (5432 for PostgreSQL)
    - Strips trailing slashes and sorts query parameters
    """
    if not url or not str(url).strip():
        return ""
    url_str = str(url).strip()

    # SQLite normalization
    if url_str.lower().startswith("sqlite"):
        raw_path = url_str.split(":///")[-1] if ":///" in url_str else url_str.replace("sqlite://", "", 1)
        clean_path = raw_path.split("?")[0].strip()
        if clean_path in ("", ":memory:"):
            return "sqlite:///:memory:"
        abs_norm = os.path.realpath(os.path.abspath(clean_path)).replace("\\", "/").lower()
        return f"sqlite:///{abs_norm}"

    # PostgreSQL / other schemes normalization
    try:
        parsed = urlparse(url_str)
        scheme = parsed.scheme.lower()
        if scheme in ("postgres", "postgresql", "postgresql+psycopg2"):
            scheme = "postgresql"
        hostname = (parsed.hostname or "").lower()
        try:
            port = parsed.port or 5432
        except ValueError as pe:
            raise RuntimeError(f"FATAL: Invalid database port: {pe}") from pe
        path = (parsed.path or "").rstrip("/").lower()
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"FATAL: Malformed database URL: {e}") from e

    query = ""
    if parsed.query:
        import urllib.parse
        q_params = urllib.parse.parse_qsl(parsed.query)
        q_params.sort(key=lambda x: x[0])
        query = "?" + urllib.parse.urlencode(q_params)

    return f"{scheme}://{hostname}:{port}{path}{query}"


def validate_test_database_safety(url: str, raw_database_url: str = None):
    """
    Fail-closed validation:
    1. Reject if FLASK_ENV is production (fail-closed environment identity check).
    2. Normalize URLs before comparing TEST_DATABASE_URL and DATABASE_URL; reject if equal.
    3. Reject connecting to production databases or databases with prod markers in test mode.
    4. For PostgreSQL: validate host against explicit allowlist, validate port, and require 'test' in DB name.
    5. Reject unapproved PostgreSQL hosts, even if their database name contains 'test'.
    6. For SQLite: resolve absolute paths and check symlinks against persistent application databases.
    7. Fail-closed behavior on every validation failure.
    """
    if not url or not str(url).strip():
        raise RuntimeError("FATAL: Empty or invalid test database URL provided!")

    flask_env = os.environ.get("FLASK_ENV", "").lower()
    if flask_env == "production":
        raise RuntimeError("FATAL: Test database validation cannot run in production environment (FLASK_ENV=production)!")

    url_str = str(url).strip()
    url_lower = url_str.lower()
    comp_raw = (raw_database_url if raw_database_url is not None else os.environ.get("DATABASE_URL", "")).strip()

    # Rule 1: Normalized URL comparison - reject if TEST_DATABASE_URL matches production/application DATABASE_URL
    norm_test = normalize_database_url(url_str)
    if raw_database_url is not None:
        norm_raw = normalize_database_url(raw_database_url)
        if norm_test and norm_raw and norm_test == norm_raw:
            raise RuntimeError(
                f"FATAL: TEST_DATABASE_URL cannot match production/application DATABASE_URL ({mask_database_url(raw_database_url)})!"
            )
    else:
        comp_raw = os.environ.get("DATABASE_URL", "").strip()
        if comp_raw:
            norm_raw = normalize_database_url(comp_raw)
            if norm_test and norm_raw and norm_test == norm_raw:
                # If comp_raw is a persistent or non-test database, reject test URL matching it
                parsed_comp = urlparse(comp_raw)
                db_name = (parsed_comp.path or "").lstrip("/").lower()
                is_isolated_test_db = ("test" in db_name and "credence_core.db" not in comp_raw.lower())
                if not is_isolated_test_db:
                    raise RuntimeError(
                        f"FATAL: TEST_DATABASE_URL cannot match production/application DATABASE_URL ({mask_database_url(comp_raw)})!"
                    )

    # Rule 2: Production keywords / host markers
    if any(m in url_lower for m in PROD_MARKERS):
        raise RuntimeError(f"FATAL: Production database URL rejected in test mode! URL contains restricted marker: {url_str}")

    # Rule 3: Scheme-specific isolation and security validation
    scheme_norm = url_lower.split("://")[0] if "://" in url_lower else ""

    if scheme_norm.startswith("sqlite"):
        raw_path = url_str.split(":///")[-1] if ":///" in url_str else url_str.replace("sqlite://", "", 1)
        clean_path = raw_path.split("?")[0].strip()
        if clean_path in ("", ":memory:"):
            return

        abs_clean = os.path.abspath(clean_path)
        real_test_path = os.path.realpath(abs_clean).lower()
        base_dir = os.path.realpath(os.path.dirname(os.path.abspath(__file__))).lower()
        persistent_db_path = os.path.realpath(os.path.join(base_dir, "credence_core.db")).lower()

        # Symlink check: verify symlink target does not point to persistent application database
        if os.path.islink(clean_path):
            target = os.path.realpath(clean_path).lower()
            if target == persistent_db_path or "credence_core.db" in target or "credence_backup.db" in target:
                raise RuntimeError(
                    f"FATAL: SQLite test database symlink points to persistent application database ({clean_path} -> {target})!"
                )

        if real_test_path == persistent_db_path or os.path.basename(real_test_path) in (
            "credence_core.db", "credence_core.sqlite", "credence_backup.db", "credence_core.db.pre_restore_bak"
        ):
            raise RuntimeError(
                f"FATAL: Test database URL points to persistent application database ({clean_path})! "
                "Tests must execute only on disposable temporary databases."
            )
    elif scheme_norm.startswith("postgres"):
        parsed = urlparse(url_str)
        db_name = (parsed.path or "").lstrip("/").lower()
        hostname = (parsed.hostname or "").lower()
        try:
            port = parsed.port
        except ValueError as pe:
            raise RuntimeError(f"FATAL: Invalid database port: {pe}") from pe

        if not hostname:
            raise RuntimeError(f"FATAL: PostgreSQL test database URL is missing a hostname: {mask_database_url(url_str)}")

        if any(m in hostname for m in PROD_MARKERS):
            raise RuntimeError(f"FATAL: Production database host rejected in test mode: {hostname}")

        # Rule 4 & 5: Validate host against explicit test host allowlist
        allowed_hosts = get_test_pg_host_allowlist()
        if hostname not in allowed_hosts:
            raise RuntimeError(
                f"FATAL: Unapproved test PostgreSQL host '{hostname}' rejected! "
                f"Test database host must be explicitly allowlisted in TEST_PG_HOST_ALLOWLIST: {sorted(list(allowed_hosts))}. "
                "A database name containing 'test' is not sufficient without an approved isolated test host."
            )

        if port is not None:
            try:
                port_num = int(port)
                if not (1 <= port_num <= 65535):
                    raise ValueError()
            except ValueError:
                raise RuntimeError(f"FATAL: Invalid database port: {port}")

        # Rule 6: Validate database name explicitly contains 'test'
        if not db_name or "test" not in db_name:
            raise RuntimeError(
                f"FATAL: Test PostgreSQL database name '{db_name}' is not isolated! "
                "Test database name must explicitly contain 'test' (e.g., 'credence_core_test') to guarantee isolation."
            )
    else:
        raise RuntimeError(f"FATAL: Unsupported database scheme for testing: {scheme_norm}")


if IS_TESTING:
    test_url = os.environ.get("TEST_DATABASE_URL", "").strip()
    if not test_url:
        raw_env_url = RAW_DATABASE_URL.strip()
        if raw_env_url and "postgres" in raw_env_url.lower() and "test" in raw_env_url.lower():
            test_url = raw_env_url
        else:
            import tempfile
            temp_db = os.path.join(tempfile.gettempdir(), f"credence_test_isolated_{os.getpid()}.db")
            test_url = f"sqlite:///{temp_db.replace(os.sep, '/')}"
    validate_test_database_safety(test_url)
    DATABASE_URL = test_url
elif RAW_DATABASE_URL.startswith("postgres://"):
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


def _register_sqlite_pragmas(eng):
    @event.listens_for(eng, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.execute("PRAGMA journal_mode = WAL;")
        cursor.execute("PRAGMA busy_timeout = 5000;")
        cursor.close()


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
    if not IS_POSTGRES:
        _register_sqlite_pragmas(engine)
    # Immediately validate connection
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    logger.info(f"Connected to database successfully at {mask_database_url(DATABASE_URL)}.")
except Exception as e:
    masked_url = mask_database_url(DATABASE_URL)
    if IS_TESTING:
        raise RuntimeError(
            f"FATAL: Database connection failed in testing mode ({masked_url}): {e}. "
            "In testing mode (FLASK_ENV=testing), database connection failures must raise a fatal error. "
            "Automatic fallback to credence_core.db or any normal application database is strictly forbidden."
        ) from e
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
    _register_sqlite_pragmas(engine)

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
                ("last_totp_step", "BIGINT DEFAULT 0"),
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


def configure_engine(new_url: str):
    """Dynamically rebind engine and session factory to an isolated database URL."""
    global engine, DATABASE_URL, IS_POSTGRES
    if os.environ.get("FLASK_ENV", "").lower() == "testing":
        validate_test_database_safety(new_url)
    DATABASE_URL = new_url
    IS_POSTGRES = DATABASE_URL.startswith("postgresql")
    kwargs = {"echo": False}
    if IS_POSTGRES:
        kwargs.update({
            "poolclass": QueuePool,
            "pool_size": 10,
            "max_overflow": 20,
            "pool_timeout": 30,
            "pool_recycle": 1800,
            "pool_pre_ping": True,
            "isolation_level": "READ COMMITTED"
        })
    else:
        kwargs.update({
            "connect_args": {"check_same_thread": False, "timeout": 30.0}
        })
    engine = create_engine(DATABASE_URL, **kwargs)
    if not IS_POSTGRES:
        _register_sqlite_pragmas(engine)
    if os.environ.get("FLASK_ENV", "").lower() == "testing":
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception as e:
            raise RuntimeError(
                f"FATAL: Database connection failed in testing mode ({mask_database_url(new_url)}): {e}. "
                "Fallback is strictly forbidden."
            ) from e
    SessionFactory.configure(bind=engine)
    SessionLocal.remove()
    return engine
