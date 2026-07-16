# =============================================================================
# Stratum AI - Platform Credentials CRUD API Tests
# =============================================================================
"""Platform credentials CRUD: role gate, secret masking, keep-secret update."""

from unittest.mock import MagicMock

import pytest


@pytest.mark.asyncio
async def test_list_requires_admin(api_client, viewer_headers) -> None:
    resp = await api_client.get(
        "/api/v1/platform-credentials",
        headers=viewer_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_returns_all_platforms_and_never_secrets(
    api_client, admin_headers, mock_db
) -> None:
    row = MagicMock(
        platform="meta",
        client_id="cid-1",
        client_secret="SHOULD-NEVER-APPEAR",
        developer_token=None,
    )
    result = MagicMock()
    result.scalars.return_value.all.return_value = [row]
    mock_db.execute.return_value = result

    resp = await api_client.get(
        "/api/v1/platform-credentials",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    platforms = {item["platform"] for item in body["data"]}
    assert platforms == {"meta", "google", "tiktok", "snapchat"}
    assert "SHOULD-NEVER-APPEAR" not in resp.text
    meta = next(i for i in body["data"] if i["platform"] == "meta")
    assert meta["configured"] is True
    assert meta["source"] == "database"
    assert meta["client_id"] == "cid-1"
    assert "/api/v1/oauth/meta/callback" in meta["callback_url"]


@pytest.mark.asyncio
async def test_put_unknown_platform_is_422(api_client, admin_headers) -> None:
    resp = await api_client.put(
        "/api/v1/platform-credentials/myspace",
        json={"client_id": "x", "client_secret": "y"},
        headers=admin_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_put_create_requires_secret(api_client, admin_headers, mock_db) -> None:
    result = MagicMock()
    result.scalar_one_or_none.return_value = None  # no existing row
    mock_db.execute.return_value = result
    resp = await api_client.put(
        "/api/v1/platform-credentials/meta",
        json={"client_id": "cid-1"},
        headers=admin_headers,
    )
    assert resp.status_code == 422
