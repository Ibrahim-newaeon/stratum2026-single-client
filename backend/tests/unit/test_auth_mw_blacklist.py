# =============================================================================
# Stratum AI - AuthContextMiddleware token enforcement tests (AUTH-001)
# =============================================================================
"""
Ported from test_tenant_mw_blacklist.py (STRAT-SC-001 Task C2): TenantMiddleware
is replaced by AuthContextMiddleware, which keeps the JWT decode + AUTH-001
token-type/blacklist enforcement but drops all tenant extraction. These tests
pin the same enforcement behavior against the new middleware, plus the public
endpoint bypass (previously untested at the unit level for this file).
"""

from unittest.mock import AsyncMock, patch

import pytest
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.security import create_access_token, create_refresh_token
from app.middleware.auth_context import AuthContextMiddleware


def _request(token: str | None, path: str = "/api/v1/campaigns") -> Request:
    headers = []
    if token is not None:
        headers.append((b"authorization", f"Bearer {token}".encode()))
    scope = {
        "type": "http",
        "method": "GET",
        "path": path,
        "headers": headers,
        "query_string": b"",
    }
    return Request(scope)


def _mw() -> AuthContextMiddleware:
    return AuthContextMiddleware(app=AsyncMock())


async def _call_next(_request):
    return Response(status_code=200)


@pytest.mark.asyncio
async def test_revoked_access_token_rejected():
    """Case 1: a blacklisted (revoked) access token -> 401."""
    token = create_access_token(subject=9, additional_claims={"role": "admin"})
    call_next = AsyncMock(side_effect=_call_next)
    with patch(
        "app.core.security.is_token_blacklisted", new=AsyncMock(return_value=True)
    ):
        resp = await _mw().dispatch(_request(token), call_next)
    assert isinstance(resp, JSONResponse)
    assert resp.status_code == 401
    call_next.assert_not_awaited()


@pytest.mark.asyncio
async def test_refresh_token_rejected_even_when_redis_down():
    """Case 2: a refresh-type token on an API route -> 401, even when the
    blacklist check would be unreachable (Redis down). Token-type rejection
    happens before the blacklist lookup, so it must not depend on Redis."""
    token = create_refresh_token(subject=9)
    call_next = AsyncMock(side_effect=_call_next)
    with patch(
        "app.core.security.is_token_blacklisted",
        new=AsyncMock(side_effect=ConnectionError("redis down")),
    ):
        resp = await _mw().dispatch(_request(token), call_next)
    assert isinstance(resp, JSONResponse)
    assert resp.status_code == 401
    call_next.assert_not_awaited()


@pytest.mark.asyncio
async def test_redis_outage_fails_open_for_valid_access_token():
    """Case 3: Redis down + a valid (non-revoked) access token -> request
    passes. A blacklist outage must not become a total auth outage."""
    token = create_access_token(subject=9, additional_claims={"role": "admin"})
    call_next = AsyncMock(side_effect=_call_next)
    with patch(
        "app.core.security.is_token_blacklisted",
        new=AsyncMock(side_effect=ConnectionError("redis down")),
    ):
        resp = await _mw().dispatch(_request(token), call_next)
    assert resp.status_code == 200
    call_next.assert_awaited_once()


@pytest.mark.asyncio
async def test_valid_access_token_passes_through():
    token = create_access_token(subject=9, additional_claims={"role": "admin"})
    call_next = AsyncMock(side_effect=_call_next)
    with patch(
        "app.core.security.is_token_blacklisted", new=AsyncMock(return_value=False)
    ):
        resp = await _mw().dispatch(_request(token), call_next)
    assert resp.status_code == 200
    call_next.assert_awaited_once()


@pytest.mark.asyncio
async def test_public_endpoint_requires_no_auth():
    """Case 4: a public endpoint is let through with no Authorization header
    at all, and never touches the blacklist check."""
    call_next = AsyncMock(side_effect=_call_next)
    with patch(
        "app.core.security.is_token_blacklisted",
        new=AsyncMock(side_effect=AssertionError("must not be called")),
    ):
        resp = await _mw().dispatch(
            _request(None, path="/api/v1/auth/login"), call_next
        )
    assert resp.status_code == 200
    call_next.assert_awaited_once()
