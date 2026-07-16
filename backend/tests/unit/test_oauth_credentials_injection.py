# =============================================================================
# Stratum AI - OAuth Credential Injection Tests
# =============================================================================
"""Factory injects resolved credentials; authorize returns typed 400."""

import pytest

from app.services.oauth.base import OAuthState
from app.services.oauth.credentials import AppCredentials
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
