# =============================================================================
# ADs Growth System - Campaigns API Integration Tests
# =============================================================================
"""Integration tests for the campaigns list/detail API.

Exercises the real ASGI app against Postgres + Redis: campaign listing
with pagination and platform filtering, campaign detail, and auth
enforcement.

STRAT-SC-001: ``Campaign`` has no per-organization scoping column anymore
(global table, single organization) — the cross-tenant-isolation test was
removed entirely, that concept no longer exists.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


async def _seed_campaign(
    db: AsyncSession,
    *,
    external_id: str,
    name: str,
    platform: str = "meta",
    status: str = "active",
):
    """Insert a real Campaign row (the list endpoint queries this table)."""
    from app.models import Campaign

    campaign = Campaign(
        platform=platform,
        external_id=external_id,
        account_id="acct_test",
        name=name,
        status=status,
    )
    db.add(campaign)
    await db.flush()
    return campaign


# =============================================================================
# List (authenticated)
# =============================================================================
class TestCampaignsList:
    @pytest.mark.asyncio
    async def test_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/campaigns")
        assert resp.status_code in {401, 403}

    @pytest.mark.asyncio
    async def test_empty_list_envelope(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.get("/api/v1/campaigns")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["items"] == []
        assert body["data"]["total"] == 0

    @pytest.mark.asyncio
    async def test_lists_campaigns(
        self, authenticated_client: AsyncClient, db_session: AsyncSession
    ):
        await _seed_campaign(db_session, external_id="ext_1", name="Summer Sale")
        await _seed_campaign(db_session, external_id="ext_2", name="Winter Promo")
        resp = await authenticated_client.get("/api/v1/campaigns")
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        assert {c["name"] for c in items} == {"Summer Sale", "Winter Promo"}
        assert resp.json()["data"]["total"] == 2

    @pytest.mark.asyncio
    async def test_pagination(
        self, authenticated_client: AsyncClient, db_session: AsyncSession
    ):
        for i in range(3):
            await _seed_campaign(db_session, external_id=f"p_{i}", name=f"Camp {i}")
        resp = await authenticated_client.get("/api/v1/campaigns?page=1&page_size=2")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data["items"]) == 2
        assert data["total"] == 3

    @pytest.mark.asyncio
    async def test_platform_filter(
        self, authenticated_client: AsyncClient, db_session: AsyncSession
    ):
        await _seed_campaign(
            db_session,
            external_id="m1",
            name="Meta",
            platform="meta",
        )
        await _seed_campaign(
            db_session,
            external_id="g1",
            name="Google",
            platform="google",
        )
        resp = await authenticated_client.get("/api/v1/campaigns?platform=google")
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        assert [c["name"] for c in items] == ["Google"]


# =============================================================================
# Detail
# =============================================================================
class TestCampaignDetail:
    @pytest.mark.asyncio
    async def test_detail_success(
        self, authenticated_client: AsyncClient, db_session: AsyncSession
    ):
        campaign = await _seed_campaign(
            db_session, external_id="d1", name="Detail Campaign"
        )
        resp = await authenticated_client.get(f"/api/v1/campaigns/{campaign.id}")
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "Detail Campaign"

    @pytest.mark.asyncio
    async def test_detail_not_found(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.get("/api/v1/campaigns/999999")
        assert resp.status_code == 404
