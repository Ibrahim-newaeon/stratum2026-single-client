# =============================================================================
# Stratum AI - Platform Credentials CRUD API Tests
# =============================================================================
"""Platform credentials CRUD: role gate, secret masking, keep-secret update."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models import AuditAction, AuditLog


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


@pytest.mark.asyncio
async def test_put_update_keeps_stored_secret_when_omitted(
    api_client, admin_headers, mock_db
) -> None:
    """When updating an existing credential without providing client_secret,
    the stored secret should be preserved."""
    # Mock existing row with stored secret
    existing_row = MagicMock(
        platform="meta",
        client_id="old",
        client_secret="stored-secret",
        developer_token=None,
    )
    result = MagicMock()
    result.scalar_one_or_none.return_value = existing_row
    mock_db.execute.return_value = result

    resp = await api_client.put(
        "/api/v1/platform-credentials/meta",
        json={"client_id": "new-cid"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    # Assert the secret was NOT updated (still equals stored value)
    assert existing_row.client_secret == "stored-secret"
    # Assert client_id was updated
    assert existing_row.client_id == "new-cid"


@pytest.mark.asyncio
async def test_put_adds_audit_log_row(api_client, admin_headers, mock_db) -> None:
    """A successful PUT should add an AuditLog to db.add."""
    # Mock: no existing row (create path)
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = result

    resp = await api_client.put(
        "/api/v1/platform-credentials/meta",
        json={"client_id": "cid-1", "client_secret": "secret-123"},
        headers=admin_headers,
    )
    assert resp.status_code == 200

    # Check that db.add was called with an AuditLog
    audit_logs = [
        call[0][0]
        for call in mock_db.add.call_args_list
        if isinstance(call[0][0], AuditLog)
    ]
    assert len(audit_logs) > 0, "No AuditLog was added"
    audit_log = audit_logs[0]
    assert audit_log.resource_type == "platform_app_credential"
    assert audit_log.action == AuditAction.CREATE


@pytest.mark.asyncio
async def test_delete_removes_row_and_audits(
    api_client, admin_headers, mock_db
) -> None:
    """DELETE should remove the row and add an audit log with DELETE action."""
    # Mock existing row
    existing_row = MagicMock(platform="meta")
    result = MagicMock()
    result.scalar_one_or_none.return_value = existing_row
    mock_db.execute.return_value = result

    resp = await api_client.delete(
        "/api/v1/platform-credentials/meta",
        headers=admin_headers,
    )
    assert resp.status_code == 200

    # Assert db.delete was called with the row
    mock_db.delete.assert_called()
    deleted_row = mock_db.delete.call_args[0][0]
    assert deleted_row.platform == "meta"

    # Check that an AuditLog with DELETE action was added
    audit_logs = [
        call[0][0]
        for call in mock_db.add.call_args_list
        if isinstance(call[0][0], AuditLog)
    ]
    assert len(audit_logs) > 0, "No AuditLog was added"
    audit_log = audit_logs[0]
    assert audit_log.action == AuditAction.DELETE
    assert audit_log.resource_type == "platform_app_credential"


@pytest.mark.asyncio
async def test_delete_404_when_no_row(api_client, admin_headers, mock_db) -> None:
    """DELETE should return 404 when no credentials exist for the platform."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = result

    resp = await api_client.delete(
        "/api/v1/platform-credentials/meta",
        headers=admin_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_requires_admin(api_client, viewer_headers) -> None:
    """DELETE should require admin role."""
    resp = await api_client.delete(
        "/api/v1/platform-credentials/meta",
        headers=viewer_headers,
    )
    assert resp.status_code == 403
