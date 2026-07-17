# =============================================================================
# Stratum AI - Onboarding Role Gate Tests
# =============================================================================
"""Onboarding writes are owner/admin-only; reads stay open (guard uses them)."""

import pytest

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_viewer_cannot_write_onboarding(api_client, viewer_headers) -> None:
    resp = await api_client.post(
        "/api/v1/onboarding/skip",
        headers=viewer_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_viewer_can_read_onboarding_check(
    api_client, viewer_headers, mock_db
) -> None:
    resp = await api_client.get(
        "/api/v1/onboarding/check",
        headers=viewer_headers,
    )
    assert resp.status_code == 200
