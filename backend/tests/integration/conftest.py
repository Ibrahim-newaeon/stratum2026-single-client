# =============================================================================
# Stratum AI - Integration Test Configuration
# =============================================================================
"""
Pytest configuration and fixtures for integration tests.

Provides:
- Database fixtures with async support
- Test organization and user factories
- API client fixtures

NOTE: These tests require a running PostgreSQL database.
Set TEST_DATABASE_URL environment variable or use default test database.

NOTE: Run this suite on a single session-scoped event loop (the FastAPI test
app uses Starlette BaseHTTPMiddleware, which breaks across pytest-asyncio's
default per-test loops). CI passes these flags; locally run with:

    pytest tests/integration -m integration \\
        -o asyncio_default_test_loop_scope=session \\
        -o asyncio_default_fixture_loop_scope=session
"""

import asyncio
import os
from datetime import date, datetime, timezone
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

# Set database URLs for tests
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://stratum:password@localhost:5432/stratum_ai_test",
)
os.environ["DATABASE_URL_SYNC"] = os.environ.get(
    "TEST_DATABASE_URL_SYNC",
    "postgresql://stratum:password@localhost:5432/stratum_ai_test",
)


# =============================================================================
# Async Event Loop Configuration
# =============================================================================


# NOTE: We intentionally do NOT define a custom ``event_loop`` fixture. Under
# pytest-asyncio 1.x that fixture is deprecated and ignored for tests (which run
# on a per-test function loop), while async *fixtures* would still bind to it —
# the split produced "Future attached to a different loop" / "Event loop is
# closed" errors through Starlette's BaseHTTPMiddleware. Letting pytest-asyncio
# own a single consistent loop per test keeps engine, app, and client aligned.


# =============================================================================
# Database Fixtures
# =============================================================================


@pytest.fixture(scope="session")
def sync_engine():
    """Create a sync database engine for setup/teardown."""
    from app.core.config import settings

    engine = create_engine(
        settings.database_url_sync,
        echo=False,
        pool_pre_ping=True,
    )
    yield engine
    engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def async_engine():
    """
    Create an async database engine per test.

    Function-scoped to avoid "Future attached to a different loop" errors
    that occur when a session-scoped engine creates connections on one
    event loop but tests run on another (pytest-asyncio creates a new
    loop per function with asyncio_mode=auto).
    """
    from app.core.config import settings

    engine = create_async_engine(
        settings.database_url,
        echo=False,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=0,
    )
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    """
    Create a database session for each test with savepoint-based rollback.

    Strategy:
    1. Open a real connection + begin an outer transaction.
    2. Start a savepoint (begin_nested) inside that transaction.
    3. Hand the session to both test fixtures and endpoint code.
    4. After each endpoint commit(), the savepoint listener restarts it.
    5. On teardown, roll back the outer transaction → all changes vanish.
    """
    connection = await async_engine.connect()
    transaction = await connection.begin()

    session = AsyncSession(bind=connection, expire_on_commit=False, autoflush=False)

    # Use nested transactions (savepoints) so endpoint commit() doesn't
    # close our outer transaction.
    nested = await connection.begin_nested()

    # After every commit from endpoint code, restart the savepoint
    @event.listens_for(session.sync_session, "after_transaction_end")
    def restart_savepoint(session_inner, trans):
        if trans.nested and not trans._parent.nested:
            session_inner.begin_nested()

    yield session

    # Tear down: rollback everything
    await session.close()
    await transaction.rollback()
    await connection.close()


@pytest.fixture(autouse=True)
def _reset_security_redis_pool():
    """Reset app.core.security's cached Redis pool between tests.

    The module caches its Redis pool on the first event loop that touches it
    (fine in prod — one long-lived loop per worker). Tests may run on fresh
    loops, so a pool cached by an earlier test (e.g. via a login call) would
    raise 'Event loop is closed' in later ones. Drop the cache after each test.
    """
    yield
    import app.core.security as security

    security._redis_pool = None
    security._redis_pool_lock = None


@pytest.fixture(scope="function")
def sync_db_session(sync_engine) -> Generator[Session, None, None]:
    """Create a sync database session for tests that require it."""
    SessionLocal = sessionmaker(bind=sync_engine, autoflush=False)
    session = SessionLocal()

    try:
        yield session
        session.rollback()
    finally:
        session.close()


# =============================================================================
# Application and Client Fixtures
# =============================================================================


@pytest_asyncio.fixture(scope="function")
async def app():
    """
    Build a stripped-down FastAPI app for integration tests.

    The full ``create_application()`` adds middleware (rate-limiter, audit,
    prometheus) that creates async Redis / DB connections at middleware init
    time.  Those connections bind to the *import-time* event loop, which
    differs from the per-test loop created by pytest-asyncio, causing
    "Future attached to a different loop" RuntimeErrors.

    To avoid this, we construct a **lightweight test app** that keeps the
    router & auth-context middleware but drops the problematic I/O
    middleware.

    STRAT-SC-001 (Task C6): ``app.middleware.tenant.TenantMiddleware`` was
    deleted in C2 (replaced by ``AuthContextMiddleware`` — decodes the JWT
    and sets ``request.state.user_id/role/cms_role``; there is no tenant
    context left to extract, since there is exactly one organization).
    """
    from fastapi import FastAPI
    from fastapi.responses import ORJSONResponse

    from app.api.v1 import api_router
    from app.core.config import settings
    from app.middleware.auth_context import AuthContextMiddleware

    application = FastAPI(
        title="Stratum AI (test)",
        default_response_class=ORJSONResponse,
    )

    # Auth-context middleware – enough for JWT decode / role context.
    application.add_middleware(AuthContextMiddleware)

    # Include the full API router (same routes as production)
    application.include_router(api_router, prefix=settings.api_v1_prefix)

    # Minimal health endpoint (some tests may hit /health)
    @application.get("/health")
    async def health():
        return {"status": "healthy"}

    yield application


@pytest_asyncio.fixture(scope="function")
async def client(app, db_session) -> AsyncGenerator[AsyncClient, None]:
    """
    Create an async HTTP client for API testing.

    Overrides the database session dependency.
    """
    from app.db.session import get_async_session

    # Override the database dependency
    async def get_test_session():
        yield db_session

    app.dependency_overrides[get_async_session] = get_test_session

    # STRAT-SC-001: app.tenancy (a get_db wrapper around get_async_session,
    # used by a handful of endpoints e.g. pacing) was deleted wholesale in
    # C2/C3 along with the rest of the tenancy layer. The import is gone too,
    # so there's nothing left to override here — kept as a no-op try/except
    # in case a future endpoint reintroduces a similar db-session wrapper.
    try:
        from app.tenancy.deps import get_db as tenancy_get_db

        app.dependency_overrides[tenancy_get_db] = get_test_session
    except ImportError:  # pragma: no cover - app.tenancy no longer exists
        pass

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac

    # Clear dependency overrides
    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def authenticated_client(client, test_user) -> AsyncClient:
    """
    Create an authenticated client with JWT token.

    STRAT-SC-001: no more tenant claim/header — there is exactly one
    organization, so nothing to disambiguate.
    """
    from app.core.security import create_access_token

    token = create_access_token(
        subject=test_user["id"],
        additional_claims={
            "email": test_user["email"],
            "role": test_user["role"],
        },
    )

    client.headers["Authorization"] = f"Bearer {token}"

    return client


# =============================================================================
# Test Data Factories
# =============================================================================


@pytest_asyncio.fixture(scope="function")
async def organization(db_session):
    """Ensure the Organization singleton (id=1) exists for this test.

    STRAT-SC-001: replaces the old ``test_tenant`` factory. There is
    exactly one organization row post-conversion (``Organization.id == 1``,
    enforced by ``ck_organization_singleton``), so this doesn't create a
    new row per test — it upserts the singleton and returns it. Endpoints
    that call ``get_organization(db)`` (features, trust-gate config,
    console/launch-readiness) need this row to exist or they raise.
    """
    from app.base_models import Organization

    org = await db_session.get(Organization, 1)
    if org is None:
        org = Organization(
            id=1,
            name="Test Organization",
            slug="test-organization",
            enforcement_mode="advisory",
        )
        db_session.add(org)
        await db_session.flush()

    return {
        "id": org.id,
        "name": org.name,
        "slug": org.slug,
        "enforcement_mode": org.enforcement_mode,
    }


@pytest_asyncio.fixture(scope="function")
async def test_user(db_session) -> dict:
    """Create a test user.

    STRAT-SC-001: no more per-organization scoping column — ``User`` is a
    global row post-C1.
    """
    from app.base_models import User, UserRole
    from app.core.security import get_password_hash

    user = User(
        email="test@example.com",
        email_hash="test@example.com",  # Simplified for tests
        password_hash=get_password_hash("testpassword123"),
        full_name="Test User",
        role=UserRole.ADMIN,
        is_active=True,
        is_verified=True,
    )

    db_session.add(user)
    await db_session.flush()

    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.value,
    }


@pytest_asyncio.fixture(scope="function")
async def test_campaign(db_session) -> dict:
    """Create a test campaign draft.

    STRAT-SC-001: no more per-organization scoping column — ``CampaignDraft``
    is global.
    """
    from app.models.campaign_builder import CampaignDraft

    campaign = CampaignDraft(
        name="Test Campaign",
        status="draft",
        platform="meta",
        draft_json={
            "objective": "conversions",
            "daily_budget": 100.0,
            "currency": "USD",
        },
    )

    db_session.add(campaign)
    await db_session.flush()

    return {
        "id": str(campaign.id),
        "name": campaign.name,
        "status": campaign.status,
        "platform": campaign.platform,
        "daily_budget": campaign.draft_json.get("daily_budget"),
    }


@pytest_asyncio.fixture(scope="function")
async def test_signal_health(db_session) -> dict:
    """Create a test signal health record.

    STRAT-SC-001: no more per-organization scoping column — one row per
    platform, no organization dimension (C4 de-fan-out).
    """
    from app.models.trust_layer import FactSignalHealthDaily, SignalHealthStatus

    record = FactSignalHealthDaily(
        date=date.today(),
        platform="meta",
        emq_score=85.0,
        event_loss_pct=3.5,
        freshness_minutes=30,
        api_error_rate=0.5,
        status=SignalHealthStatus.OK,
    )

    db_session.add(record)
    await db_session.flush()

    return {
        "id": str(record.id),
        "platform": record.platform,
        "emq_score": record.emq_score,
        "status": record.status.value,
    }


@pytest_asyncio.fixture(scope="function")
async def test_action(db_session, test_user) -> dict:
    """Create a test action queue item.

    STRAT-SC-001: no more per-organization scoping column.
    """
    import json

    from app.models.trust_layer import FactActionsQueue

    action = FactActionsQueue(
        date=date.today(),
        action_type="budget_increase",
        entity_type="campaign",
        entity_id="campaign_123",
        entity_name="Test Campaign",
        platform="meta",
        action_json=json.dumps({"amount": 50, "percentage": 10}),
        status="queued",
        created_by_user_id=test_user["id"],
    )

    db_session.add(action)
    await db_session.flush()

    return {
        "id": str(action.id),
        "action_type": action.action_type,
        "status": action.status,
        "entity_name": action.entity_name,
    }


# =============================================================================
# Utility Fixtures
# =============================================================================


@pytest.fixture
def auth_headers(test_user):
    """Generate authentication headers for API requests.

    STRAT-SC-001: no more tenant claim/header.
    """
    from app.core.security import create_access_token

    token = create_access_token(
        subject=test_user["id"],
        additional_claims={
            "email": test_user["email"],
            "role": test_user["role"],
        },
    )

    return {
        "Authorization": f"Bearer {token}",
    }


@pytest_asyncio.fixture(scope="function")
async def owner_user(db_session, organization) -> dict:
    """Create the owner user backing ``owner_headers``.

    Owner endpoints resolve the caller via ``get_current_user``
    (``SELECT User WHERE id = <jwt subject>``) and audit tables FK
    ``user_id -> users.id``. The token must therefore be signed for a real
    owner row, otherwise requests 401 and event inserts violate the FK.

    STRAT-SC-001: no more per-owner ``Tenant`` row — depends on the
    ``organization`` fixture (the Organization singleton) instead, since
    owner/console endpoints commonly call ``get_organization(db)``.
    """
    from app.base_models import User, UserRole
    from app.core.security import get_password_hash

    user = User(
        email="admin@stratum.ai",
        email_hash="admin@stratum.ai",
        password_hash=get_password_hash("adminpassword123"),
        full_name="Owner",
        role=UserRole.OWNER,
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.flush()

    return {
        "id": user.id,
        "email": user.email,
        "role": user.role.value,
    }


@pytest_asyncio.fixture(scope="function")
async def owner_headers(owner_user) -> dict:
    """Generate owner authentication headers for a real owner row."""
    from app.core.security import create_access_token

    token = create_access_token(
        subject=owner_user["id"],
        additional_claims={
            "email": owner_user["email"],
            "role": owner_user["role"],
        },
    )

    return {
        "Authorization": f"Bearer {token}",
    }


# =============================================================================
# Database Setup/Teardown
# =============================================================================


@pytest.fixture(scope="session", autouse=True)
def setup_test_database(sync_engine):
    """Build the test schema with the real Alembic migration chain (#343).

    Previously this fixture built schema via ``Base.metadata.create_all``
    plus manual ``CREATE TYPE`` / ``ALTER COLUMN`` DDL to fake the native
    enums migrations create — which let model<->migration drift pass
    unnoticed (see migration 055). Running the actual chain keeps the test
    schema identical to production (native enum columns included, so
    ``StrEnumType.bind_expression``'s CAST just works) at a cost of ~10s
    once per session.

    Requires a pgvector-enabled PostgreSQL image (migration 049 runs
    ``CREATE EXTENSION vector``) — CI uses ``pgvector/pgvector:pg16``,
    same as the local compose db.
    """
    from pathlib import Path

    from alembic.config import Config
    from sqlalchemy import text

    from alembic import command

    with sync_engine.begin() as conn:
        # Clean slate: nukes tables, enum types, and the vector extension
        # in one shot (migration 049 recreates the extension).
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        # Revision ids reach 38 chars; Alembic's default version table is
        # VARCHAR(32). Pre-create it wide (same as fix_alembic_version.py —
        # the version_num_width kwarg in env.py is not a real Alembic
        # option and is silently ignored).
        conn.execute(
            text(
                "CREATE TABLE alembic_version ("
                "version_num VARCHAR(128) NOT NULL, "
                "CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num))"
            )
        )

    backend_dir = Path(__file__).resolve().parents[2]
    cfg = Config(str(backend_dir / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_dir / "migrations"))
    # migrations/env.py reads settings.database_url_sync, which the
    # os.environ lines at the top of this module already point at
    # TEST_DATABASE_URL_SYNC before any app import.
    command.upgrade(cfg, "head")

    yield


# =============================================================================
# Sample Data Fixtures
# =============================================================================


@pytest.fixture
def sample_platform_metrics():
    """Sample platform metrics for EMQ calculation."""
    from app.analytics.logic.emq_calculation import PlatformMetrics

    return PlatformMetrics(
        platform="meta",
        pixel_events=10000,
        capi_events=8500,
        matched_events=8000,
        pages_with_pixel=95,
        total_pages=100,
        events_configured=8,
        events_expected=10,
        avg_conversion_latency_hours=2.5,
        platform_conversions=500,
        ga4_conversions=520,
        platform_revenue=50000.0,
        ga4_revenue=52000.0,
        last_event_at=datetime.now(timezone.utc),
    )
