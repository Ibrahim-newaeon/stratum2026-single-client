# =============================================================================
# ADs Growth System - ML router authorization test (ML-003)
# =============================================================================
"""
The /ml router (model upload / train / delete) operates on the GLOBAL model
registry and was completely unauthenticated. It must now require owner.

Tested behaviorally through the api_client fixture (a fresh app with real
auth middleware + the api_router mounted): a non-owner is rejected, an
owner is let through, and an unauthenticated request is refused. This is
more robust than inspecting router internals, which are sensitive to test
import order / shared-app mutation across the suite.
"""

import pytest

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_ml_models_rejects_non_owner(api_client, admin_headers):
    # An org admin (role != owner) must be forbidden.
    resp = await api_client.get("/api/v1/ml/models", headers=admin_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_ml_models_allows_owner(api_client, owner_headers):
    # An owner passes the gate (whatever the handler then returns, it is
    # not an auth rejection).
    resp = await api_client.get("/api/v1/ml/models", headers=owner_headers)
    assert resp.status_code not in (401, 403)


@pytest.mark.asyncio
async def test_ml_upload_rejects_unauthenticated(api_client):
    resp = await api_client.post("/api/v1/ml/upload")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_ml_delete_rejects_non_owner(api_client, admin_headers):
    resp = await api_client.delete(
        "/api/v1/ml/models/roas_predictor", headers=admin_headers
    )
    assert resp.status_code == 403
