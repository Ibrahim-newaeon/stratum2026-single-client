# =============================================================================
# ADs Growth System - Integrations (HubSpot) Endpoint Integration Tests
# =============================================================================
"""Integration tests for the HubSpot integration reads under
``/api/v1/integrations/...``: connection status and pipeline ROAS. These read
DB-backed connection/metric state (no live HubSpot API calls).

Every route is owner-gated (``require_owner``). The 200-path therefore uses
owner auth.

STRAT-SC-001: these routes used to also enforce a per-organization query
param matching the request's organization (``_verify_tenant_access``) —
there is now exactly one organization, so that query param and its
matching request header are gone, and the tenant-mismatch test was
removed entirely (that concept no longer exists).

NOTE: run with the session-scoped event loop CI uses
(``-o asyncio_default_test_loop_scope=session``).
"""

import pytest
from httpx import AsyncClient

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

_BASE = "/api/v1/integrations"


class TestGate:
    async def test_requires_auth(self, client: AsyncClient):
        resp = await client.get(f"{_BASE}/hubspot/status")
        assert resp.status_code in {401, 403}

    async def test_non_owner_denied(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.get(f"{_BASE}/hubspot/status")
        assert resp.status_code == 403


class TestHubSpotStatus:
    async def test_status_not_connected(self, client: AsyncClient, owner_headers):
        resp = await client.get(
            f"{_BASE}/hubspot/status",
            headers=owner_headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["connected"] is False


class TestPipelineRoas:
    async def test_pipeline_roas_empty(self, client: AsyncClient, owner_headers):
        resp = await client.get(
            f"{_BASE}/pipeline/roas",
            params={
                "start_date": "2026-01-01",
                "end_date": "2026-06-01",
            },
            headers=owner_headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["success"] is True
