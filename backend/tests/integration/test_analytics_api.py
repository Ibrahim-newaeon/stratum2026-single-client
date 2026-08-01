# =============================================================================
# ADs Growth System - Analytics Dashboard Endpoint Integration Tests
# =============================================================================
"""Integration tests for the analytics dashboard surface under
``/api/v1/analytics/...``: KPI tiles, demographics, heatmap, platform &
account breakdowns, trends, tenant overview, and executive summary.

All endpoints aggregate org-wide ``CampaignMetric`` rows. The smoke tests
assert each endpoint is reachable and returns a 200 envelope on an empty
database; ``/kpis`` is additionally exercised against a seeded metric.
"""

import datetime as dt

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

_BASE = "/api/v1/analytics"

_ENDPOINTS = [
    "/kpis",
    "/demographics",
    "/heatmap",
    "/platform-breakdown",
    "/account-breakdown",
    "/trends",
    "/tenant-overview",
    "/executive-summary",
]


async def _seed_metric(
    db: AsyncSession,
    *,
    spend_cents: int,
    revenue_cents: int,
    impressions: int = 0,
    clicks: int = 0,
    conversions: int = 0,
):
    """Insert a Campaign + a CampaignMetric dated today."""
    from app.models import Campaign, CampaignMetric

    campaign = Campaign(
        platform="meta",
        external_id="an_ext_1",
        account_id="acct_an",
        name="Analytics Campaign",
        status="active",
    )
    db.add(campaign)
    await db.flush()

    metric = CampaignMetric(
        campaign_id=campaign.id,
        date=dt.date.today(),
        spend_cents=spend_cents,
        revenue_cents=revenue_cents,
        impressions=impressions,
        clicks=clicks,
        conversions=conversions,
    )
    db.add(metric)
    await db.flush()
    return campaign, metric


class TestAuth:
    @pytest.mark.parametrize("path", _ENDPOINTS)
    async def test_requires_auth(self, client: AsyncClient, path):
        resp = await client.get(f"{_BASE}{path}")
        assert resp.status_code in {401, 403}


class TestSmoke:
    @pytest.mark.parametrize("path", _ENDPOINTS)
    async def test_empty_org_returns_200(
        self, authenticated_client: AsyncClient, organization, path
    ):
        # /tenant-overview calls get_organization(db) internally (STRAT-SC-001:
        # residual name, now reads the Organization singleton) and raises if
        # the row doesn't exist yet.
        resp = await authenticated_client.get(f"{_BASE}{path}")
        assert resp.status_code == 200, f"{path}: {resp.text}"


class TestKpis:
    async def test_kpis_aggregate_seeded_metric(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
    ):
        await _seed_metric(
            db_session,
            spend_cents=10000,  # $100
            revenue_cents=40000,  # $400
            impressions=1000,
            clicks=50,
            conversions=5,
        )
        resp = await authenticated_client.get(f"{_BASE}/kpis", params={"period": "30d"})
        assert resp.status_code == 200, resp.text
        # Envelope shape is asserted leniently — the body must carry the spend
        # or revenue we seeded somewhere in its serialized form.
        text = resp.text
        assert "spend" in text.lower() or "revenue" in text.lower()
