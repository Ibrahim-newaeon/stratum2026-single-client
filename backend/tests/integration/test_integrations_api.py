# =============================================================================
# Stratum AI - Integrations (HubSpot) Endpoint Integration Tests
# =============================================================================
"""Integration tests for the HubSpot integration reads under
``/api/v1/integrations/...``: connection status and pipeline ROAS. These read
DB-backed connection/metric state (no live HubSpot API calls).

Every route is owner-gated (``require_owner``) AND enforces that
the ``tenant_id`` query param matches the request's tenant
(``_verify_tenant_access``). The 200-path therefore uses owner auth with a
matching ``X-Tenant-ID``.

NOTE: run with the session-scoped event loop CI uses
(``-o asyncio_default_test_loop_scope=session``).
"""

import pytest
from httpx import AsyncClient

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

_BASE = "/api/v1/integrations"


def _sa(owner_headers, tenant_id):
    return {**owner_headers, "X-Tenant-ID": str(tenant_id)}


class TestGate:
    async def test_requires_auth(self, client: AsyncClient, test_tenant):
        resp = await client.get(
            f"{_BASE}/hubspot/status", params={"tenant_id": test_tenant["id"]}
        )
        assert resp.status_code in {401, 403}

    async def test_non_owner_denied(
        self, authenticated_client: AsyncClient, test_tenant
    ):
        resp = await authenticated_client.get(
            f"{_BASE}/hubspot/status", params={"tenant_id": test_tenant["id"]}
        )
        assert resp.status_code == 403


class TestHubSpotStatus:
    async def test_status_not_connected(
        self, client: AsyncClient, owner_headers, test_tenant
    ):
        resp = await client.get(
            f"{_BASE}/hubspot/status",
            params={"tenant_id": test_tenant["id"]},
            headers=_sa(owner_headers, test_tenant["id"]),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["connected"] is False

    async def test_tenant_mismatch_forbidden(
        self, client: AsyncClient, owner_headers, test_tenant
    ):
        # Owner acting as test_tenant but querying a different tenant_id.
        resp = await client.get(
            f"{_BASE}/hubspot/status",
            params={"tenant_id": test_tenant["id"] + 99999},
            headers=_sa(owner_headers, test_tenant["id"]),
        )
        assert resp.status_code == 403


class TestPipelineRoas:
    async def test_pipeline_roas_empty(
        self, client: AsyncClient, owner_headers, test_tenant
    ):
        resp = await client.get(
            f"{_BASE}/pipeline/roas",
            params={
                "tenant_id": test_tenant["id"],
                "start_date": "2026-01-01",
                "end_date": "2026-06-01",
            },
            headers=_sa(owner_headers, test_tenant["id"]),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["success"] is True
