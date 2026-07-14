# =============================================================================
# Stratum AI - Webhook Subscription (admin) Endpoint Integration Tests
# =============================================================================
"""Integration tests for the super-admin webhook-subscription management API
under ``/api/v1/webhooks``. Every route is gated by ``require_owner``.
"""

import pytest
from httpx import AsyncClient

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

_BASE = "/api/v1/webhooks"


class TestGate:
    async def test_unauthenticated_forbidden(self, client: AsyncClient):
        resp = await client.get(_BASE)
        assert resp.status_code in {401, 403}

    async def test_non_owner_denied(self, authenticated_client: AsyncClient):
        # A regular ADMIN is not a super admin -> require_owner rejects it.
        resp = await authenticated_client.get(_BASE)
        assert resp.status_code in {401, 403}


class TestOwnerReads:
    async def test_list_webhooks_empty(self, client: AsyncClient, owner_headers):
        resp = await client.get(_BASE, headers=owner_headers)
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"] == []
