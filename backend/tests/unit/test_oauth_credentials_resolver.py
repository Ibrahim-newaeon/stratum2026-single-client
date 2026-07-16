"""resolve_app_credentials: DB row wins, env falls back, else typed error."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.oauth.credentials import (
    AppCredentials,
    CredentialsNotConfigured,
    credentials_message,
    resolve_app_credentials,
)


def _db_returning(row: object | None) -> AsyncMock:
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = row
    db.execute.return_value = result
    return db


@pytest.mark.asyncio
async def test_db_row_wins_over_env(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "meta_app_id", "env-id")
    monkeypatch.setattr(settings, "meta_app_secret", "env-secret")
    row = MagicMock(
        platform="meta",
        client_id="db-id",
        client_secret="db-secret",
        developer_token=None,
    )
    creds = await resolve_app_credentials("meta", _db_returning(row))
    assert creds == AppCredentials(
        platform="meta",
        client_id="db-id",
        client_secret="db-secret",
        developer_token=None,
        source="database",
    )


@pytest.mark.asyncio
async def test_env_fallback_when_no_db_row(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "google_ads_client_id", "g-id")
    monkeypatch.setattr(settings, "google_ads_client_secret", "g-secret")
    monkeypatch.setattr(settings, "google_ads_developer_token", "g-dev")
    creds = await resolve_app_credentials("google", _db_returning(None))
    assert creds.source == "environment"
    assert creds.client_id == "g-id"
    assert creds.developer_token == "g-dev"


@pytest.mark.asyncio
async def test_raises_typed_error_when_nothing_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "tiktok_app_id", None)
    monkeypatch.setattr(settings, "tiktok_secret", None)
    with pytest.raises(CredentialsNotConfigured) as exc:
        await resolve_app_credentials("tiktok", _db_returning(None))
    assert exc.value.platform == "tiktok"


def test_message_names_the_platform_and_the_fix() -> None:
    msg = credentials_message("meta")
    assert "Meta app credentials are not configured" in msg
    assert "Settings → Integrations" in msg


@pytest.mark.asyncio
async def test_unknown_platform_raises() -> None:
    with pytest.raises(CredentialsNotConfigured):
        await resolve_app_credentials("myspace", _db_returning(None))
