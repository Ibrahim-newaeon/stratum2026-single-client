# =============================================================================
# ADs Growth System - Autopilot Endpoint Integration Tests
# =============================================================================
"""Integration tests for the autopilot API under ``/api/v1/autopilot/...``:
status, action queue listing, and the action/outcome summaries.

STRAT-SC-001: this router used to be scoped under a path-organization
prefix (``/api/v1/tenant/<id>/autopilot/...``) with a path-organization /
token match check; there is now exactly one organization, so the path is
un-prefixed and the cross-tenant-forbidden test was removed entirely
(that concept no longer exists).
"""

import pytest
from httpx import AsyncClient

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

_BASE = "/api/v1/autopilot"


class TestStatus:
    async def test_requires_auth(self, client: AsyncClient):
        resp = await client.get(f"{_BASE}/status")
        assert resp.status_code in {401, 403}

    async def test_status_defaults(
        self, authenticated_client: AsyncClient, organization
    ):
        resp = await authenticated_client.get(f"{_BASE}/status")
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert "autopilot_level" in data
        assert "pending_actions" in data
        assert "caps" in data
        assert isinstance(data["enabled"], bool)


class TestActions:
    async def test_empty_actions(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.get(f"{_BASE}/actions")
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["count"] == 0
        assert data["actions"] == []

    async def test_actions_summary(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.get(f"{_BASE}/actions/summary")
        assert resp.status_code == 200, resp.text
        assert "data" in resp.json()

    async def test_outcomes_summary(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.get(f"{_BASE}/outcomes/summary")
        assert resp.status_code == 200, resp.text
        assert "data" in resp.json()
