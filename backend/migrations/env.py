# =============================================================================
# Stratum AI - Alembic Migration Environment
# =============================================================================
"""
Alembic environment configuration for database migrations.
Uses synchronous migrations for simplicity and reliability.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool, create_engine
from sqlalchemy.engine import Connection

from app.core.config import settings
from app.db.base import Base, StrEnumType
from app.db.types import EncryptedString
from app.models import *  # noqa: F401, F403 - Import all models for metadata

# Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set target metadata for autogenerate
target_metadata = Base.metadata


def get_url() -> str:
    """Get database URL from settings."""
    return settings.database_url_sync


def render_item(type_, obj, autogen_context):
    """Autogenerate renderer for the custom ``StrEnumType`` column type.

    Two problems, one fix:

    1. Alembic's default renderer only knows how to reconstruct a column
       type from its ``__init__`` kwargs; ``StrEnumType`` takes a
       *positional* Python enum class (``enum_class``) plus a derived
       ``_pg_enum_name``, neither of which the default renderer can
       discover. Left alone, autogenerate emits
       ``app.db.base.StrEnumType(length=50)`` — missing the required
       ``enum_class`` arg — a SyntaxError-free but TypeError-at-runtime
       migration.
    2. ``StrEnumType.impl`` is ``String(50)`` (a plain VARCHAR) — DDL
       generated straight from the Python type would create a VARCHAR
       column. But ``StrEnumType.bind_expression()`` unconditionally CASTs
       every bound parameter to a *native* Postgres enum type
       (``create_type=False`` — it assumes that type already exists and
       matches the column). A VARCHAR column compared/inserted against
       that CAST fails at runtime with "operator does not exist:
       character varying = <enum_name>" for every query that filters on
       the column, not just inserts (verified against a live DB). The
       pre-conversion Alembic chain always created these columns as
       genuine ``postgresql.ENUM`` types by hand for exactly this reason.

    So: render the column's *migration-time* DDL type as a real
    ``postgresql.ENUM`` (auto-creates the native type on
    ``create_table``, matching what ``bind_expression`` expects) rather
    than as ``StrEnumType`` itself — the ORM mapping in the model file
    still uses ``StrEnumType``, unaffected by this; only the generated
    migration's DDL changes.
    """
    if type_ == "type" and isinstance(obj, StrEnumType):
        enum_cls = obj.enum_class
        values = ", ".join(repr(e.value) for e in enum_cls)
        autogen_context.imports.add("from sqlalchemy.dialects import postgresql")
        return f"postgresql.ENUM({values}, name={obj._pg_enum_name!r})"
    if type_ == "type" and isinstance(obj, EncryptedString):
        # impl=String (plain VARCHAR) — no PG-side type mismatch like
        # StrEnumType above, just needs its import registered so the
        # default-rendered ``app.db.types.EncryptedString(length=N)`` call
        # in the generated migration resolves.
        autogen_context.imports.add("import app.db.types")
        return False
    return False


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine,
    though an Engine is acceptable here as well. By skipping the Engine
    creation we don't even need a DBAPI to be available.
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        version_num_width=128,
        render_item=render_item,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations with the given connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        version_num_width=128,
        render_item=render_item,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode using sync engine.
    """
    connectable = create_engine(
        get_url(),
        poolclass=pool.NullPool,
        connect_args={"connect_timeout": 10},
    )

    with connectable.connect() as connection:
        do_run_migrations(connection)

    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
