# =============================================================================
# Stratum AI - Owner Analytics Endpoint Integration Tests
# =============================================================================
"""Integration tests for the platform-wide owner analytics under
``/api/v1/console/analytics/console/...``: platform overview, signal-health
trends, and actions analytics. Every route is gated by
``Depends(require_owner())`` (``app.auth.deps``).

STRAT-SC-001 (Task C6): ``/tenant-profitability`` (+ its ``calculate_health_score``
helper) was deleted in C3 — it enumerated tenants and grouped by the dropped
``tenant_id`` column, which makes no sense for a single-org deployment.
Removed from this suite's endpoint list accordingly.
"""

import pytest
from httpx import AsyncClient

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

_BASE = "/api/v1/console/analytics/console"

_ENDPOINTS = [
    "/platform-overview",
    "/signal-health-trends",
    "/actions-analytics",
]


class TestOwnerGate:
    async def test_requires_auth(self, client: AsyncClient):
        resp = await client.get(f"{_BASE}/platform-overview")
        assert resp.status_code in {401, 403}

    async def test_non_owner_forbidden(self, authenticated_client: AsyncClient):
        # authenticated_client is a regular ADMIN -> require_owner() 403s it.
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
