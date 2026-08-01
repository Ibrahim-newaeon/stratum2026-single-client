# =============================================================================
# ADs Growth System - OAuth Credential Injection Tests
# =============================================================================
"""Factory injects resolved credentials; authorize returns typed 400."""

import pytest

from app.services.oauth.base import OAuthState
from app.services.oauth.credentials import AppCredentials, CredentialsNotConfigured
from app.services.oauth.factory import get_oauth_service


def _creds(platform: str) -> AppCredentials:
    return AppCredentials(
        platform=platform,
        client_id="cid-123",
        client_secret="sec-456",
        developer_token="dev-789" if platform == "google" else None,
        source="database",
    )


def _state(platform: str) -> OAuthState:
    return OAuthState(
        state_token="s" * 32,
        user_id=1,
        platform=platform,
        redirect_uri="https://app.example.com/connect",
    )


def test_factory_returns_fresh_instances() -> None:
    a = get_oauth_service("meta")
    b = get_oauth_service("meta")
    assert a is not b  # singleton cache removed - per-request credentials


def test_meta_apply_credentials_sets_app_fields() -> None:
    svc = get_oauth_service("meta", credentials=_creds("meta"))
    assert svc.app_id == "cid-123"
    assert svc.app_secret == "sec-456"


def test_google_apply_credentials_sets_client_and_dev_token() -> None:
    svc = get_oauth_service("google", credentials=_creds("google"))
    assert svc.client_id == "cid-123"
    assert svc.client_secret == "sec-456"
    assert svc.developer_token == "dev-789"


def test_tiktok_apply_credentials_sets_app_fields() -> None:
    svc = get_oauth_service("tiktok", credentials=_creds("tiktok"))
    assert svc.app_id == "cid-123"
    assert svc.app_secret == "sec-456"


def test_snapchat_apply_credentials_sets_client_fields() -> None:
    svc = get_oauth_service("snapchat", credentials=_creds("snapchat"))
    assert svc.client_id == "cid-123"
    assert svc.client_secret == "sec-456"


@pytest.mark.parametrize("platform", ["meta", "google", "tiktok", "snapchat"])
def test_all_services_accept_credentials(platform: str) -> None:
    svc = get_oauth_service(platform, credentials=_creds(platform))
    # Every service must expose the injected values through whatever
    # attribute names it uses internally; verify via authorization URL
    # construction not raising the "not configured" ValueError.
    state = _state(platform)
    url = svc.get_authorization_url(state)
    assert "cid-123" in url


def test_no_credentials_falls_back_to_env_configured_attrs() -> None:
    # credentials=None (the default) must not raise - services read
    # settings in __init__ exactly as before this change.
    svc = get_oauth_service("meta")
    assert svc.platform == "meta"


# =============================================================================
# Callback redirect when credentials are unconfigured (not a raw 400)
# =============================================================================
# GET /oauth/{platform}/callback is reached by a BROWSER redirect from the ad
# platform, not an API caller. A JSON 400 would strand the user on a blank
# error page instead of the frontend's /connect error banner - every other
# failure branch in that endpoint redirects, so unconfigured app credentials
# must too (see app/api/v1/endpoints/oauth.py::oauth_callback).


async def test_callback_redirects_when_credentials_not_configured(
    api_client, monkeypatch
) -> None:
    import app.api.v1.endpoints.oauth as oauth_ep

    async def _raise(platform: str, db):
        raise CredentialsNotConfigured(platform)

    monkeypatch.setattr(oauth_ep, "resolve_app_credentials", _raise)

    resp = await api_client.get(
        "/api/v1/oauth/meta/callback",
        params={"code": "authcode", "state": "some-state-token"},
        follow_redirects=False,
    )

    assert resp.status_code in (302, 307)
    location = resp.headers["location"]
    assert "error=credentials_not_configured" in location
    assert "platform=meta" in location
    assert "/connect" in location
