# =============================================================================
# ADs Growth System - Onboarding Agent Endpoint Integration Tests
# =============================================================================
"""Integration tests for the conversational onboarding agent under
``/api/v1/onboarding-agent/...``: start, message, status, quick-replies, and
session deletion. The agent (``RootAgent``) is a deterministic rule-based state
machine (no LLM), and sessions are persisted in Redis — both available in the
harness.

NOTE: run with the session-scoped event loop CI uses
(``-o asyncio_default_test_loop_scope=session``).
"""

import pytest
from httpx import AsyncClient

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

_BASE = "/api/v1/onboarding-agent"


async def _start(client: AsyncClient) -> str:
    resp = await client.post(_BASE + "/start", json={"language": "en"})
    assert resp.status_code == 200, resp.text
    return resp.json()["session_id"]


class TestStart:
    async def test_start_works_without_auth(self, client: AsyncClient):
        """STRAT-SC-001 (C6): replaces test_requires_auth. The endpoint uses
        OptionalUserDep BY DESIGN (its docstring: "Can be used with or
        without authentication") — pre-signup onboarding is an anonymous
        flow. Under the old TenantMiddleware the anonymous path was
        unreachable (the middleware 401'd everything not allowlisted), which
        masked the endpoint's own contract; AuthContextMiddleware (C2)
        honors it."""
        resp = await client.post(_BASE + "/start", json={"language": "en"})
        assert resp.status_code == 200, resp.text
        assert resp.json()["session_id"]

    async def test_start_returns_greeting(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.post(
            _BASE + "/start", json={"language": "en", "name": "Ada"}
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["session_id"]
        assert data["message"]
        assert isinstance(data["quick_replies"], list)
        assert 0 <= data["progress_percent"] <= 100


class TestAnonymousSessionAccess:
    """STRAT-AUTH-005: /message and /status take OptionalUserDep so the
    anonymous pre-signup flow can run end to end. Possession of the uuid4
    session_id is therefore the only credential an anonymous caller has, which
    is fine for a session they started themselves — but must NOT reach a
    session created by a signed-in user, or those sessions would silently drop
    from "auth + session_id" to "session_id alone" for the full 24h TTL.
    """

    async def test_anonymous_can_continue_own_session(self, client: AsyncClient):
        """The whole point: start anonymously, then keep talking."""
        session_id = await _start(client)

        msg = await client.post(
            f"{_BASE}/message", json={"session_id": session_id, "message": "Ada"}
        )
        assert msg.status_code == 200, msg.text

        st = await client.get(f"{_BASE}/status/{session_id}")
        assert st.status_code == 200, st.text
        assert st.json()["session_id"] == session_id

    async def test_anonymous_cannot_read_owned_session(
        self, authenticated_client: AsyncClient
    ):
        """404, not 403 — a probe must not learn that the session exists.

        Only ``authenticated_client`` is requested, then its header is
        dropped. The ``authenticated_client`` fixture mutates and returns the
        very same object as ``client`` (conftest sets
        ``client.headers["Authorization"]`` and returns ``client``), so a test
        asking for both fixtures gets one authenticated client twice and its
        "anonymous" leg silently isn't. Both are function-scoped, so mutating
        headers here cannot leak into another test.
        """
        session_id = await _start(authenticated_client)
        authenticated_client.headers.pop("Authorization")

        resp = await authenticated_client.get(f"{_BASE}/status/{session_id}")
        assert resp.status_code == 404, resp.text

    async def test_anonymous_cannot_message_owned_session(
        self, authenticated_client: AsyncClient
    ):
        session_id = await _start(authenticated_client)
        authenticated_client.headers.pop("Authorization")

        resp = await authenticated_client.post(
            f"{_BASE}/message", json={"session_id": session_id, "message": "hijack"}
        )
        assert resp.status_code == 404, resp.text

    async def test_owner_still_reaches_own_session(
        self, authenticated_client: AsyncClient
    ):
        """The guard must not lock owners out of their own sessions."""
        session_id = await _start(authenticated_client)

        st = await authenticated_client.get(f"{_BASE}/status/{session_id}")
        assert st.status_code == 200, st.text

        msg = await authenticated_client.post(
            f"{_BASE}/message", json={"session_id": session_id, "message": "Ada"}
        )
        assert msg.status_code == 200, msg.text


class TestStatus:
    async def test_status_roundtrip(self, authenticated_client: AsyncClient):
        session_id = await _start(authenticated_client)
        resp = await authenticated_client.get(f"{_BASE}/status/{session_id}")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["session_id"] == session_id
        assert "state" in data

    async def test_unknown_session_404(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.get(f"{_BASE}/status/does-not-exist")
        assert resp.status_code == 404


class TestMessage:
    async def test_message_advances_conversation(
        self, authenticated_client: AsyncClient
    ):
        session_id = await _start(authenticated_client)
        resp = await authenticated_client.post(
            _BASE + "/message",
            json={"session_id": session_id, "message": "Get Started"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["message"]
        assert "state" in data
        assert isinstance(data["quick_replies"], list)


class TestQuickReplies:
    async def test_quick_replies_for_state(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.get(f"{_BASE}/quick-replies/greeting")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["state"] == "greeting"
        assert "Get Started" in body["quick_replies"]


class TestSessionDelete:
    async def test_delete_then_status_404(self, authenticated_client: AsyncClient):
        session_id = await _start(authenticated_client)
        deleted = await authenticated_client.delete(f"{_BASE}/session/{session_id}")
        assert deleted.status_code == 200, deleted.text
        gone = await authenticated_client.get(f"{_BASE}/status/{session_id}")
        assert gone.status_code == 404


async def _seed_completed_session() -> str:
    """Persist a fully-walked (COMPLETED) onboarding session to Redis."""
    from uuid import uuid4

    from app.api.v1.endpoints.onboarding_agent import get_redis_client, save_session
    from app.services.agents import (
        ConversationContext,
        ConversationState,
        UserContext,
    )
    from app.services.agents.root_agent import OnboardingData

    session_id = str(uuid4())
    context = ConversationContext(
        session_id=session_id,
        user_context=UserContext(is_new_user=False),
        state=ConversationState.COMPLETED,
        onboarding_data=OnboardingData(
            company_name="Acme Co",
            industry="ecommerce",
            timezone="UTC",
            currency="USD",
            selected_platforms=["meta", "google"],
            healthy_threshold=70,
            degraded_threshold=40,
        ),
    )
    redis = await get_redis_client()
    try:
        await save_session(session_id, context, redis)
    finally:
        await redis.aclose()
    return session_id


class TestComplete:
    async def test_unknown_session_404(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.post(f"{_BASE}/complete/does-not-exist")
        assert resp.status_code == 404

    async def test_not_completed_400(self, authenticated_client: AsyncClient):
        # A freshly-started session is in GREETING, not COMPLETED.
        session_id = await _start(authenticated_client)
        resp = await authenticated_client.post(f"{_BASE}/complete/{session_id}")
        assert resp.status_code == 400, resp.text

    async def test_complete_persists_and_clears_session(
        self, authenticated_client: AsyncClient, db_session, organization
    ):
        session_id = await _seed_completed_session()

        resp = await authenticated_client.post(f"{_BASE}/complete/{session_id}")
        assert resp.status_code == 200, resp.text
        assert resp.json()["success"] is True

        # Collected data was persisted to the Organization singleton.
        from sqlalchemy import select

        from app.base_models import Organization

        row = await db_session.execute(
            select(Organization).where(Organization.id == organization["id"])
        )
        org = row.scalar_one()
        assert org.settings.get("onboarding_completed") is True
        assert org.settings.get("selected_platforms") == ["meta", "google"]

        # Session is cleared after completion.
        gone = await authenticated_client.get(f"{_BASE}/status/{session_id}")
        assert gone.status_code == 404
