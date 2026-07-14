# =============================================================================
# Stratum AI - QA Fixes Endpoint Integration Tests
# =============================================================================
"""Integration tests for the QA-fixes surface under ``/api/v1/qa-fixes/...``:
quality-issue detection, the prioritized fix playbook, and applied-fix
history.

STRAT-SC-001: routes no longer take a tenant_id path segment (single global
organization); the router now enforces real auth via
``dependencies=[Depends(get_current_user)]`` router-wide.
"""

import pytest
from httpx import AsyncClient

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

_BASE = "/api/v1/qa-fixes"


class TestHealth:
    async def test_health(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.get(f"{_BASE}/health")
        assert resp.status_code == 200


class TestIssues:
    async def test_requires_auth(self, client: AsyncClient):
        resp = await client.get(f"{_BASE}/issues")
        assert resp.status_code in {401, 403}

    # STRAT-SC-001: cross-tenant isolation no longer exists (single org) —
    # test_cross_tenant_forbidden removed (routes no longer take a
    # tenant_id path segment to mismatch against).

    async def test_no_connections_empty_issues(
        self, authenticated_client: AsyncClient
    ):
        resp = await authenticated_client.get(f"{_BASE}/issues")
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["total"] == 0
        assert data["issues"] == []


class TestPlaybook:
    async def test_empty_playbook(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.get(f"{_BASE}/playbook")
        assert resp.status_code == 200, resp.text
        assert "data" in resp.json()

    # STRAT-SC-001: cross-tenant isolation no longer exists (single org) —
    # test_cross_tenant_forbidden removed (routes no longer take a
    # tenant_id path segment to mismatch against).


class TestHistory:
    async def test_empty_history(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.get(f"{_BASE}/history")
        assert resp.status_code == 200, resp.text
        assert "data" in resp.json()
