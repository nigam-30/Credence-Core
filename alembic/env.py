import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Add repository root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import engine as app_engine, get_db_url, validate_test_database_safety
from models import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Set sqlalchemy.url dynamically from database module if not already configured
if not config.get_main_option("sqlalchemy.url"):
    config.set_main_option("sqlalchemy.url", get_db_url())

if os.environ.get("FLASK_ENV", "").lower() == "testing":
    validate_test_database_safety(config.get_main_option("sqlalchemy.url"))


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    if os.environ.get("FLASK_ENV", "").lower() == "testing":
        validate_test_database_safety(url)
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connection = config.attributes.get("connection", None)
    if connection is not None:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True if connection.dialect.name == "sqlite" else False,
        )
        with context.begin_transaction():
            context.run_migrations()
        return

    url = config.get_main_option("sqlalchemy.url")
    if os.environ.get("FLASK_ENV", "").lower() == "testing":
        validate_test_database_safety(url)
        if url and url != get_db_url():
            from sqlalchemy import create_engine
            connectable = create_engine(url)
        else:
            connectable = app_engine
    elif url and url != get_db_url():
        from sqlalchemy import create_engine
        connectable = create_engine(url)
    else:
        connectable = app_engine

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True if connection.dialect.name == "sqlite" else False,
        )

        with context.begin_transaction():
            context.run_migrations()



if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
