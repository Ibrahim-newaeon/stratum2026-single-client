# =============================================================================
# Stratum AI - Owner Analytics Endpoint Integration Tests
# =============================================================================
"""Integration tests for the platform-wide owner analytics under
``/api/v1/console/analytics/console/...``: platform overview, tenant
profitability, signal-health trends, and actions analytics. Every route is
gated on ``request.state.is_superadmin``.
"""

import pytest
from httpx import AsyncClient

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

_BASE = "/api/v1/console/analytics/console"

_ENDPOINTS = [
    "/platform-overview",
    "/tenant-profitability",
    "/signal-health-trends",
    "/actions-analytics",
]


class TestOwnerGate:
    async def test_requires_auth(self, client: AsyncClient):
        resp = await client.get(f"{_BASE}/platform-overview")
        assert resp.status_code in {401, 403}

    async def test_non_owner_forbidden(self, authenticated_client: AsyncClient):
        # authenticated_client is a regular ADMIN -> is_superadmin is False.
        resp = await authenticated_client.get(f"{_BASE}/platform-overview")
        assert resp.status_code == 403


class TestOwnerAnalytics:
    @pytest.mark.parametrize("path", _ENDPOINTS)
    async def test_owner_can_read(
        self, client: AsyncClient, owner_headers, path
    ):
        resp = await client.get(f"{_BASE}{path}", headers=owner_headers)
        assert resp.status_code == 200, f"{path}: {resp.text}"
        assert resp.json()["success"] is True
