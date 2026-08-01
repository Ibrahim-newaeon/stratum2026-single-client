# =============================================================================
# ADs Growth System - Owner Console Endpoint Integration Tests
# =============================================================================
"""Integration tests for the platform Owner API under
``/api/v1/console/...``: system health, audit log, dashboard, credentials
health, and anomaly rollup reads. Every route is gated by the local
``require_owner`` dependency (reads ``request.state.role``/``user_id``).

STRAT-SC-001 (Task C6): this file used to cover ``/superadmin/...`` routes
that read the deleted ``Tenant`` model directly (revenue, tenant portfolio,
churn risk, billing plans/invoices/subscriptions) — B1 renamed the router
``/superadmin`` -> ``/console`` and C3 deleted every one of those Tenant-
sourced/billing routes outright (single-org deployment has no MRR, tenant
portfolio, churn, or billing concept). Rewritten against the routes that
actually survive in ``app/api/v1/endpoints/console.py`` today.

NOTE: run with the session-scoped event loop CI uses
(``-o asyncio_default_test_loop_scope=session``).
"""

import pytest
from httpx import AsyncClient

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

_BASE = "/api/v1/console"

_GETS = [
    "/system/health",
    "/audit",
    "/dashboard",
    "/credentials/health",
    "/anomalies-rollup",
]


class TestGate:
    async def test_unauthenticated_denied(self, client: AsyncClient):
        resp = await client.get(f"{_BASE}/audit")
        assert resp.status_code in {401, 403}

    async def test_non_owner_denied(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.get(f"{_BASE}/audit")
        assert resp.status_code in {401, 403}


class TestOwnerReads:
    @pytest.mark.parametrize("path", _GETS)
    async def test_get_returns_200(self, client: AsyncClient, owner_headers, path):
        resp = await client.get(f"{_BASE}{path}", headers=owner_headers)
        assert resp.status_code == 200, f"{path}: {resp.text}"
        assert resp.json()["success"] is True
