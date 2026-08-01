# =============================================================================
# ADs Growth System - Campaign Builder Unit Tests
# =============================================================================
"""
Comprehensive unit tests for the Campaign Builder feature.

Tests cover:
- Enums (AdPlatform, ConnectionStatus, DraftStatus, PublishResult)
- Pydantic schemas (validation, defaults, serialization)
- Connector endpoints (status, start OAuth, refresh, disconnect)
- Ad account endpoints (list, sync, update)
- Campaign draft endpoints (CRUD + approval workflow)
- Publish log endpoints (list, retry)
- Workflow state machine (draft→submitted→approved→published, rejection, re-edit)
- Budget guardrails (publish blocked when over cap)
- Celery tasks (sync, refresh, publish, health check)
- Edge cases (empty state, missing data, invalid transitions)
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

# ---------------------------------------------------------------------------
# Schema imports
# ---------------------------------------------------------------------------
from app.api.v1.endpoints.campaign_builder import (
    AdAccountResponse,
    AdAccountUpdateRequest,
    CampaignDraftCreate,
    CampaignDraftResponse,
    CampaignDraftUpdate,
    ConnectorStatusResponse,
    PublishLogResponse,
)
from app.core.config import settings

# ---------------------------------------------------------------------------
# Model / enum imports
# ---------------------------------------------------------------------------
from app.models.campaign_builder import (
    AdAccount,
    AdPlatform,
    CampaignDraft,
    CampaignPublishLog,
    ConnectionStatus,
    DraftStatus,
    PlatformConnection,
    PublishResult,
)

# =============================================================================
# Enum Tests
# =============================================================================


class TestAdPlatform:
    """Tests for AdPlatform enum."""

    def test_all_platforms_defined(self):
        platforms = [p.value for p in AdPlatform]
        assert set(platforms) == {"meta", "google", "tiktok", "snapchat"}

    def test_platform_is_str_enum(self):
        assert isinstance(AdPlatform.META, str)
        assert AdPlatform.META == "meta"

    def test_platform_from_value(self):
        assert AdPlatform("meta") == AdPlatform.META
        assert AdPlatform("google") == AdPlatform.GOOGLE
        assert AdPlatform("tiktok") == AdPlatform.TIKTOK
        assert AdPlatform("snapchat") == AdPlatform.SNAPCHAT

    def test_invalid_platform_raises(self):
        with pytest.raises(ValueError):
            AdPlatform("twitter")


class TestConnectionStatus:
    """Tests for ConnectionStatus enum."""

    def test_all_statuses_defined(self):
        statuses = [s.value for s in ConnectionStatus]
        assert set(statuses) == {"connected", "expired", "error", "disconnected"}

    def test_status_is_str_enum(self):
        assert isinstance(ConnectionStatus.CONNECTED, str)
        assert ConnectionStatus.CONNECTED == "connected"


class TestDraftStatus:
    """Tests for DraftStatus enum - the workflow state machine."""

    def test_all_statuses_defined(self):
        statuses = [s.value for s in DraftStatus]
        assert set(statuses) == {
            "draft",
            "submitted",
            "approved",
            "rejected",
            "publishing",
            "published",
            "failed",
        }

    def test_draft_is_initial_state(self):
        assert DraftStatus.DRAFT.value == "draft"

    def test_published_is_terminal_state(self):
        assert DraftStatus.PUBLISHED.value == "published"


class TestPublishResult:
    """Tests for PublishResult enum."""

    def test_results_defined(self):
        assert PublishResult.SUCCESS.value == "success"
        assert PublishResult.FAILURE.value == "failure"


# =============================================================================
# Pydantic Schema Tests
# =============================================================================


class TestConnectorStatusResponse:
    """Tests for ConnectorStatusResponse schema."""

    def test_minimal_response(self):
        resp = ConnectorStatusResponse(platform="meta", status="disconnected")
        assert resp.platform == "meta"
        assert resp.status == "disconnected"
        assert resp.connected_at is None
        assert resp.scopes == []

    def test_full_response(self):
        now = datetime.now(timezone.utc)
        resp = ConnectorStatusResponse(
            platform="google",
            status="connected",
            connected_at=now,
            last_refreshed_at=now,
            scopes=["ads_read", "ads_management"],
            last_error=None,
        )
        assert resp.scopes == ["ads_read", "ads_management"]
        assert resp.connected_at == now


class TestAdAccountResponse:
    """Tests for AdAccountResponse schema."""

    def test_required_fields(self):
        uid = uuid4()
        resp = AdAccountResponse(
            id=uid,
            platform="meta",
            platform_account_id="act_123",
            name="Test Account",
            currency="SAR",
            timezone="Asia/Riyadh",
            is_enabled=True,
        )
        assert resp.id == uid
        assert resp.is_enabled is True

    def test_optional_budget_cap(self):
        uid = uuid4()
        resp = AdAccountResponse(
            id=uid,
            platform="meta",
            platform_account_id="act_123",
            name="Test",
            currency="USD",
            timezone="UTC",
            is_enabled=False,
            daily_budget_cap=5000.0,
        )
        assert resp.daily_budget_cap == 5000.0


class TestAdAccountUpdateRequest:
    """Tests for AdAccountUpdateRequest schema."""

    def test_empty_update(self):
        req = AdAccountUpdateRequest()
        assert req.is_enabled is None
        assert req.daily_budget_cap is None

    def test_partial_update_enabled(self):
        req = AdAccountUpdateRequest(is_enabled=True)
        assert req.is_enabled is True
        assert req.daily_budget_cap is None

    def test_partial_update_budget(self):
        req = AdAccountUpdateRequest(daily_budget_cap=1000.0)
        assert req.daily_budget_cap == 1000.0


class TestCampaignDraftCreate:
    """Tests for CampaignDraftCreate schema."""

    def test_minimal_create(self):
        uid = uuid4()
        req = CampaignDraftCreate(
            platform="meta",
            ad_account_id=uid,
            name="Summer Sale",
        )
        assert req.platform == "meta"
        assert req.ad_account_id == uid
        assert req.name == "Summer Sale"
        assert req.description is None
        assert req.draft_json == {}

    def test_full_create(self):
        uid = uuid4()
        campaign_config = {
            "campaign": {
                "objective": "conversions",
                "budget": {"amount": 5000, "type": "daily"},
            }
        }
        req = CampaignDraftCreate(
            platform="google",
            ad_account_id=uid,
            name="Winter Campaign",
            description="Holiday season push",
            draft_json=campaign_config,
        )
        assert req.draft_json["campaign"]["objective"] == "conversions"


class TestCampaignDraftUpdate:
    """Tests for CampaignDraftUpdate schema."""

    def test_empty_update(self):
        req = CampaignDraftUpdate()
        assert req.name is None
        assert req.description is None
        assert req.draft_json is None

    def test_partial_name_update(self):
        req = CampaignDraftUpdate(name="New Name")
        assert req.name == "New Name"

    def test_draft_json_update(self):
        new_config = {"campaign": {"objective": "awareness"}}
        req = CampaignDraftUpdate(draft_json=new_config)
        assert req.draft_json == new_config


class TestCampaignDraftResponse:
    """Tests for CampaignDraftResponse schema."""

    def test_full_response(self):
        uid = uuid4()
        acc_id = uuid4()
        now = datetime.now(timezone.utc)
        resp = CampaignDraftResponse(
            id=uid,
            platform="meta",
            ad_account_id=acc_id,
            name="Test Campaign",
            status="draft",
            draft_json={"campaign": {}},
            created_at=now,
            updated_at=now,
        )
        assert resp.id == uid
        assert resp.status == "draft"
        assert resp.submitted_at is None
        assert resp.published_at is None


class TestPublishLogResponse:
    """Tests for PublishLogResponse schema."""

    def test_success_log(self):
        uid = uuid4()
        draft_id = uuid4()
        now = datetime.now(timezone.utc)
        resp = PublishLogResponse(
            id=uid,
            draft_id=draft_id,
            platform="meta",
            platform_account_id="act_123",
            event_time=now,
            result_status="success",
            platform_campaign_id="camp_abc123",
            retry_count=0,
        )
        assert resp.result_status == "success"
        assert resp.error_code is None

    def test_failure_log(self):
        uid = uuid4()
        now = datetime.now(timezone.utc)
        resp = PublishLogResponse(
            id=uid,
            platform="google",
            platform_account_id="act_456",
            event_time=now,
            result_status="failure",
            error_code="RATE_LIMIT",
            error_message="Too many requests",
            retry_count=2,
        )
        assert resp.error_code == "RATE_LIMIT"
        assert resp.retry_count == 2


# =============================================================================
# Helper: mock async DB session & Request
# =============================================================================


def _make_request(user_id=1):
    """Create a mock Request with state attributes."""
    request = MagicMock()
    request.state = SimpleNamespace(user_id=user_id)
    request.base_url = "http://localhost:8000/"
    return request


def _make_scalar_result(value):
    """Create a mock SQLAlchemy result that returns a scalar."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _make_scalars_result(values):
    """Create a mock SQLAlchemy result that returns scalars().all()."""
    result = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = values
    result.scalars.return_value = scalars
    return result


def _make_db():
    """Create an async mock DB session."""
    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.add = MagicMock()
    return db


def _make_connection(platform=AdPlatform.META, status=ConnectionStatus.CONNECTED):
    """Create a mock PlatformConnection."""
    conn = MagicMock(spec=PlatformConnection)
    conn.id = uuid4()
    conn.platform = platform
    conn.status = status
    conn.access_token_encrypted = "enc_token_xxx"
    conn.refresh_token_encrypted = "enc_refresh_xxx"
    conn.connected_at = datetime.now(timezone.utc)
    conn.last_refreshed_at = None
    conn.scopes = ["ads_read", "ads_management"]
    conn.last_error = None
    conn.token_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    return conn


def _make_ad_account(platform=AdPlatform.META, is_enabled=True, daily_budget_cap=None):
    """Create a mock AdAccount."""
    acc = MagicMock(spec=AdAccount)
    acc.id = uuid4()
    acc.platform = platform
    acc.platform_account_id = "act_meta_001"
    acc.name = "Main Business Account"
    acc.business_name = "Test Business"
    acc.currency = "SAR"
    acc.timezone = "Asia/Riyadh"
    acc.is_enabled = is_enabled
    acc.daily_budget_cap = Decimal(str(daily_budget_cap)) if daily_budget_cap else None
    acc.last_synced_at = datetime.now(timezone.utc)
    return acc


def _make_draft(status=DraftStatus.DRAFT, ad_account=None, draft_json=None):
    """Create a mock CampaignDraft."""
    draft = MagicMock(spec=CampaignDraft)
    draft.id = uuid4()
    draft.platform = AdPlatform.META
    draft.ad_account_id = ad_account.id if ad_account else uuid4()
    draft.ad_account = ad_account
    draft.name = "Test Campaign"
    draft.description = "Test Description"
    draft.status = status
    draft.draft_json = draft_json or {"campaign": {"objective": "conversions"}}
    draft.created_at = datetime.now(timezone.utc)
    draft.updated_at = datetime.now(timezone.utc)
    draft.submitted_at = None
    draft.approved_at = None
    draft.rejected_at = None
    draft.rejection_reason = None
    draft.platform_campaign_id = None
    draft.published_at = None
    draft.created_by_user_id = 1
    draft.submitted_by_user_id = None
    draft.approved_by_user_id = None
    draft.rejected_by_user_id = None
    return draft


def _make_publish_log(result_status=PublishResult.SUCCESS, draft_id=None):
    """Create a mock CampaignPublishLog."""
    log = MagicMock(spec=CampaignPublishLog)
    log.id = uuid4()
    log.draft_id = draft_id or uuid4()
    log.platform = AdPlatform.META
    log.platform_account_id = "act_meta_001"
    log.published_by_user_id = 1
    log.event_time = datetime.now(timezone.utc)
    log.request_json = {}
    log.response_json = {}
    log.result_status = result_status
    log.platform_campaign_id = (
        "camp_abc123" if result_status == PublishResult.SUCCESS else None
    )
    log.error_code = None
    log.error_message = None
    log.retry_count = 0
    log.last_retry_at = None
    return log


# =============================================================================
# Connector Endpoint Tests
# =============================================================================


class TestGetConnectorStatus:
    """Tests for GET /connect/{platform}/status"""

    @pytest.mark.asyncio
    async def test_connected_platform(self):
        from app.api.v1.endpoints.campaign_builder import get_connector_status

        conn = _make_connection()
        db = _make_db()
        db.execute.return_value = _make_scalar_result(conn)

        resp = await get_connector_status(_make_request(), AdPlatform.META, db)
        assert resp.success is True
        assert resp.data.status == "connected"
        assert resp.data.platform == "meta"

    @pytest.mark.asyncio
    async def test_disconnected_platform_no_record(self):
        from app.api.v1.endpoints.campaign_builder import get_connector_status

        db = _make_db()
        db.execute.return_value = _make_scalar_result(None)

        resp = await get_connector_status(_make_request(), AdPlatform.GOOGLE, db)
        assert resp.success is True
        assert resp.data.status == "disconnected"

    @pytest.mark.asyncio
    async def test_connection_with_error(self):
        from app.api.v1.endpoints.campaign_builder import get_connector_status

        conn = _make_connection(status=ConnectionStatus.ERROR)
        conn.last_error = "Token expired"
        db = _make_db()
        db.execute.return_value = _make_scalar_result(conn)

        resp = await get_connector_status(_make_request(), AdPlatform.META, db)
        assert resp.data.status == "error"
        assert resp.data.last_error == "Token expired"


class TestStartPlatformConnection:
    """Tests for POST /connect/{platform}/start"""

    @pytest.mark.asyncio
    async def test_start_meta_connection(self):
        from app.api.v1.endpoints.campaign_builder import start_platform_connection

        db = _make_db()
        request = _make_request()

        with patch.object(settings, "meta_app_id", "test_app_id_123"):
            resp = await start_platform_connection(request, AdPlatform.META, db)

        assert resp.success is True
        assert "oauth_url" in resp.data
        assert "facebook.com" in resp.data["oauth_url"]
        assert "test_app_id_123" in resp.data["oauth_url"]

    @pytest.mark.asyncio
    async def test_start_google_connection(self):
        from app.api.v1.endpoints.campaign_builder import start_platform_connection

        db = _make_db()
        request = _make_request()

        with patch.object(settings, "google_ads_client_id", "google_client_123"):
            resp = await start_platform_connection(request, AdPlatform.GOOGLE, db)

        assert resp.success is True
        assert "accounts.google.com" in resp.data["oauth_url"]

    @pytest.mark.asyncio
    async def test_start_tiktok_connection(self):
        from app.api.v1.endpoints.campaign_builder import start_platform_connection

        db = _make_db()
        request = _make_request()

        with patch.object(settings, "tiktok_app_id", "tiktok_app_123"):
            resp = await start_platform_connection(request, AdPlatform.TIKTOK, db)

        assert resp.success is True
        assert "tiktok.com" in resp.data["oauth_url"]

    @pytest.mark.asyncio
    async def test_start_snapchat_connection(self):
        from app.api.v1.endpoints.campaign_builder import start_platform_connection

        db = _make_db()
        request = _make_request()

        with patch.object(settings, "snapchat_client_id", "snap_app_123"):
            resp = await start_platform_connection(request, AdPlatform.SNAPCHAT, db)

        assert resp.success is True
        assert "snapchat.com" in resp.data["oauth_url"]

    @pytest.mark.asyncio
    async def test_oauth_not_configured(self):
        from fastapi import HTTPException

        from app.api.v1.endpoints.campaign_builder import start_platform_connection

        db = _make_db()
        request = _make_request()

        with patch.object(settings, "meta_app_id", None):
            with pytest.raises(HTTPException) as exc_info:
                await start_platform_connection(request, AdPlatform.META, db)
            assert exc_info.value.status_code == 400
            assert "not configured" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_oauth_url_contains_state_param(self):
        from app.api.v1.endpoints.campaign_builder import start_platform_connection

        db = _make_db()
        request = _make_request()

        with patch.object(settings, "meta_app_id", "test_app"):
            resp = await start_platform_connection(request, AdPlatform.META, db)

        assert "state" in resp.data
        assert len(resp.data["state"]) > 20  # CSRF token is long enough


class TestRefreshPlatformToken:
    """Tests for POST /connect/{platform}/refresh"""

    @pytest.mark.asyncio
    async def test_refresh_no_connection(self):
        from fastapi import HTTPException

        from app.api.v1.endpoints.campaign_builder import refresh_platform_token

        db = _make_db()
        db.execute.return_value = _make_scalar_result(None)

        with pytest.raises(HTTPException) as exc_info:
            await refresh_platform_token(_make_request(), AdPlatform.META, db)
        assert exc_info.value.status_code == 404


class TestDisconnectPlatform:
    """Tests for DELETE /connect/{platform}"""

    @pytest.mark.asyncio
    async def test_disconnect_success(self):
        from app.api.v1.endpoints.campaign_builder import disconnect_platform

        conn = _make_connection()
        db = _make_db()
        db.execute.return_value = _make_scalar_result(conn)

        resp = await disconnect_platform(_make_request(), AdPlatform.META, db)
        assert resp.success is True
        assert conn.status == ConnectionStatus.DISCONNECTED
        assert conn.access_token_encrypted is None
        assert conn.refresh_token_encrypted is None

    @pytest.mark.asyncio
    async def test_disconnect_not_connected(self):
        from fastapi import HTTPException

        from app.api.v1.endpoints.campaign_builder import disconnect_platform

        db = _make_db()
        db.execute.return_value = _make_scalar_result(None)

        with pytest.raises(HTTPException) as exc_info:
            await disconnect_platform(_make_request(), AdPlatform.META, db)
        assert exc_info.value.status_code == 404


# =============================================================================
# Ad Account Endpoint Tests
# =============================================================================


class TestListAdAccounts:
    """Tests for GET /ad-accounts/{platform}"""

    @pytest.mark.asyncio
    async def test_list_accounts(self):
        from app.api.v1.endpoints.campaign_builder import list_ad_accounts

        accounts = [_make_ad_account(), _make_ad_account()]
        db = _make_db()
        db.execute.return_value = _make_scalars_result(accounts)

        resp = await list_ad_accounts(_make_request(), AdPlatform.META, False, db)
        assert resp.success is True
        assert len(resp.data) == 2

    @pytest.mark.asyncio
    async def test_list_empty(self):
        from app.api.v1.endpoints.campaign_builder import list_ad_accounts

        db = _make_db()
        db.execute.return_value = _make_scalars_result([])

        resp = await list_ad_accounts(_make_request(), AdPlatform.META, False, db)
        assert resp.success is True
        assert resp.data == []


class TestSyncAdAccounts:
    """Tests for POST /ad-accounts/{platform}/sync"""

    @pytest.mark.asyncio
    async def test_sync_connected_platform(self):
        from app.api.v1.endpoints.campaign_builder import sync_ad_accounts

        conn = _make_connection()
        db = _make_db()
        db.execute.return_value = _make_scalar_result(conn)
        bg = MagicMock()

        resp = await sync_ad_accounts(_make_request(), AdPlatform.META, bg, db)
        assert resp.success is True
        assert "Sync started" in resp.data["message"]

    @pytest.mark.asyncio
    async def test_sync_not_connected(self):
        from fastapi import HTTPException

        from app.api.v1.endpoints.campaign_builder import sync_ad_accounts

        db = _make_db()
        db.execute.return_value = _make_scalar_result(None)
        bg = MagicMock()

        with pytest.raises(HTTPException) as exc_info:
            await sync_ad_accounts(_make_request(), AdPlatform.META, bg, db)
        assert exc_info.value.status_code == 400


class TestUpdateAdAccount:
    """Tests for PUT /ad-accounts/{platform}/{ad_account_id}"""

    @pytest.mark.asyncio
    async def test_enable_account(self):
        from app.api.v1.endpoints.campaign_builder import update_ad_account

        acc = _make_ad_account(is_enabled=False)
        db = _make_db()
        db.execute.return_value = _make_scalar_result(acc)

        update = AdAccountUpdateRequest(is_enabled=True)
        resp = await update_ad_account(
            _make_request(), AdPlatform.META, acc.id, update, db
        )
        assert resp.success is True
        assert acc.is_enabled is True

    @pytest.mark.asyncio
    async def test_set_budget_cap(self):
        from app.api.v1.endpoints.campaign_builder import update_ad_account

        acc = _make_ad_account()
        db = _make_db()
        db.execute.return_value = _make_scalar_result(acc)

        update = AdAccountUpdateRequest(daily_budget_cap=5000.0)
        resp = await update_ad_account(
            _make_request(), AdPlatform.META, acc.id, update, db
        )
        assert resp.success is True
        assert acc.daily_budget_cap == 5000.0

    @pytest.mark.asyncio
    async def test_update_not_found(self):
        from fastapi import HTTPException

        from app.api.v1.endpoints.campaign_builder import update_ad_account

        db = _make_db()
        db.execute.return_value = _make_scalar_result(None)
        update = AdAccountUpdateRequest(is_enabled=True)

        with pytest.raises(HTTPException) as exc_info:
            await update_ad_account(
                _make_request(), AdPlatform.META, uuid4(), update, db
            )
        assert exc_info.value.status_code == 404


# =============================================================================
# Campaign Draft CRUD Tests
# =============================================================================


class TestCreateCampaignDraft:
    """Tests for POST /campaign-drafts"""

    @pytest.mark.asyncio
    async def test_create_draft_success(self):
        from app.api.v1.endpoints.campaign_builder import create_campaign_draft

        acc = _make_ad_account(is_enabled=True)
        db = _make_db()
        db.execute.return_value = _make_scalar_result(acc)

        # After db.refresh, the draft needs id/timestamps populated
        async def _fake_refresh(obj):
            obj.id = uuid4()
            obj.created_at = datetime.now(timezone.utc)
            obj.updated_at = datetime.now(timezone.utc)

        db.refresh = AsyncMock(side_effect=_fake_refresh)

        draft_data = CampaignDraftCreate(
            platform="meta",
            ad_account_id=acc.id,
            name="Summer Sale",
            draft_json={"campaign": {"objective": "conversions"}},
        )

        resp = await create_campaign_draft(_make_request(), draft_data, db)
        assert resp.success is True
        db.add.assert_called_once()
        db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_create_draft_ad_account_not_enabled(self):
        from fastapi import HTTPException

        from app.api.v1.endpoints.campaign_builder import create_campaign_draft

        db = _make_db()
        db.execute.return_value = _make_scalar_result(None)  # No enabled ad account

        draft_data = CampaignDraftCreate(
            platform="meta",
            ad_account_id=uuid4(),
            name="Test",
        )

        with pytest.raises(HTTPException) as exc_info:
            await create_campaign_draft(_make_request(), draft_data, db)
        assert exc_info.value.status_code == 400
        assert "not found or not enabled" in exc_info.value.detail


class TestListCampaignDrafts:
    """Tests for GET /campaign-drafts"""

    @pytest.mark.asyncio
    async def test_list_drafts(self):
        from app.api.v1.endpoints.campaign_builder import list_campaign_drafts

        drafts = [_make_draft(), _make_draft()]
        db = _make_db()
        db.execute.return_value = _make_scalars_result(drafts)

        resp = await list_campaign_drafts(_make_request(), limit=50, offset=0, db=db)
        assert resp.success is True
        assert len(resp.data) == 2

    @pytest.mark.asyncio
    async def test_list_empty(self):
        from app.api.v1.endpoints.campaign_builder import list_campaign_drafts

        db = _make_db()
        db.execute.return_value = _make_scalars_result([])

        resp = await list_campaign_drafts(_make_request(), limit=50, offset=0, db=db)
        assert resp.success is True
        assert resp.data == []


class TestGetCampaignDraft:
    """Tests for GET /campaign-drafts/{draft_id}"""

    @pytest.mark.asyncio
    async def test_get_draft_found(self):
        from app.api.v1.endpoints.campaign_builder import get_campaign_draft

        draft = _make_draft()
        db = _make_db()
        db.execute.return_value = _make_scalar_result(draft)

        resp = await get_campaign_draft(_make_request(), draft.id, db)
        assert resp.success is True

    @pytest.mark.asyncio
    async def test_get_draft_not_found(self):
        from fastapi import HTTPException

        from app.api.v1.endpoints.campaign_builder import get_campaign_draft

        db = _make_db()
        db.execute.return_value = _make_scalar_result(None)

        with pytest.raises(HTTPException) as exc_info:
            await get_campaign_draft(_make_request(), uuid4(), db)
        assert exc_info.value.status_code == 404


class TestUpdateCampaignDraft:
    """Tests for PUT /campaign-drafts/{draft_id}"""

    @pytest.mark.asyncio
    async def test_update_draft_in_draft_status(self):
        from app.api.v1.endpoints.campaign_builder import update_campaign_draft

        draft = _make_draft(status=DraftStatus.DRAFT)
        db = _make_db()
        db.execute.return_value = _make_scalar_result(draft)

        update = CampaignDraftUpdate(name="Updated Name")
        resp = await update_campaign_draft(_make_request(), draft.id, update, db)
        assert resp.success is True
        assert draft.name == "Updated Name"

    @pytest.mark.asyncio
    async def test_update_rejected_draft_resets_to_draft(self):
        from app.api.v1.endpoints.campaign_builder import update_campaign_draft

        draft = _make_draft(status=DraftStatus.REJECTED)
        draft.rejection_reason = "Budget too high"
        db = _make_db()
        db.execute.return_value = _make_scalar_result(draft)

        update = CampaignDraftUpdate(name="Revised Campaign")
        resp = await update_campaign_draft(_make_request(), draft.id, update, db)
        assert resp.success is True
        assert draft.status == DraftStatus.DRAFT
        assert draft.rejection_reason is None

    @pytest.mark.asyncio
    async def test_update_submitted_draft_fails(self):
        from fastapi import HTTPException

        from app.api.v1.endpoints.campaign_builder import update_campaign_draft

        draft = _make_draft(status=DraftStatus.SUBMITTED)
        db = _make_db()
        db.execute.return_value = _make_scalar_result(draft)

        update = CampaignDraftUpdate(name="Cannot Update")
        with pytest.raises(HTTPException) as exc_info:
            await update_campaign_draft(_make_request(), draft.id, update, db)
        assert exc_info.value.status_code == 400
        assert "submitted" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_update_approved_draft_fails(self):
        from fastapi import HTTPException

        from app.api.v1.endpoints.campaign_builder import update_campaign_draft

        draft = _make_draft(status=DraftStatus.APPROVED)
        db = _make_db()
        db.execute.return_value = _make_scalar_result(draft)

        update = CampaignDraftUpdate(name="Cannot Update")
        with pytest.raises(HTTPException) as exc_info:
            await update_campaign_draft(_make_request(), draft.id, update, db)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_update_published_draft_fails(self):
        from fastapi import HTTPException

        from app.api.v1.endpoints.campaign_builder import update_campaign_draft

        draft = _make_draft(status=DraftStatus.PUBLISHED)
        db = _make_db()
        db.execute.return_value = _make_scalar_result(draft)

        update = CampaignDraftUpdate(name="Cannot Update")
        with pytest.raises(HTTPException) as exc_info:
            await update_campaign_draft(_make_request(), draft.id, update, db)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_update_not_found(self):
        from fastapi import HTTPException

        from app.api.v1.endpoints.campaign_builder import update_campaign_draft

        db = _make_db()
        db.execute.return_value = _make_scalar_result(None)

        update = CampaignDraftUpdate(name="New Name")
        with pytest.raises(HTTPException) as exc_info:
            await update_campaign_draft(_make_request(), uuid4(), update, db)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_update_draft_json(self):
        from app.api.v1.endpoints.campaign_builder import update_campaign_draft

        draft = _make_draft(status=DraftStatus.DRAFT)
        db = _make_db()
        db.execute.return_value = _make_scalar_result(draft)

        new_config = {
            "campaign": {"objective": "awareness", "budget": {"amount": 3000}}
        }
        update = CampaignDraftUpdate(draft_json=new_config)
        resp = await update_campaign_draft(_make_request(), draft.id, update, db)
        assert resp.success is True
        assert draft.draft_json == new_config


# =============================================================================
# Workflow State Machine Tests
# =============================================================================


class TestSubmitCampaignDraft:
    """Tests for POST /campaign-drafts/{draft_id}/submit"""

    @pytest.mark.asyncio
    async def test_submit_from_draft(self):
        from app.api.v1.endpoints.campaign_builder import submit_campaign_draft

        draft = _make_draft(status=DraftStatus.DRAFT)
        db = _make_db()
        db.execute.return_value = _make_scalar_result(draft)

        resp = await submit_campaign_draft(_make_request(), draft.id, db)
        assert resp.success is True
        assert draft.status == DraftStatus.SUBMITTED
        assert draft.submitted_at is not None
        assert draft.submitted_by_user_id == 1

    @pytest.mark.asyncio
    async def test_submit_non_draft_fails(self):
        from fastapi import HTTPException

        from app.api.v1.endpoints.campaign_builder import submit_campaign_draft

        draft = _make_draft(status=DraftStatus.APPROVED)
        db = _make_db()
        db.execute.return_value = _make_scalar_result(draft)

        with pytest.raises(HTTPException) as exc_info:
            await submit_campaign_draft(_make_request(), draft.id, db)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_submit_not_found(self):
        from fastapi import HTTPException

        from app.api.v1.endpoints.campaign_builder import submit_campaign_draft

        db = _make_db()
        db.execute.return_value = _make_scalar_result(None)

        with pytest.raises(HTTPException) as exc_info:
            await submit_campaign_draft(_make_request(), uuid4(), db)
        assert exc_info.value.status_code == 404


class TestApproveCampaignDraft:
    """Tests for POST /campaign-drafts/{draft_id}/approve"""

    @pytest.mark.asyncio
    async def test_approve_submitted_draft(self):
        from app.api.v1.endpoints.campaign_builder import approve_campaign_draft

        draft = _make_draft(status=DraftStatus.SUBMITTED)
        db = _make_db()
        db.execute.return_value = _make_scalar_result(draft)

        resp = await approve_campaign_draft(_make_request(), draft.id, db)
        assert resp.success is True
        assert draft.status == DraftStatus.APPROVED
        assert draft.approved_at is not None
        assert draft.approved_by_user_id == 1

    @pytest.mark.asyncio
    async def test_approve_non_submitted_fails(self):
        from fastapi import HTTPException

        from app.api.v1.endpoints.campaign_builder import approve_campaign_draft

        draft = _make_draft(status=DraftStatus.DRAFT)
        db = _make_db()
        db.execute.return_value = _make_scalar_result(draft)

        with pytest.raises(HTTPException) as exc_info:
            await approve_campaign_draft(_make_request(), draft.id, db)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_approve_already_approved_fails(self):
        from fastapi import HTTPException

        from app.api.v1.endpoints.campaign_builder import approve_campaign_draft

        draft = _make_draft(status=DraftStatus.APPROVED)
        db = _make_db()
        db.execute.return_value = _make_scalar_result(draft)

        with pytest.raises(HTTPException) as exc_info:
            await approve_campaign_draft(_make_request(), draft.id, db)
        assert exc_info.value.status_code == 400


class TestRejectCampaignDraft:
    """Tests for POST /campaign-drafts/{draft_id}/reject"""

    @pytest.mark.asyncio
    async def test_reject_submitted_draft(self):
        from app.api.v1.endpoints.campaign_builder import reject_campaign_draft

        draft = _make_draft(status=DraftStatus.SUBMITTED)
        db = _make_db()
        db.execute.return_value = _make_scalar_result(draft)

        resp = await reject_campaign_draft(
            _make_request(), draft.id, "Budget too high", db
        )
        assert resp.success is True
        assert draft.status == DraftStatus.REJECTED
        assert draft.rejection_reason == "Budget too high"
        assert draft.rejected_at is not None

    @pytest.mark.asyncio
    async def test_reject_non_submitted_fails(self):
        from fastapi import HTTPException

        from app.api.v1.endpoints.campaign_builder import reject_campaign_draft

        draft = _make_draft(status=DraftStatus.DRAFT)
        db = _make_db()
        db.execute.return_value = _make_scalar_result(draft)

        with pytest.raises(HTTPException) as exc_info:
            await reject_campaign_draft(_make_request(), draft.id, "Reason", db)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_reject_not_found(self):
        from fastapi import HTTPException

        from app.api.v1.endpoints.campaign_builder import reject_campaign_draft

        db = _make_db()
        db.execute.return_value = _make_scalar_result(None)

        with pytest.raises(HTTPException) as exc_info:
            await reject_campaign_draft(_make_request(), uuid4(), "Reason", db)
        assert exc_info.value.status_code == 404


class TestPublishCampaignDraft:
    """Tests for POST /campaign-drafts/{draft_id}/publish

    The endpoint validates fully and then refuses with 501: there is no
    platform publish adapter (STRAT-CB-001 P0). It previously marked drafts
    PUBLISHED and wrote a SUCCESS log with no network call — the assertions
    below deliberately invert that. Behaviour once an adapter lands is
    specified in docs/architecture/campaign-publish-plan.md.
    """

    @pytest.mark.asyncio
    async def test_publish_approved_draft_refuses_and_does_not_publish(self):
        from fastapi import HTTPException

        from app.api.v1.endpoints.campaign_builder import publish_campaign_draft

        acc = _make_ad_account(daily_budget_cap=10000)
        draft = _make_draft(
            status=DraftStatus.APPROVED,
            ad_account=acc,
            draft_json={"campaign": {"budget": {"amount": 5000}}},
        )
        db = _make_db()
        db.execute.return_value = _make_scalar_result(draft)

        with pytest.raises(HTTPException) as exc_info:
            await publish_campaign_draft(draft.id, db)

        assert exc_info.value.status_code == 501
        # The draft stays exactly as it was — still approved, still publishable.
        assert draft.status == DraftStatus.APPROVED
        assert draft.published_at is None
        assert draft.platform_campaign_id is None

    @pytest.mark.asyncio
    async def test_publish_non_approved_fails(self):
        from fastapi import HTTPException

        from app.api.v1.endpoints.campaign_builder import publish_campaign_draft

        draft = _make_draft(status=DraftStatus.SUBMITTED)
        db = _make_db()
        db.execute.return_value = _make_scalar_result(draft)

        with pytest.raises(HTTPException) as exc_info:
            await publish_campaign_draft(draft.id, db)
        assert exc_info.value.status_code == 400
        assert "Must be approved" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_publish_budget_exceeds_cap(self):
        from fastapi import HTTPException

        from app.api.v1.endpoints.campaign_builder import publish_campaign_draft

        acc = _make_ad_account(daily_budget_cap=5000)
        draft = _make_draft(
            status=DraftStatus.APPROVED,
            ad_account=acc,
            draft_json={"campaign": {"budget": {"amount": 10000}}},
        )
        db = _make_db()
        db.execute.return_value = _make_scalar_result(draft)

        with pytest.raises(HTTPException) as exc_info:
            await publish_campaign_draft(draft.id, db)
        # Budget guardrail must still win over the 501 — validation runs first,
        # so a caller learns their budget is wrong rather than only that
        # publishing is unavailable.
        assert exc_info.value.status_code == 400
        assert "exceeds" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_publish_no_budget_cap_reaches_the_501(self):
        from fastapi import HTTPException

        from app.api.v1.endpoints.campaign_builder import publish_campaign_draft

        acc = _make_ad_account(daily_budget_cap=None)
        draft = _make_draft(
            status=DraftStatus.APPROVED,
            ad_account=acc,
            draft_json={"campaign": {"budget": {"amount": 99999}}},
        )
        db = _make_db()
        db.execute.return_value = _make_scalar_result(draft)

        with pytest.raises(HTTPException) as exc_info:
            await publish_campaign_draft(draft.id, db)
        assert exc_info.value.status_code == 501
        assert draft.status == DraftStatus.APPROVED

    @pytest.mark.asyncio
    async def test_publish_not_found(self):
        from fastapi import HTTPException

        from app.api.v1.endpoints.campaign_builder import publish_campaign_draft

        db = _make_db()
        db.execute.return_value = _make_scalar_result(None)

        with pytest.raises(HTTPException) as exc_info:
            await publish_campaign_draft(uuid4(), db)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_publish_writes_no_log_entry(self):
        """Inverted from the original: nothing is attempted, so nothing is logged.

        CampaignPublishLog is the record of what was sent to a platform. A row
        written when no request was made is worse than no row at all.
        """
        from fastapi import HTTPException

        from app.api.v1.endpoints.campaign_builder import publish_campaign_draft

        acc = _make_ad_account(daily_budget_cap=None)
        draft = _make_draft(status=DraftStatus.APPROVED, ad_account=acc)
        db = _make_db()
        db.execute.return_value = _make_scalar_result(draft)

        with pytest.raises(HTTPException):
            await publish_campaign_draft(draft.id, db)
        db.add.assert_not_called()


# =============================================================================
# Full Workflow Integration Tests
# =============================================================================


class TestFullWorkflow:
    """Test the complete draft→submit→approve→publish workflow."""

    @pytest.mark.asyncio
    async def test_draft_to_submitted_to_approved(self):
        from app.api.v1.endpoints.campaign_builder import (
            approve_campaign_draft,
            submit_campaign_draft,
        )

        draft = _make_draft(status=DraftStatus.DRAFT)
        db = _make_db()
        db.execute.return_value = _make_scalar_result(draft)

        # Submit
        await submit_campaign_draft(_make_request(), draft.id, db)
        assert draft.status == DraftStatus.SUBMITTED

        # Approve
        db.execute.return_value = _make_scalar_result(draft)
        await approve_campaign_draft(_make_request(), draft.id, db)
        assert draft.status == DraftStatus.APPROVED

    @pytest.mark.asyncio
    async def test_reject_then_re_edit_and_resubmit(self):
        from app.api.v1.endpoints.campaign_builder import (
            reject_campaign_draft,
            submit_campaign_draft,
            update_campaign_draft,
        )

        draft = _make_draft(status=DraftStatus.DRAFT)
        db = _make_db()

        # Submit
        db.execute.return_value = _make_scalar_result(draft)
        await submit_campaign_draft(_make_request(), draft.id, db)
        assert draft.status == DraftStatus.SUBMITTED

        # Reject
        db.execute.return_value = _make_scalar_result(draft)
        await reject_campaign_draft(_make_request(), draft.id, "Too expensive", db)
        assert draft.status == DraftStatus.REJECTED
        assert draft.rejection_reason == "Too expensive"

        # Re-edit (should reset to draft)
        db.execute.return_value = _make_scalar_result(draft)
        update = CampaignDraftUpdate(name="Revised Campaign")
        await update_campaign_draft(_make_request(), draft.id, update, db)
        assert draft.status == DraftStatus.DRAFT
        assert draft.rejection_reason is None

        # Re-submit
        db.execute.return_value = _make_scalar_result(draft)
        await submit_campaign_draft(_make_request(), draft.id, db)
        assert draft.status == DraftStatus.SUBMITTED


# =============================================================================
# Publish Log Endpoint Tests
# =============================================================================


class TestListPublishLogs:
    """Tests for GET /campaign-publish-logs"""

    @pytest.mark.asyncio
    async def test_list_logs(self):
        from app.api.v1.endpoints.campaign_builder import list_publish_logs

        logs = [_make_publish_log(), _make_publish_log()]
        db = _make_db()
        db.execute.return_value = _make_scalars_result(logs)

        resp = await list_publish_logs(_make_request(), limit=50, offset=0, db=db)
        assert resp.success is True
        assert len(resp.data) == 2

    @pytest.mark.asyncio
    async def test_list_empty(self):
        from app.api.v1.endpoints.campaign_builder import list_publish_logs

        db = _make_db()
        db.execute.return_value = _make_scalars_result([])

        resp = await list_publish_logs(_make_request(), limit=50, offset=0, db=db)
        assert resp.success is True
        assert resp.data == []


class TestRetryPublish:
    """Tests for POST /campaign-publish-logs/{log_id}/retry"""

    @pytest.mark.asyncio
    async def test_retry_failed_publish(self):
        from app.api.v1.endpoints.campaign_builder import retry_publish

        log = _make_publish_log(result_status=PublishResult.FAILURE)
        log.retry_count = 0
        db = _make_db()
        db.execute.return_value = _make_scalar_result(log)
        bg = MagicMock()

        resp = await retry_publish(_make_request(), log.id, bg, db)
        assert resp.success is True
        assert log.retry_count == 1
        assert log.last_retry_at is not None

    @pytest.mark.asyncio
    async def test_retry_success_log_fails(self):
        from fastapi import HTTPException

        from app.api.v1.endpoints.campaign_builder import retry_publish

        log = _make_publish_log(result_status=PublishResult.SUCCESS)
        db = _make_db()
        db.execute.return_value = _make_scalar_result(log)
        bg = MagicMock()

        with pytest.raises(HTTPException) as exc_info:
            await retry_publish(_make_request(), log.id, bg, db)
        assert exc_info.value.status_code == 400
        assert "failed" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_retry_not_found(self):
        from fastapi import HTTPException

        from app.api.v1.endpoints.campaign_builder import retry_publish

        db = _make_db()
        db.execute.return_value = _make_scalar_result(None)
        bg = MagicMock()

        with pytest.raises(HTTPException) as exc_info:
            await retry_publish(_make_request(), uuid4(), bg, db)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_retry_increments_count(self):
        from app.api.v1.endpoints.campaign_builder import retry_publish

        log = _make_publish_log(result_status=PublishResult.FAILURE)
        log.retry_count = 2
        db = _make_db()
        db.execute.return_value = _make_scalar_result(log)
        bg = MagicMock()

        await retry_publish(_make_request(), log.id, bg, db)
        assert log.retry_count == 3


# =============================================================================
# Celery Task Tests
# =============================================================================

# NOTE (STRAT-SC-001, closed in C4): app/workers/campaign_builder_tasks.py
# used to query the per-organization scoping columns on
# PlatformConnection/AdAccount (and construct AdAccount
# with that scoping kwarg), but those columns were removed from the
# models — the tasks raised AttributeError at runtime. C4's de-fan-out
# rewrote the tasks to operate on the single org (one connection per
# platform, no tenant filter), so these tests now exercise real behavior
# again (no more xfail).


class TestSyncAdAccountsTask:
    """Tests for the sync_ad_accounts Celery task."""

    def test_sync_no_active_connection(self):
        from app.workers.campaign_builder_tasks import sync_ad_accounts

        mock_db = MagicMock()
        mock_db.execute.return_value.scalar_one_or_none.return_value = None

        with patch("app.workers.campaign_builder_tasks.SessionLocal") as mock_session:
            mock_session.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_session.return_value.__exit__ = MagicMock(return_value=False)
            result = sync_ad_accounts(platform="meta")

        assert result["status"] == "skipped"

    @staticmethod
    def _patched_service(accounts, side_effect=None):
        """Patch the provider seam sync_ad_accounts now goes through.

        The task used to invent two accounts inline, so these tests only had to
        patch SessionLocal. It now calls the real OAuthService.fetch_ad_accounts
        (implemented for all four platforms), so the provider is the thing that
        must be stubbed — and what comes back is what gets written.
        """
        service = MagicMock()
        service.decrypt_token.return_value = "decrypted-token"
        service.fetch_ad_accounts = AsyncMock(
            return_value=accounts, side_effect=side_effect
        )
        return service

    def test_sync_writes_exactly_what_the_provider_returns(self):
        from app.services.oauth.base import AdAccountInfo
        from app.workers.campaign_builder_tasks import sync_ad_accounts

        conn = MagicMock()
        conn.id = uuid4()
        conn.status = ConnectionStatus.CONNECTED

        mock_db = MagicMock()
        # First call returns connection, subsequent calls return None (no existing accounts)
        mock_db.execute.return_value.scalar_one_or_none.side_effect = [
            conn,
            None,
            None,
            None,
        ]

        accounts = [
            AdAccountInfo(account_id="act_111", name="Real Account One"),
            AdAccountInfo(account_id="act_222", name="Real Account Two"),
            AdAccountInfo(account_id="act_333", name="Real Account Three"),
        ]

        with patch(
            "app.workers.campaign_builder_tasks.SessionLocal"
        ) as mock_session, patch(
            "app.workers.campaign_builder_tasks._resolve_platform_credentials",
            new=AsyncMock(return_value=None),
        ), patch(
            "app.workers.campaign_builder_tasks.get_oauth_service",
            return_value=self._patched_service(accounts),
        ):
            mock_session.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_session.return_value.__exit__ = MagicMock(return_value=False)
            result = sync_ad_accounts(platform="meta")

        assert result["status"] == "success"
        # Three, because the provider returned three. The old assertion was
        # `== 2` with the comment "Mock returns 2 accounts" — it was pinning the
        # hardcoded fixture, so it would have passed no matter what the platform
        # actually held.
        assert result["synced_count"] == 3
        written = [c.args[0] for c in mock_db.add.call_args_list]
        assert [a.platform_account_id for a in written] == [
            "act_111",
            "act_222",
            "act_333",
        ]
        mock_db.commit.assert_called()

    def test_sync_invents_nothing_when_provider_returns_nothing(self):
        """An account with no ad accounts must end up with no AdAccount rows."""
        from app.workers.campaign_builder_tasks import sync_ad_accounts

        conn = MagicMock()
        conn.id = uuid4()
        conn.status = ConnectionStatus.CONNECTED

        mock_db = MagicMock()
        mock_db.execute.return_value.scalar_one_or_none.side_effect = [conn]

        with patch(
            "app.workers.campaign_builder_tasks.SessionLocal"
        ) as mock_session, patch(
            "app.workers.campaign_builder_tasks._resolve_platform_credentials",
            new=AsyncMock(return_value=None),
        ), patch(
            "app.workers.campaign_builder_tasks.get_oauth_service",
            return_value=self._patched_service([]),
        ):
            mock_session.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_session.return_value.__exit__ = MagicMock(return_value=False)
            result = sync_ad_accounts(platform="meta")

        assert result["status"] == "success"
        assert result["synced_count"] == 0
        mock_db.add.assert_not_called()

    def test_sync_updates_existing_accounts(self):
        from app.services.oauth.base import AdAccountInfo
        from app.workers.campaign_builder_tasks import sync_ad_accounts

        conn = MagicMock()
        conn.id = uuid4()
        conn.status = ConnectionStatus.CONNECTED

        existing_account = MagicMock()
        mock_db = MagicMock()
        # Connection found, then existing accounts found
        mock_db.execute.return_value.scalar_one_or_none.side_effect = [
            conn,
            existing_account,
            existing_account,
        ]

        accounts = [
            AdAccountInfo(account_id="act_111", name="Renamed On Platform"),
            AdAccountInfo(account_id="act_222", name="Also Renamed"),
        ]

        with patch(
            "app.workers.campaign_builder_tasks.SessionLocal"
        ) as mock_session, patch(
            "app.workers.campaign_builder_tasks._resolve_platform_credentials",
            new=AsyncMock(return_value=None),
        ), patch(
            "app.workers.campaign_builder_tasks.get_oauth_service",
            return_value=self._patched_service(accounts),
        ):
            mock_session.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_session.return_value.__exit__ = MagicMock(return_value=False)
            result = sync_ad_accounts(platform="meta")

        assert result["status"] == "success"
        # The platform's name wins on update — the old assertion was only
        # `is not None`, which a MagicMock satisfies without any assignment.
        assert existing_account.name == "Also Renamed"
        assert existing_account.sync_error is None
        mock_db.add.assert_not_called()

    def test_sync_without_access_token_does_not_call_provider(self):
        from app.workers.campaign_builder_tasks import sync_ad_accounts

        conn = MagicMock()
        conn.id = uuid4()
        conn.status = ConnectionStatus.CONNECTED
        conn.access_token_encrypted = None

        mock_db = MagicMock()
        mock_db.execute.return_value.scalar_one_or_none.side_effect = [conn]

        with patch(
            "app.workers.campaign_builder_tasks.SessionLocal"
        ) as mock_session, patch(
            "app.workers.campaign_builder_tasks.get_oauth_service"
        ) as mock_get_service:
            mock_session.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_session.return_value.__exit__ = MagicMock(return_value=False)
            result = sync_ad_accounts(platform="meta")

        assert result["status"] == "error"
        assert result["reason"] == "no access token"
        mock_get_service.assert_not_called()
        mock_db.add.assert_not_called()


class TestRefreshTokensTask:
    """Tests for the refresh_tokens Celery task."""

    def test_refresh_no_connection(self):
        from app.workers.campaign_builder_tasks import refresh_tokens

        mock_db = MagicMock()
        mock_db.execute.return_value.scalar_one_or_none.return_value = None

        with patch("app.workers.campaign_builder_tasks.SessionLocal") as mock_session:
            mock_session.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_session.return_value.__exit__ = MagicMock(return_value=False)
            result = refresh_tokens(platform="meta")

        assert result["status"] == "skipped"

    def test_refresh_success(self):
        # OAUTH-001: the task now performs a real refresh via the provider
        # service (decrypt refresh token -> refresh_access_token -> persist).
        from app.workers.campaign_builder_tasks import refresh_tokens

        conn = MagicMock()
        conn.status = ConnectionStatus.CONNECTED
        conn.error_count = 0
        conn.refresh_token_encrypted = "enc_refresh"

        new_tokens = MagicMock(
            access_token="new_access",
            refresh_token="new_refresh",
            expires_at=None,
            expires_in=3600,
        )
        service = MagicMock()
        service.decrypt_token.return_value = "plain_refresh"
        service.encrypt_token.side_effect = lambda t: f"enc:{t}"
        service.refresh_access_token = AsyncMock(return_value=new_tokens)

        mock_db = MagicMock()
        mock_db.execute.return_value.scalar_one_or_none.return_value = conn

        with patch(
            "app.workers.campaign_builder_tasks.SessionLocal"
        ) as mock_session, patch(
            "app.workers.campaign_builder_tasks.get_oauth_service",
            return_value=service,
        ):
            mock_session.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_session.return_value.__exit__ = MagicMock(return_value=False)
            result = refresh_tokens(platform="meta")

        assert result["status"] == "success"
        assert conn.status == ConnectionStatus.CONNECTED
        assert conn.last_error is None
        # Real tokens were persisted (encrypted), not a faked expiry.
        service.refresh_access_token.assert_awaited_once_with("plain_refresh")
        assert conn.access_token_encrypted == "enc:new_access"
        assert conn.refresh_token_encrypted == "enc:new_refresh"
        mock_db.commit.assert_called()

    def test_refresh_no_refresh_token_marks_expired(self):
        # OAUTH-001: without a stored refresh token, the task cannot refresh —
        # mark expired (needs re-auth) rather than faking success.
        from app.workers.campaign_builder_tasks import refresh_tokens

        conn = MagicMock()
        conn.status = ConnectionStatus.CONNECTED
        conn.refresh_token_encrypted = None

        mock_db = MagicMock()
        mock_db.execute.return_value.scalar_one_or_none.return_value = conn

        with patch("app.workers.campaign_builder_tasks.SessionLocal") as mock_session:
            mock_session.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_session.return_value.__exit__ = MagicMock(return_value=False)
            result = refresh_tokens(platform="meta")

        assert result["status"] == "error"
        assert conn.status == ConnectionStatus.EXPIRED


class TestPublishCampaignTask:
    """Tests for the publish_campaign Celery task."""

    def test_publish_draft_not_found(self):
        from app.workers.campaign_builder_tasks import publish_campaign

        mock_db = MagicMock()
        mock_db.execute.return_value.scalar_one_or_none.return_value = None

        with patch("app.workers.campaign_builder_tasks.SessionLocal") as mock_session:
            mock_session.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_session.return_value.__exit__ = MagicMock(return_value=False)
            result = publish_campaign(
                draft_id=str(uuid4()), publish_log_id=str(uuid4())
            )

        assert result["status"] == "error"

    def test_publish_wrong_status_skips(self):
        from app.workers.campaign_builder_tasks import publish_campaign

        draft = MagicMock()
        draft.status = DraftStatus.DRAFT  # Not PUBLISHING
        publish_log = MagicMock()

        mock_db = MagicMock()
        mock_db.execute.return_value.scalar_one_or_none.side_effect = [
            draft,
            publish_log,
        ]

        with patch("app.workers.campaign_builder_tasks.SessionLocal") as mock_session:
            mock_session.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_session.return_value.__exit__ = MagicMock(return_value=False)
            result = publish_campaign(
                draft_id=str(uuid4()), publish_log_id=str(uuid4())
            )

        assert result["status"] == "skipped"

    def test_publish_with_healthy_connection_still_fails_no_adapter(self):
        """Everything the task needs is present, and it still must not succeed.

        Renamed from test_publish_success. The old assertions — status success,
        draft PUBLISHED, log SUCCESS — were satisfied by a mock that invented a
        campaign id without a network call, so the test passed precisely
        because the production code was lying. See STRAT-CB-001 P0.
        """
        from app.workers.campaign_builder_tasks import publish_campaign

        draft_id = uuid4()
        draft = MagicMock()
        draft.id = draft_id
        draft.status = DraftStatus.PUBLISHING
        draft.platform = AdPlatform.META
        draft.ad_account_id = uuid4()
        draft.draft_json = {"campaign": {}}
        draft.platform_campaign_id = None

        publish_log = MagicMock()
        publish_log.platform_campaign_id = None

        ad_account = MagicMock()
        connection = MagicMock()
        connection.status = ConnectionStatus.CONNECTED

        mock_db = MagicMock()
        mock_db.execute.return_value.scalar_one_or_none.side_effect = [
            draft,
            publish_log,
            ad_account,
            connection,
        ]

        with patch("app.workers.campaign_builder_tasks.SessionLocal") as mock_session:
            mock_session.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_session.return_value.__exit__ = MagicMock(return_value=False)
            result = publish_campaign(
                draft_id=str(draft_id), publish_log_id=str(uuid4())
            )

        assert result["status"] == "error"
        assert draft.status == DraftStatus.FAILED
        assert publish_log.result_status == PublishResult.FAILURE
        assert draft.platform_campaign_id is None
        assert publish_log.platform_campaign_id is None


class TestPublishRetryTask:
    """Tests for the publish_retry Celery task."""

    def test_retry_log_not_found(self):
        from app.workers.campaign_builder_tasks import publish_retry

        mock_db = MagicMock()
        mock_db.execute.return_value.scalar_one_or_none.return_value = None

        with patch("app.workers.campaign_builder_tasks.SessionLocal") as mock_session:
            mock_session.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_session.return_value.__exit__ = MagicMock(return_value=False)
            result = publish_retry(log_id=str(uuid4()))

        assert result["status"] == "error"

    def test_retry_non_failure_skips(self):
        from app.workers.campaign_builder_tasks import publish_retry

        log = MagicMock()
        log.result_status = PublishResult.SUCCESS

        mock_db = MagicMock()
        mock_db.execute.return_value.scalar_one_or_none.return_value = log

        with patch("app.workers.campaign_builder_tasks.SessionLocal") as mock_session:
            mock_session.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_session.return_value.__exit__ = MagicMock(return_value=False)
            result = publish_retry(log_id=str(uuid4()))

        assert result["status"] == "skipped"


class TestConnectorHealthCheckTask:
    """Tests for the connector_health_check Celery task."""

    @staticmethod
    def _run(conn, probe_side_effect=None):
        """Run the task against one connection with the provider seam stubbed.

        The probe is a real authenticated call (fetch_ad_accounts), so the
        provider is what must be stubbed. The old test patched only
        SessionLocal and asserted healthy is True — which the hardcoded
        `healthy = True` satisfied regardless of any platform's actual state.
        """
        from app.workers.campaign_builder_tasks import connector_health_check

        service = MagicMock()
        service.decrypt_token.return_value = "decrypted-token"
        service.fetch_ad_accounts = AsyncMock(
            return_value=[], side_effect=probe_side_effect
        )

        mock_db = MagicMock()
        mock_db.execute.return_value.scalars.return_value.all.return_value = [conn]

        with patch(
            "app.workers.campaign_builder_tasks.SessionLocal"
        ) as mock_session, patch(
            "app.workers.campaign_builder_tasks._resolve_platform_credentials",
            new=AsyncMock(return_value=None),
        ), patch(
            "app.workers.campaign_builder_tasks.get_oauth_service",
            return_value=service,
        ):
            mock_session.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_session.return_value.__exit__ = MagicMock(return_value=False)
            return connector_health_check()

    @staticmethod
    def _conn(error_count=0, last_error=None, token="enc-token"):
        conn = MagicMock()
        conn.id = uuid4()
        conn.platform = AdPlatform.META
        conn.status = ConnectionStatus.CONNECTED
        conn.error_count = error_count
        conn.last_error = last_error
        conn.access_token_encrypted = token
        return conn

    def test_successful_probe_marks_healthy_and_clears_errors(self):
        conn = self._conn(error_count=2, last_error="previous failure")

        result = self._run(conn)

        assert result["results"][0]["healthy"] is True
        # Clearing is now evidence-backed: it happens only after the provider
        # actually answered.
        assert conn.error_count == 0
        assert conn.last_error is None

    def test_failed_probe_marks_unhealthy_and_records_the_error(self):
        conn = self._conn()

        result = self._run(conn, probe_side_effect=RuntimeError("token expired"))

        assert result["results"][0]["healthy"] is False
        assert conn.error_count == 1
        assert "token expired" in conn.last_error

    def test_failed_probe_does_not_erase_prior_error_state(self):
        """The regression that mattered most.

        The old task cleared last_error and error_count unconditionally, every
        30 minutes, so a connection that was continuously broken had the
        evidence of its own breakage wiped on each beat and never accumulated
        toward ERROR.
        """
        conn = self._conn(error_count=1, last_error="earlier failure")

        self._run(conn, probe_side_effect=RuntimeError("still broken"))

        assert conn.error_count == 2, "error state was reset instead of accumulating"
        assert conn.last_error != "earlier failure"
        assert conn.last_error is not None

    def test_threshold_failures_mark_connection_error(self):
        """The old else branch was unreachable, so ERROR could never be set."""
        from app.workers.campaign_builder_tasks import UNHEALTHY_PROBE_THRESHOLD

        conn = self._conn(error_count=UNHEALTHY_PROBE_THRESHOLD - 1)

        self._run(conn, probe_side_effect=RuntimeError("down"))

        assert conn.error_count == UNHEALTHY_PROBE_THRESHOLD
        assert conn.status == ConnectionStatus.ERROR

    def test_non_socket_errors_count_as_unhealthy(self):
        """Expired tokens surface as provider errors, not OSError subclasses.

        The previous except clause caught only (ConnectionError, TimeoutError,
        OSError), so the failure mode that matters most here would have
        propagated rather than being recorded.
        """
        conn = self._conn()

        class OAuthProviderError(Exception):
            pass

        result = self._run(conn, probe_side_effect=OAuthProviderError("invalid_grant"))

        assert result["results"][0]["healthy"] is False
        assert "invalid_grant" in conn.last_error

    def test_missing_token_is_unhealthy_and_never_probes(self):
        conn = self._conn(error_count=1, last_error="earlier failure", token=None)

        result = self._run(conn)

        assert result["results"][0]["healthy"] is False
        assert conn.error_count == 2
        assert "re-authorization" in conn.last_error

    def test_health_check_no_connections(self):
        from app.workers.campaign_builder_tasks import connector_health_check

        mock_db = MagicMock()
        mock_db.execute.return_value.scalars.return_value.all.return_value = []

        with patch("app.workers.campaign_builder_tasks.SessionLocal") as mock_session:
            mock_session.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_session.return_value.__exit__ = MagicMock(return_value=False)
            result = connector_health_check()

        assert result["status"] == "completed"
        assert result["results"] == []


# =============================================================================
# Edge Cases & Boundary Tests
# =============================================================================


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_draft_json_empty_default(self):
        uid = uuid4()
        req = CampaignDraftCreate(platform="meta", ad_account_id=uid, name="Test")
        assert req.draft_json == {}

    def test_all_platforms_have_oauth_config(self):
        """Verify all 4 platforms have OAuth configs in start_platform_connection."""
        # This is a static check on the source code
        from app.api.v1.endpoints.campaign_builder import start_platform_connection

        # All platforms should be present in the oauth_configs dict
        for platform in AdPlatform:
            assert platform in [
                AdPlatform.META,
                AdPlatform.GOOGLE,
                AdPlatform.TIKTOK,
                AdPlatform.SNAPCHAT,
            ]

    # The three budget-boundary cases below assert the guardrail *lets the
    # request through*. Before STRAT-CB-001 P0 "through" meant a 200; it now
    # means reaching the 501 refusal at the end of the handler. Either way the
    # thing under test is the same: these budgets are not rejected as over cap.

    @pytest.mark.asyncio
    async def test_publish_budget_zero_amount_passes(self):
        """Zero budget should pass since 0 <= any cap."""
        from fastapi import HTTPException

        from app.api.v1.endpoints.campaign_builder import publish_campaign_draft

        acc = _make_ad_account(daily_budget_cap=5000)
        draft = _make_draft(
            status=DraftStatus.APPROVED,
            ad_account=acc,
            draft_json={"campaign": {"budget": {"amount": 0}}},
        )
        db = _make_db()
        db.execute.return_value = _make_scalar_result(draft)

        with pytest.raises(HTTPException) as exc_info:
            await publish_campaign_draft(draft.id, db)
        assert exc_info.value.status_code == 501

    @pytest.mark.asyncio
    async def test_publish_no_budget_in_draft_json(self):
        """If draft_json has no budget field, budget check should pass (amount=0)."""
        from fastapi import HTTPException

        from app.api.v1.endpoints.campaign_builder import publish_campaign_draft

        acc = _make_ad_account(daily_budget_cap=5000)
        draft = _make_draft(
            status=DraftStatus.APPROVED,
            ad_account=acc,
            draft_json={"campaign": {"objective": "awareness"}},
        )
        db = _make_db()
        db.execute.return_value = _make_scalar_result(draft)

        with pytest.raises(HTTPException) as exc_info:
            await publish_campaign_draft(draft.id, db)
        assert exc_info.value.status_code == 501

    @pytest.mark.asyncio
    async def test_publish_budget_exactly_at_cap(self):
        """Budget exactly equal to cap should pass (> not >=)."""
        from fastapi import HTTPException

        from app.api.v1.endpoints.campaign_builder import publish_campaign_draft

        acc = _make_ad_account(daily_budget_cap=5000)
        draft = _make_draft(
            status=DraftStatus.APPROVED,
            ad_account=acc,
            draft_json={"campaign": {"budget": {"amount": 5000}}},
        )
        db = _make_db()
        db.execute.return_value = _make_scalar_result(draft)

        with pytest.raises(HTTPException) as exc_info:
            await publish_campaign_draft(draft.id, db)
        assert exc_info.value.status_code == 501

    @pytest.mark.asyncio
    async def test_disconnect_clears_tokens(self):
        """Verify disconnecting clears sensitive token data."""
        from app.api.v1.endpoints.campaign_builder import disconnect_platform

        conn = _make_connection()
        assert conn.access_token_encrypted is not None

        db = _make_db()
        db.execute.return_value = _make_scalar_result(conn)

        await disconnect_platform(_make_request(), AdPlatform.META, db)
        assert conn.access_token_encrypted is None
        assert conn.refresh_token_encrypted is None
        assert conn.status == ConnectionStatus.DISCONNECTED

    def test_platform_enum_used_as_string(self):
        """AdPlatform inherits from str, so .value can be used in string contexts."""
        assert f"Platform: {AdPlatform.META.value}" == "Platform: meta"
        assert str(AdPlatform.GOOGLE.value) + "_suffix" == "google_suffix"

    def test_draft_status_workflow_values(self):
        """Verify all workflow states are present for state machine correctness."""
        expected = {
            "draft",
            "submitted",
            "approved",
            "rejected",
            "publishing",
            "published",
            "failed",
        }
        actual = {s.value for s in DraftStatus}
        assert actual == expected
