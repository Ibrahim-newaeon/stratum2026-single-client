# =============================================================================
# Stratum AI - Console Credentials Health Source Tests
# =============================================================================
"""GET /console/credentials/health reports where each ad_platform credential
came from: a DB-stored PlatformAppCredential row ("database"), an env var
("environment"), or nothing configured (null)."""

from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_requires_owner(api_client, admin_headers) -> None:
    resp = await api_client.get(
        "/api/v1/console/credentials/health",
        headers=admin_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_db_row_marks_source_database_and_presence_true(
    api_client, owner_headers, mock_db
) -> None:
    """A DB-stored meta credential should report source=database and flip
    the presence booleans to True even when no env vars are set."""
    meta_row = MagicMock(platform="meta")
    result = MagicMock()
    result.scalars.return_value.all.return_value = [meta_row]
    mock_db.execute.return_value = result

    resp = await api_client.get(
        "/api/v1/console/credentials/health",
        headers=owner_headers,
    )
    assert resp.status_code == 200
    ad_platforms = resp.json()["data"]["ad_platforms"]

    meta = ad_platforms["meta"]
    assert meta["source"] == "database"
    assert meta["app_id"] is True
    assert meta["app_secret"] is True

    # Untouched platforms fall back to env-based presence (no env configured
    # in this test process) and a null source.
    google = ad_platforms["google_ads"]
    assert google["source"] is None


@pytest.mark.asyncio
async def test_no_db_rows_leaves_source_null_when_env_unset(
    api_client, owner_headers, mock_db
) -> None:
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = result

    resp = await api_client.get(
        "/api/v1/console/credentials/health",
        headers=owner_headers,
    )
    assert resp.status_code == 200
    ad_platforms = resp.json()["data"]["ad_platforms"]
    for platform in ("meta", "google_ads", "tiktok", "snapchat"):
        assert ad_platforms[platform]["source"] is None
