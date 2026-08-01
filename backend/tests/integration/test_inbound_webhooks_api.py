# =============================================================================
# ADs Growth System - Inbound Webhook Endpoint Integration Tests
# =============================================================================
"""Integration tests for the unauthenticated inbound webhook receiver:

- ``POST /api/v1/webhooks/sendgrid`` — SendGrid Event Webhook. Verified by a URL
  ``?token=`` matched (constant-time) against ``sendgrid_webhook_token``.

This pins the token verification contract — the security-critical branch —
without needing live SendGrid credentials.

NOTE: run with the session-scoped event loop CI uses
(``-o asyncio_default_test_loop_scope=session``).
"""

import pytest
from httpx import AsyncClient

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

_SENDGRID = "/api/v1/webhooks/sendgrid"


class TestSendgridWebhook:
    async def test_wrong_token_401(self, client: AsyncClient, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(
            settings, "sendgrid_webhook_token", "sg_secret", raising=False
        )
        # No token query param -> verification fails.
        resp = await client.post(_SENDGRID, json=[])
        assert resp.status_code == 401, resp.text

    async def test_valid_token_empty_batch_ok(self, client: AsyncClient, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(
            settings, "sendgrid_webhook_token", "sg_secret", raising=False
        )
        resp = await client.post(f"{_SENDGRID}?token=sg_secret", json=[])
        assert resp.status_code == 200, resp.text

    async def test_valid_token_non_list_400(self, client: AsyncClient, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(
            settings, "sendgrid_webhook_token", "sg_secret", raising=False
        )
        # SendGrid posts a JSON array; an object should be rejected.
        resp = await client.post(f"{_SENDGRID}?token=sg_secret", json={"not": "a list"})
        assert resp.status_code == 400, resp.text
