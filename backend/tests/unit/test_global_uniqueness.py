# =============================================================================
# Stratum AI - Global Uniqueness Tests [STRAT-SC-001 / Task C1]
# =============================================================================
"""
One positive+negative pair per §4.9 constraint conversion.

Every constraint below used to be scoped by a per-organization column
(composite unique key) and is now a bare global unique constraint, per the
single-client conversion (the ``Tenant`` model and its scoping column were
deleted in this task). Each pair proves:

- positive: the first row inserts cleanly.
- negative: a second row that only duplicates the *remaining* (post-rescope)
  columns is rejected with ``IntegrityError`` — i.e. uniqueness is enforced
  globally, with no tenant dimension left to disambiguate it.

Schema strategy: C1 predates the fresh Alembic chain (that's Task C6), so
this module builds the test schema directly from the current SQLAlchemy
metadata (``Base.metadata.create_all``) against the real Postgres test
database, rather than running the (still tenant-shaped) legacy migration
chain. Requires the integration-runway env vars (DATABASE_URL /
DATABASE_URL_SYNC pointed at the dockerized ``stratum_db``) to be set in the
same shell invocation as pytest.
"""

from __future__ import annotations

from typing import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

pytestmark = pytest.mark.asyncio


# =============================================================================
# Schema + session fixtures
# =============================================================================


@pytest.fixture(scope="session")
def sync_engine():
    """Sync engine used only to (re)build the schema from metadata."""
    from app.core.config import settings

    engine = create_engine(settings.database_url_sync, echo=False, pool_pre_ping=True)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def _fresh_schema(sync_engine):
    """Build a schema straight from current model metadata.

    C1 has not regenerated the Alembic chain yet (Task C6 does that) — using
    ``Base.metadata.create_all`` here means these tests exercise the *new*
    post-C1 constraint shapes rather than the still tenant-scoped migration
    history.
    """
    from sqlalchemy import text

    import app.base_models  # noqa: F401 - register base models with Base.metadata
    import app.models  # noqa: F401 - register all model modules
    from app.db.base import Base, StrEnumType

    # StrEnumType (app.db.base) always binds with create_type=False — it
    # assumes the native PG enum type already exists (normally created by an
    # Alembic migration). Since this fixture builds schema straight from
    # metadata (no migrations), pre-create every distinct PG enum type that
    # any StrEnumType column references, mirroring what the migration chain
    # would do.
    pg_enum_types: dict[str, list[str]] = {}
    for table in Base.metadata.tables.values():
        for column in table.columns:
            col_type = column.type
            if isinstance(col_type, StrEnumType):
                pg_enum_types.setdefault(
                    col_type._pg_enum_name,
                    [e.value for e in col_type.enum_class],
                )

    with sync_engine.begin() as conn:
        # DROP SCHEMA ... CASCADE rather than Base.metadata.drop_all: the test
        # DB may carry leftover tables from the pre-C1 (tenant-shaped) schema
        # that are no longer tracked by the current metadata (e.g. the
        # deleted user_tenant_memberships table), which would otherwise block
        # drop_all with FK dependency errors.
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        for type_name, values in pg_enum_types.items():
            labels = ", ".join(f"'{v}'" for v in values)
            conn.execute(text(f"CREATE TYPE {type_name} AS ENUM ({labels})"))
        Base.metadata.create_all(conn)
    yield


@pytest_asyncio.fixture
async def async_engine():
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


@pytest_asyncio.fixture
async def db_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    """Savepoint-scoped session — same recipe as tests/integration/conftest.py."""
    connection = await async_engine.connect()
    transaction = await connection.begin()
    session = AsyncSession(bind=connection, expire_on_commit=False, autoflush=False)
    await connection.begin_nested()

    @event.listens_for(session.sync_session, "after_transaction_end")
    def _restart_savepoint(session_inner, trans):
        if trans.nested and not trans._parent.nested:
            session_inner.begin_nested()

    yield session

    await session.close()
    await transaction.rollback()
    await connection.close()


# =============================================================================
# Helper factories (minimal required fields per model)
# =============================================================================


def make_user(**overrides):
    from app.base_models import User

    defaults = dict(
        email="dup@example.com",
        email_hash="dup@example.com",
        password_hash="hashed",
    )
    defaults.update(overrides)
    return User(**defaults)


def make_campaign(**overrides):
    from app.base_models import AdPlatform, Campaign

    defaults = dict(
        platform=AdPlatform.META,
        external_id="ext-123",
        account_id="act-123",
        name="Test Campaign",
    )
    defaults.update(overrides)
    return Campaign(**defaults)


def make_competitor_benchmark(**overrides):
    from app.base_models import CompetitorBenchmark

    defaults = dict(domain="example.com")
    defaults.update(overrides)
    return CompetitorBenchmark(**defaults)


def make_creative(**overrides):
    from app.models.audit_services import Creative

    defaults = dict(external_id="creative-1", platform="meta")
    defaults.update(overrides)
    return Creative(**defaults)


def make_audience_record(**overrides):
    from app.models.audit_services import AudienceRecord

    defaults = dict(
        external_id="aud-1",
        platform="meta",
        name="Lookalike 1%",
        audience_type="lookalike",
    )
    defaults.update(overrides)
    return AudienceRecord(**defaults)


def make_ltv_cohort(**overrides):
    from app.models.audit_services import LTVCohortAnalysis

    defaults = dict(cohort_month="2026-01")
    defaults.update(overrides)
    return LTVCohortAnalysis(**defaults)


def make_enforcement_settings(**overrides):
    from app.models.autopilot import TenantEnforcementSettings

    return TenantEnforcementSettings(**overrides)


def make_enforcement_rule(settings_id, **overrides):
    from app.models.autopilot import TenantEnforcementRule, ViolationType

    defaults = dict(
        settings_id=settings_id,
        rule_id="rule-1",
        rule_type=ViolationType.BUDGET_EXCEEDED,
        threshold_value=100.0,
    )
    defaults.update(overrides)
    return TenantEnforcementRule(**defaults)


def make_platform_connection(**overrides):
    from app.models.campaign_builder import PlatformConnection

    defaults = dict(platform="meta")
    defaults.update(overrides)
    return PlatformConnection(**defaults)


def make_cdp_profile(**overrides):
    from app.models.cdp import CDPProfile

    return CDPProfile(**overrides)


def make_cdp_canonical_identity(profile_id, **overrides):
    from app.models.cdp import CDPCanonicalIdentity

    defaults = dict(profile_id=profile_id)
    defaults.update(overrides)
    return CDPCanonicalIdentity(**defaults)


def make_cdp_segment(**overrides):
    from app.models.cdp import CDPSegment

    defaults = dict(name="Test Segment", slug="test-segment")
    defaults.update(overrides)
    return CDPSegment(**defaults)


def make_cdp_computed_trait(**overrides):
    from app.models.cdp import CDPComputedTrait

    defaults = dict(name="total_purchases", display_name="Total Purchases")
    defaults.update(overrides)
    return CDPComputedTrait(**defaults)


def make_cdp_funnel(**overrides):
    from app.models.cdp import CDPFunnel

    defaults = dict(name="Test Funnel", slug="test-funnel")
    defaults.update(overrides)
    return CDPFunnel(**defaults)


def make_client(**overrides):
    from app.models.client import Client

    defaults = dict(name="Test Client", slug="test-client")
    defaults.update(overrides)
    return Client(**defaults)


def make_emq_playbook_item(**overrides):
    from app.models.emq_playbook import EmqPlaybookItemState

    defaults = dict(item_key="enhanced_conversions")
    defaults.update(overrides)
    return EmqPlaybookItemState(**defaults)


def make_product(**overrides):
    from app.models.profit import ProductCatalog

    defaults = dict(sku="SKU-1", name="Test Product")
    defaults.update(overrides)
    return ProductCatalog(**defaults)


def make_report_template(**overrides):
    from app.models.reporting import ReportTemplate, ReportType

    defaults = dict(name="Test Report", report_type=ReportType.CUSTOM)
    defaults.update(overrides)
    return ReportTemplate(**defaults)


def make_delivery_channel_config(**overrides):
    from app.models.reporting import DeliveryChannel, DeliveryChannelConfig

    defaults = dict(channel=DeliveryChannel.EMAIL, name="Primary Email", config={})
    defaults.update(overrides)
    return DeliveryChannelConfig(**defaults)


# =============================================================================
# 1. base_models.py:481 - User.email_hash  (was org-scope + email_hash)
# =============================================================================


async def test_user_email_hash_globally_unique(db_session) -> None:
    u1 = make_user(email="dup@example.com", email_hash="dup@example.com")
    db_session.add(u1)
    await db_session.commit()  # positive

    u2 = make_user(email="dup2@example.com", email_hash="dup@example.com")
    db_session.add(u2)
    with pytest.raises(IntegrityError):  # negative
        await db_session.commit()


# =============================================================================
# 2. base_models.py:637 - Campaign(platform, external_id)  (was + org-scope)
# =============================================================================


async def test_campaign_platform_external_id_globally_unique(db_session) -> None:
    from app.base_models import AdPlatform

    c1 = make_campaign(platform=AdPlatform.META, external_id="dup-ext")
    db_session.add(c1)
    await db_session.commit()  # positive

    c2 = make_campaign(platform=AdPlatform.META, external_id="dup-ext")
    db_session.add(c2)
    with pytest.raises(IntegrityError):  # negative
        await db_session.commit()


# =============================================================================
# 3. base_models.py:958 - CompetitorBenchmark.domain  (was + org-scope)
# =============================================================================


async def test_competitor_benchmark_domain_globally_unique(db_session) -> None:
    b1 = make_competitor_benchmark(domain="dup-domain.com")
    db_session.add(b1)
    await db_session.commit()  # positive

    b2 = make_competitor_benchmark(domain="dup-domain.com")
    db_session.add(b2)
    with pytest.raises(IntegrityError):  # negative
        await db_session.commit()


# =============================================================================
# 4. base_models.py:524 - UserTenantMembership(user_id, org-scope)
#    Table deleted entirely (multi-tenant membership concept removed) --
#    no conversion to test; nothing left to assert uniqueness on.
# =============================================================================


# =============================================================================
# 5. models/audit_services.py:604 - Creative(platform, external_id)
# =============================================================================


async def test_creative_platform_external_id_globally_unique(db_session) -> None:
    c1 = make_creative(platform="meta", external_id="dup-creative")
    db_session.add(c1)
    await db_session.commit()  # positive

    c2 = make_creative(platform="meta", external_id="dup-creative")
    db_session.add(c2)
    with pytest.raises(IntegrityError):  # negative
        await db_session.commit()


# =============================================================================
# 6. models/audit_services.py:1000 - AudienceRecord(platform, external_id)
# =============================================================================


async def test_audience_record_platform_external_id_globally_unique(db_session) -> None:
    a1 = make_audience_record(platform="meta", external_id="dup-audience")
    db_session.add(a1)
    await db_session.commit()  # positive

    a2 = make_audience_record(platform="meta", external_id="dup-audience")
    db_session.add(a2)
    with pytest.raises(IntegrityError):  # negative
        await db_session.commit()


# =============================================================================
# 7. models/audit_services.py:1174 - LTVCohortAnalysis.cohort_month
# =============================================================================


async def test_ltv_cohort_month_globally_unique(db_session) -> None:
    c1 = make_ltv_cohort(cohort_month="2026-07")
    db_session.add(c1)
    await db_session.commit()  # positive

    c2 = make_ltv_cohort(cohort_month="2026-07")
    db_session.add(c2)
    with pytest.raises(IntegrityError):  # negative
        await db_session.commit()


# =============================================================================
# 8. models/autopilot.py:199 - TenantEnforcementRule.rule_id
# =============================================================================


async def test_enforcement_rule_id_globally_unique(db_session) -> None:
    settings_row = make_enforcement_settings()
    db_session.add(settings_row)
    await db_session.flush()

    r1 = make_enforcement_rule(settings_row.id, rule_id="dup-rule")
    db_session.add(r1)
    await db_session.commit()  # positive

    r2 = make_enforcement_rule(settings_row.id, rule_id="dup-rule")
    db_session.add(r2)
    with pytest.raises(IntegrityError):  # negative
        await db_session.commit()


# =============================================================================
# 9. models/campaign_builder.py:147 - PlatformConnection.platform
# =============================================================================


async def test_platform_connection_platform_globally_unique(db_session) -> None:
    p1 = make_platform_connection(platform="meta")
    db_session.add(p1)
    await db_session.commit()  # positive

    p2 = make_platform_connection(platform="meta")
    db_session.add(p2)
    with pytest.raises(IntegrityError):  # negative
        await db_session.commit()


# =============================================================================
# 10. models/cdp.py:775 - CDPCanonicalIdentity.profile_id
# =============================================================================


async def test_cdp_canonical_identity_profile_id_globally_unique(db_session) -> None:
    profile = make_cdp_profile()
    db_session.add(profile)
    await db_session.flush()

    i1 = make_cdp_canonical_identity(profile.id)
    db_session.add(i1)
    await db_session.commit()  # positive

    i2 = make_cdp_canonical_identity(profile.id)
    db_session.add(i2)
    with pytest.raises(IntegrityError):  # negative
        await db_session.commit()


# =============================================================================
# 11. models/cdp.py:887 - CDPSegment.slug
# =============================================================================


async def test_cdp_segment_slug_globally_unique(db_session) -> None:
    s1 = make_cdp_segment(slug="dup-segment")
    db_session.add(s1)
    await db_session.commit()  # positive

    s2 = make_cdp_segment(slug="dup-segment")
    db_session.add(s2)
    with pytest.raises(IntegrityError):  # negative
        await db_session.commit()


# =============================================================================
# 12. models/cdp.py:1027 - CDPComputedTrait.name
# =============================================================================


async def test_cdp_computed_trait_name_globally_unique(db_session) -> None:
    t1 = make_cdp_computed_trait(name="dup-trait")
    db_session.add(t1)
    await db_session.commit()  # positive

    t2 = make_cdp_computed_trait(name="dup-trait")
    db_session.add(t2)
    with pytest.raises(IntegrityError):  # negative
        await db_session.commit()


# =============================================================================
# 13. models/cdp.py:1116 - CDPFunnel.slug
# =============================================================================


async def test_cdp_funnel_slug_globally_unique(db_session) -> None:
    f1 = make_cdp_funnel(slug="dup-funnel")
    db_session.add(f1)
    await db_session.commit()  # positive

    f2 = make_cdp_funnel(slug="dup-funnel")
    db_session.add(f2)
    with pytest.raises(IntegrityError):  # negative
        await db_session.commit()


# =============================================================================
# 14. models/client.py:130 - Client.slug
# =============================================================================


async def test_client_slug_globally_unique(db_session) -> None:
    c1 = make_client(slug="dup-client")
    db_session.add(c1)
    await db_session.commit()  # positive

    c2 = make_client(slug="dup-client")
    db_session.add(c2)
    with pytest.raises(IntegrityError):  # negative
        await db_session.commit()


# =============================================================================
# 15. models/emq_playbook.py:47 - EmqPlaybookItemState.item_key
# =============================================================================


async def test_emq_playbook_item_key_globally_unique(db_session) -> None:
    i1 = make_emq_playbook_item(item_key="dup-item")
    db_session.add(i1)
    await db_session.commit()  # positive

    i2 = make_emq_playbook_item(item_key="dup-item")
    db_session.add(i2)
    with pytest.raises(IntegrityError):  # negative
        await db_session.commit()


# =============================================================================
# 16. models/profit.py:142 - ProductCatalog.sku
# =============================================================================


async def test_product_sku_globally_unique(db_session) -> None:
    p1 = make_product(sku="dup-sku")
    db_session.add(p1)
    await db_session.commit()  # positive

    p2 = make_product(sku="dup-sku")
    db_session.add(p2)
    with pytest.raises(IntegrityError):  # negative
        await db_session.commit()


# =============================================================================
# 17. models/reporting.py:194 - ReportTemplate.name
# =============================================================================


async def test_report_template_name_globally_unique(db_session) -> None:
    r1 = make_report_template(name="dup-report")
    db_session.add(r1)
    await db_session.commit()  # positive

    r2 = make_report_template(name="dup-report")
    db_session.add(r2)
    with pytest.raises(IntegrityError):  # negative
        await db_session.commit()


# =============================================================================
# 18. models/reporting.py:559 - DeliveryChannelConfig(channel, name)
# =============================================================================


async def test_delivery_channel_config_channel_name_globally_unique(db_session) -> None:
    from app.models.reporting import DeliveryChannel

    d1 = make_delivery_channel_config(channel=DeliveryChannel.SLACK, name="dup-channel")
    db_session.add(d1)
    await db_session.commit()  # positive

    d2 = make_delivery_channel_config(channel=DeliveryChannel.SLACK, name="dup-channel")
    db_session.add(d2)
    with pytest.raises(IntegrityError):  # negative
        await db_session.commit()
