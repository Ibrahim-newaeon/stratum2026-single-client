# =============================================================================
# Stratum AI - GDPR / Compliance API Integration Tests
# =============================================================================
"""Integration tests for the GDPR compliance API.

Exercises the real ASGI app against Postgres + Redis: data export (right
to portability), anonymization (right to be forgotten) with the required
confirmation token, consent updates, and the audit-log read — plus auth
and not-found paths.
"""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration

_MISSING = 99999999


@pytest.fixture
def enterprise_plan():
    """No-op (STRAT-SC-001 / Task A1).

    GDPR tools used to be gated behind a tier-aware ``FeatureGate``
    (Enterprise only), so tests elevated the test tenant's tier via a
    ``get_subscription_info`` patch. ``FeatureGate`` is now purely
    env-driven (``Feature.GDPR_TOOLS`` -> ``settings.feature_gdpr_compliance``,
    default True) and no longer looks at tenant/tier at all, so there is
    nothing left to elevate. Kept as a no-op fixture so call sites below
    don't need to change.
    """
    return None


# =============================================================================
# Export (right to data portability)
# =============================================================================
class TestExport:
    @pytest.mark.asyncio
    async def test_requires_auth(self, client: AsyncClient):
        resp = await client.post("/api/v1/gdpr/export", json={"user_id": 1})
        assert resp.status_code in {401, 403}

    # Note: the export happy path decrypts the user's Fernet-encrypted PII;
    # the shared test fixtures store plaintext, so the full export payload is
    # exercised at the unit level. Here we cover the route's auth + not-found
    # contract (the not-found check runs before any decryption).

    @pytest.mark.asyncio
    async def test_export_user_not_found(
        self, authenticated_client: AsyncClient, enterprise_plan
    ):
        resp = await authenticated_client.post(
            "/api/v1/gdpr/export", json={"user_id": _MISSING}
        )
        assert resp.status_code == 404


# =============================================================================
# Anonymize (right to be forgotten)
# =============================================================================
class TestAnonymize:
    @pytest.mark.asyncio
    async def test_invalid_confirmation_rejected(
        self, authenticated_client: AsyncClient, test_user: dict, enterprise_plan
    ):
        # confirmation must match the CONFIRM_DELETE pattern → 422.
        resp = await authenticated_client.post(
            "/api/v1/gdpr/anonymize",
            json={"user_id": test_user["id"], "confirmation": "nope"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_anonymize_user_not_found(
        self, authenticated_client: AsyncClient, enterprise_plan
    ):
        resp = await authenticated_client.post(
            "/api/v1/gdpr/anonymize",
            json={"user_id": _MISSING, "confirmation": "CONFIRM_DELETE"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_anonymize_success(
        self, authenticated_client: AsyncClient, test_user: dict, enterprise_plan
    ):
        resp = await authenticated_client.post(
            "/api/v1/gdpr/anonymize",
            json={"user_id": test_user["id"], "confirmation": "CONFIRM_DELETE"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["user_id"] == test_user["id"]
        assert isinstance(data["tables_affected"], list)


# =============================================================================
# Consent + audit logs
# =============================================================================
class TestConsentAndAudit:
    @pytest.mark.asyncio
    async def test_update_consent(
        self, authenticated_client: AsyncClient, enterprise_plan
    ):
        resp = await authenticated_client.post(
            "/api/v1/gdpr/consent",
            params={"consent_marketing": True, "consent_analytics": False},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["consent_marketing"] is True
        assert data["consent_analytics"] is False

    @pytest.mark.asyncio
    async def test_consent_requires_auth(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/gdpr/consent", params={"consent_marketing": True}
        )
        assert resp.status_code in {401, 403}

    @pytest.mark.asyncio
    async def test_audit_logs_paginated(
        self, authenticated_client: AsyncClient, enterprise_plan
    ):
        resp = await authenticated_client.get("/api/v1/gdpr/audit-logs")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "items" in data
        assert "total" in data
