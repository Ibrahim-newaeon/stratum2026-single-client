# =============================================================================
# ADs Growth System - Audit Services Endpoint Integration Tests
# =============================================================================
"""Integration tests for the audit-services surface under
``/api/v1/audit-services/...``. This is a large ML-service router; these
tests cover the stable read/info/admin endpoints (health, info, metrics, and
the admin config/status/rate-limit views) plus the auth + admin gates.
"""

import pytest
from httpx import AsyncClient

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

# Live path is /api/v1/audit-services/* — the router carries its own prefix and
# is registered with an empty registry prefix (STRAT-SC-001 fix 5-1).
_BASE = "/api/v1/audit-services"

# GET endpoints that don't require request bodies, ML execution, or seeded data.
_SMOKE_GETS = [
    "/health",
    "/info",
    "/metrics",
    "/admin/services/status",
    "/admin/config",
    "/admin/rate-limits",
]


class TestAuth:
    # STRAT-SC-001 (C6): "/info" dropped from this parametrization — its
    # handler docstring declares it a public API-discovery endpoint (static
    # metadata, no per-route auth dependency). Under the old TenantMiddleware
    # it was 401'd anyway (middleware rejected everything not allowlisted);
    # AuthContextMiddleware (C2) honors the endpoint's own public contract.
    @pytest.mark.parametrize("path", ["/admin/config"])
    async def test_requires_auth(self, client: AsyncClient, path):
        resp = await client.get(f"{_BASE}{path}")
        assert resp.status_code in {401, 403}


class TestSmoke:
    @pytest.mark.parametrize("path", _SMOKE_GETS)
    async def test_get_returns_200(self, authenticated_client: AsyncClient, path):
        resp = await authenticated_client.get(f"{_BASE}{path}")
        assert resp.status_code == 200, f"{path}: {resp.text}"


class TestHealth:
    async def test_health_reports_services(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.get(f"{_BASE}/health")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] in {"healthy", "degraded"}
        assert isinstance(body["services"], dict)
        assert body["services"]  # at least one service reported
