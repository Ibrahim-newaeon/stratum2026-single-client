# =============================================================================
# Stratum AI - Database Session Management
# =============================================================================
"""
Async and sync database session management with connection pooling.
Implements proper context management for multi-tenant queries.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# =============================================================================
# Async Engine (Primary - for FastAPI)
# =============================================================================
async_engine = create_async_engine(
    settings.database_url,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_recycle=settings.db_pool_recycle,
    pool_timeout=settings.db_pool_timeout,
    pool_pre_ping=True,
    echo=settings.debug and settings.is_development,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# =============================================================================
# Sync Engine (For Celery workers and migrations)
# =============================================================================
sync_engine = create_engine(
    settings.database_url_sync,
    poolclass=QueuePool,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_recycle=settings.db_pool_recycle,
    pool_timeout=settings.db_pool_timeout,
    pool_pre_ping=True,
    echo=settings.debug and settings.is_development,
)

SyncSessionLocal = sessionmaker(
    bind=sync_engine,
    autocommit=False,
    autoflush=False,
)


# =============================================================================
# Connection Event Listeners for Row-Level Security
# =============================================================================
@event.listens_for(sync_engine, "connect")
def set_search_path_sync(dbapi_connection, connection_record):
    """Set search path for sync connections."""
    cursor = dbapi_connection.cursor()
    cursor.execute("SET search_path TO public")
    cursor.close()


# =============================================================================
# Dependency Injection Generators
# =============================================================================
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for async database sessions.

    Does NOT auto-commit. Rolls back on exception, closes on completion.
    Any handler (or service it calls) that mutates the database MUST call
    ``await session.commit()`` before returning, or the writes are silently
    discarded when the session closes. ``flush()`` alone is not durable.

    Usage:
        @router.get("/items")
        async def get_items(db: AsyncSession = Depends(get_async_session)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def get_sync_session() -> Generator[Session, None, None]:
    """
    Dependency for sync database sessions (Celery workers).

    Usage:
        with get_sync_session() as session:
            ...
    """
    session = SyncSessionLocal()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@asynccontextmanager
async def async_session_context() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for async sessions outside of FastAPI.

    Usage:
        async with async_session_context() as session:
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


# =============================================================================
# Event-Loop Hygiene for Celery Tasks
# =============================================================================
async def dispose_stale_async_pool() -> None:
    """Discard DB connections pooled under a previous task's event loop.

    Celery tasks enter a fresh event loop via ``asyncio.run()``, but the
    module-level async engine keeps pooled asyncpg connections bound to
    the loop that created them. The second task to run in the same worker
    process then fails with ``RuntimeError: ... got Future attached to a
    different loop``. Call this at the START of every task coroutine that
    uses the async engine. ``close=False`` discards the stale connections
    without awaiting their close across loops.
    """
    await async_engine.dispose(close=False)


# =============================================================================
# Health Check
# =============================================================================
async def check_database_health() -> dict:
    """Check database connectivity and return health status."""
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
            return {"status": "healthy", "database": "connected"}
    except (ConnectionError, TimeoutError, OSError, Exception) as e:
        # Catch SQLAlchemy OperationalError, InterfaceError, and other DB errors
        logger.error(
            "database_health_check_failed", error=str(e), error_type=type(e).__name__
        )
        return {"status": "unhealthy", "database": "disconnected", "error": str(e)}


# =============================================================================
# Legacy Alias
# =============================================================================
# Several task modules import this name. It is an alias for AsyncSessionLocal
# used as an async context manager (matching the interface of async_session_context).
async_session_factory = async_session_context

# Legacy alias used by worker modules (e.g. crm_sync_tasks)
async_session_maker = async_session_context

# Alias for embed_widgets and other modules that import get_db
get_db = get_async_session

# Legacy alias used by Celery worker modules (e.g. campaign_builder_tasks)
SessionLocal = SyncSessionLocal
