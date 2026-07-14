# =============================================================================
# Stratum AI - Trust Layer Endpoint Integration Tests
# =============================================================================
"""Integration tests for the Trust Layer surface under
``/api/v1/trust/...``: signal-health (+history), trust-status,
and the feature-flag gates.

Signal health reads ``fact_signal_health_daily``; the happy-path tests seed
a real row for today and assert the computed overall status + automation
block. The ``signal_health`` feature flag is toggled per-test via the
Organization singleton's ``feature_flags`` JSON override so behaviour is
deterministic regardless of plan defaults.

STRAT-SC-001: de-tenanted. There is exactly one Organization singleton
(id=1) now, so feature flags live on ``Organization.feature_flags`` rather
than a per-tenant row, and the routes no longer take a tenant_id path
segment.
"""

import datetime as dt

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

_BASE = "/api/v1/trust"


async def _set_features(db: AsyncSession, **flags) -> None:
    """Override the Organization's feature_flags JSON (overrides beat plan defaults)."""
    from sqlalchemy import update

    from app.base_models import Organization

    await db.execute(
        update(Organization).where(Organization.id == 1).values(feature_flags=flags)
    )
    await db.flush()


async def _seed_signal_health(
    db: AsyncSession,
    *,
    platform: str,
    status,
    emq_score: float = 95.0,
    event_loss_pct: float = 2.0,
):
    """Insert a fact_signal_health_daily row for today."""
    from app.models.trust_layer import FactSignalHealthDaily

    record = FactSignalHealthDaily(
        date=dt.date.today(),
        platform=platform,
        account_id="acct_1",
        emq_score=emq_score,
        event_loss_pct=event_loss_pct,
        freshness_minutes=10,
        api_error_rate=0.5,
        status=status,
    )
    db.add(record)
    await db.flush()
    return record


# =============================================================================
# Signal health — gates
# =============================================================================
class TestSignalHealthGates:
    async def test_requires_auth(self, client: AsyncClient):
        resp = await client.get(f"{_BASE}/signal-health")
        assert resp.status_code in {401, 403}

    # STRAT-SC-001: cross-tenant isolation no longer exists (single org) —
    # test_cross_tenant_forbidden removed (routes no longer take a
    # tenant_id path segment to mismatch against).

    async def test_feature_disabled_forbidden(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        organization,
    ):
        await _set_features(db_session, signal_health=False)
        resp = await authenticated_client.get(f"{_BASE}/signal-health")
        assert resp.status_code == 403


# =============================================================================
# Signal health — data
# =============================================================================
class TestSignalHealth:
    async def test_empty_returns_no_data(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        organization,
    ):
        await _set_features(db_session, signal_health=True)
        resp = await authenticated_client.get(f"{_BASE}/signal-health")
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["status"] == "no_data"
        assert data["automation_blocked"] is False

    async def test_critical_record_blocks_automation(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        organization,
    ):
        from app.models.trust_layer import SignalHealthStatus

        await _set_features(db_session, signal_health=True)
        await _seed_signal_health(
            db_session,
            platform="meta",
            status=SignalHealthStatus.CRITICAL,
            emq_score=55.0,
            event_loss_pct=40.0,
        )
        resp = await authenticated_client.get(f"{_BASE}/signal-health")
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["status"] == "critical"
        assert data["automation_blocked"] is True
        assert len(data["platform_rows"]) == 1
        assert data["platform_rows"][0]["platform"] == "meta"

    async def test_history_returns_empty_envelope(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        organization,
    ):
        await _set_features(db_session, signal_health=True)
        resp = await authenticated_client.get(
            f"{_BASE}/signal-health/history", params={"days": 7}
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["days"] == 7
        assert data["history"] == []


# =============================================================================
# Combined trust status
# =============================================================================
class TestTrustStatus:
    # STRAT-SC-001: cross-tenant isolation no longer exists (single org) —
    # test_requires_tenant_match removed (routes no longer take a tenant_id
    # path segment to mismatch against).

    async def test_ok_when_no_features(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        organization,
    ):
        # Both trust features off -> bare status, automation allowed.
        await _set_features(
            db_session,
            signal_health=False,
            attribution_variance=False,
        )
        resp = await authenticated_client.get(f"{_BASE}/trust-status")
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["overall_status"] == "ok"
        assert data["automation_allowed"] is True
        assert data["signal_health"] is None

    async def test_degraded_signal_health_blocks_automation(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        organization,
    ):
        from app.models.trust_layer import SignalHealthStatus

        await _set_features(
            db_session,
            signal_health=True,
            attribution_variance=False,
        )
        await _seed_signal_health(
            db_session,
            platform="google",
            status=SignalHealthStatus.DEGRADED,
            emq_score=70.0,
            event_loss_pct=20.0,
        )
        resp = await authenticated_client.get(f"{_BASE}/trust-status")
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["overall_status"] == "degraded"
        assert data["automation_allowed"] is False
        assert data["signal_health"] is not None
        assert data["signal_health"]["status"] == "degraded"
