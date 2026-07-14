# =============================================================================
# Stratum AI - Feature Flags API Integration Tests
# =============================================================================
"""Integration tests for the org + owner feature-flags API.

Exercises the real ASGI app against Postgres + Redis: organization feature
retrieval/update (single global org, no per-tenant scoping), and the owner
console routes (which gate on the ``owner`` role).

The owner route tests also guard the role-attribute fix: these
handlers previously read ``request.state.user_role`` (never set by the
tenant middleware, which populates ``request.state.role``), so every
owner feature-flag route returned 403 regardless of caller.

STRAT-SC-001: these routes used to be scoped under path-organization
prefixes (``/api/v1/tenant/<id>/features`` and
``/api/v1/console/tenants/<id>/features``); both are now un-prefixed
(``/api/v1/features`` and ``/api/v1/console/features``) since there is
exactly one organization. Cross-tenant-isolation tests were removed
entirely — that concept no longer exists.
"""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


# =============================================================================
# Org routes
# =============================================================================
class TestOrgFeatures:
    @pytest.mark.asyncio
    async def test_get_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/features")
        assert resp.status_code in {401, 403}

    @pytest.mark.asyncio
    async def test_get_features(
        self, authenticated_client: AsyncClient, organization: dict
    ):
        resp = await authenticated_client.get("/api/v1/features")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "features" in data
        assert "categories" in data
        assert "descriptions" in data

    @pytest.mark.asyncio
    async def test_update_features_persists(
        self, client: AsyncClient, owner_headers: dict, organization: dict
    ):
        # PUT requires the owner role (require_owner()); authenticated_client
        # in this suite is an ADMIN, so exercise it as owner instead.
        updated = await client.put(
            "/api/v1/features",
            headers=owner_headers,
            json={"campaign_builder": True, "autopilot_level": 2},
        )
        assert updated.status_code == 200
        feats = updated.json()["data"]["features"]
        assert feats["campaign_builder"] is True
        assert feats["autopilot_level"] == 2

        # Override is persisted and visible on a subsequent GET.
        fetched = await client.get("/api/v1/features", headers=owner_headers)
        assert fetched.json()["data"]["features"]["campaign_builder"] is True

    @pytest.mark.asyncio
    async def test_update_rejects_out_of_range(
        self, client: AsyncClient, owner_headers: dict, organization: dict
    ):
        resp = await client.put(
            "/api/v1/features",
            headers=owner_headers,
            json={"autopilot_level": 9},  # bounded 0..2
        )
        assert resp.status_code == 422


# =============================================================================
# Owner routes (role-gated)
# =============================================================================
class TestOwnerFeatures:
    @pytest.mark.asyncio
    async def test_non_owner_forbidden(self, authenticated_client: AsyncClient):
        # authenticated_client is an ADMIN, not a owner → 403.
        resp = await authenticated_client.get("/api/v1/console/features")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_owner_get_features(
        self, client: AsyncClient, owner_headers: dict
    ):
        resp = await client.get(
            "/api/v1/console/features",
            headers=owner_headers,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "features" in data

    @pytest.mark.asyncio
    async def test_owner_update_features(
        self, client: AsyncClient, owner_headers: dict
    ):
        resp = await client.put(
            "/api/v1/console/features",
            headers=owner_headers,
            json={"signal_health": True},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["features"]["signal_health"] is True

    @pytest.mark.asyncio
    async def test_owner_reset_features(
        self, client: AsyncClient, owner_headers: dict
    ):
        resp = await client.post(
            "/api/v1/console/features/reset",
            headers=owner_headers,
        )
        assert resp.status_code == 200
        assert "features" in resp.json()["data"]

    @pytest.mark.asyncio
    async def test_feature_metadata(self, client: AsyncClient, owner_headers: dict):
        resp = await client.get(
            "/api/v1/console/feature-metadata", headers=owner_headers
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "categories" in data
        assert "descriptions" in data
