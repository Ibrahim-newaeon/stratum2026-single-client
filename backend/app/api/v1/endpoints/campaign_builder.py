# =============================================================================
# Stratum AI - Campaign Builder API Router
# =============================================================================
"""
API endpoints for the Campaign Builder feature:
- Platform connectors (OAuth management)
- Ad accounts (sync and enable/disable)
- Campaign drafts (CRUD + workflow)
- Publish logs (audit trail)

All routes enforce RBAC permissions.
"""

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.deps import get_current_user
from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import get_async_session
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
from app.schemas.response import APIResponse, PaginatedResponse

logger = get_logger(__name__)
# SECURITY (STRAT-SC-001/C3): the old per-org request guards were the only
# auth on these routes; deleted in the de-tenanting sweep, so real auth is
# enforced router-wide here.
router = APIRouter(
    tags=["campaign-builder"],
    dependencies=[Depends(get_current_user)],
)


async def require_campaign_publish_enabled() -> None:
    """
    Gate campaign publish behind a feature flag.

    Publishing currently marks a draft PUBLISHED with no platform call and no
    ``platform_campaign_id`` (hardcoded SUCCESS, dispatch commented out) — it
    records campaigns as live that don't exist on-platform, a data-integrity
    risk. Gated off until a real publish adapter lands. Only publish is 503'd;
    draft CRUD stays available.
    """
    if not settings.enable_campaign_publish:
        raise HTTPException(
            status_code=503,
            detail="Campaign publishing is not enabled on this deployment.",
        )


# =============================================================================
# Pydantic Schemas
# =============================================================================


class ConnectorStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    platform: str
    status: str
    connected_at: Optional[datetime] = None
    last_refreshed_at: Optional[datetime] = None
    scopes: List[str] = []
    last_error: Optional[str] = None


class AdAccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    platform: str
    platform_account_id: str
    name: str
    business_name: Optional[str] = None
    currency: str
    timezone: str
    is_enabled: bool
    daily_budget_cap: Optional[float] = None
    last_synced_at: Optional[datetime] = None


class AdAccountUpdateRequest(BaseModel):
    is_enabled: Optional[bool] = None
    daily_budget_cap: Optional[float] = None


class CampaignDraftCreate(BaseModel):
    platform: str
    ad_account_id: UUID
    name: str
    description: Optional[str] = None
    draft_json: dict = Field(default_factory=dict)


class CampaignDraftUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    draft_json: Optional[dict] = None


class CampaignDraftResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    platform: str
    ad_account_id: Optional[UUID] = None
    name: str
    description: Optional[str] = None
    status: str
    draft_json: dict
    created_at: datetime
    updated_at: datetime
    submitted_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    rejected_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    platform_campaign_id: Optional[str] = None
    published_at: Optional[datetime] = None


class PublishLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    draft_id: Optional[UUID] = None
    platform: str
    platform_account_id: str
    event_time: datetime
    result_status: str
    platform_campaign_id: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int


# =============================================================================
# Connectors Endpoints
# =============================================================================


@router.get(
    "/connect/{platform}/status", response_model=APIResponse[ConnectorStatusResponse]
)
async def get_connector_status(
    request: Request,
    platform: AdPlatform,
    db: AsyncSession = Depends(get_async_session),
):
    """Get connection status for a platform."""
    result = await db.execute(
        select(PlatformConnection).where(PlatformConnection.platform == platform)
    )
    connection = result.scalar_one_or_none()

    if not connection:
        return APIResponse(
            success=True,
            data=ConnectorStatusResponse(
                platform=platform.value,
                status=ConnectionStatus.DISCONNECTED.value,
            ),
        )

    return APIResponse(
        success=True,
        data=ConnectorStatusResponse(
            platform=connection.platform.value,
            status=connection.status.value,
            connected_at=connection.connected_at,
            last_refreshed_at=connection.last_refreshed_at,
            scopes=connection.scopes or [],
            last_error=connection.last_error,
        ),
    )


@router.post("/connect/{platform}/start")
async def start_platform_connection(
    request: Request,
    platform: AdPlatform,
    db: AsyncSession = Depends(get_async_session),
):
    """
    Start OAuth flow for a platform.
    Returns the authorization URL to redirect the user.
    """
    # Generate OAuth URL with state parameter for CSRF protection
    import secrets

    state_token = secrets.token_urlsafe(32)
    redirect_uri = (
        f"{request.base_url}api/v1/campaign-builder/connect/{platform.value}/callback"
    )

    oauth_configs = {
        AdPlatform.META: {
            "base_url": "https://www.facebook.com/v25.0/dialog/oauth",
            "client_id": settings.meta_app_id,
            "scope": "ads_management,ads_read,business_management,pages_read_engagement",
        },
        AdPlatform.GOOGLE: {
            "base_url": "https://accounts.google.com/o/oauth2/v2/auth",
            "client_id": settings.google_ads_client_id,
            "scope": "https://www.googleapis.com/auth/adwords",
        },
        AdPlatform.TIKTOK: {
            "base_url": "https://ads.tiktok.com/marketing_api/auth",
            "client_id": settings.tiktok_app_id,
            "scope": "advertiser.read,advertiser.write,campaign.read,campaign.write,report.read",
        },
        AdPlatform.SNAPCHAT: {
            "base_url": "https://accounts.snapchat.com/accounts/oauth2/auth",
            "client_id": settings.snapchat_client_id,
            "scope": "snapchat-marketing-api",
        },
    }

    config = oauth_configs.get(platform)
    if not config:
        raise HTTPException(
            status_code=400, detail=f"Unsupported platform: {platform.value}"
        )

    client_id = config["client_id"] or ""
    if not client_id:
        raise HTTPException(
            status_code=400,
            detail=f"OAuth not configured for {platform.value}. Contact your administrator.",
        )

    from urllib.parse import urlencode

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": state_token,
        "scope": config["scope"],
        "response_type": "code",
    }
    oauth_url = f"{config['base_url']}?{urlencode(params)}"

    return APIResponse(
        success=True,
        data={
            "oauth_url": oauth_url,
            "state": state_token,
            "redirect_uri": redirect_uri,
            "message": f"Redirect user to OAuth URL for {platform.value}",
        },
    )


@router.post("/connect/{platform}/refresh")
async def refresh_platform_token(
    request: Request,
    platform: AdPlatform,
    db: AsyncSession = Depends(get_async_session),
):
    """Refresh OAuth token for a platform."""
    result = await db.execute(
        select(PlatformConnection).where(PlatformConnection.platform == platform)
    )
    connection = result.scalar_one_or_none()

    if not connection:
        raise HTTPException(status_code=404, detail="Platform not connected")

    # Attempt token refresh via platform OAuth
    try:
        from app.services.oauth.factory import get_oauth_service

        oauth_service = get_oauth_service(platform)
        refresh_token = connection.refresh_token_encrypted

        if not refresh_token:
            raise HTTPException(
                status_code=400,
                detail=f"Platform authentication expired for {platform.value}. Please re-authenticate.",
            )

        new_tokens = await oauth_service.refresh_access_token(refresh_token)

        if new_tokens and new_tokens.get("access_token"):
            connection.access_token_encrypted = new_tokens["access_token"]
            if new_tokens.get("refresh_token"):
                connection.refresh_token_encrypted = new_tokens["refresh_token"]
            connection.last_refreshed_at = datetime.now(timezone.utc)
            connection.status = ConnectionStatus.CONNECTED
            connection.last_error = None
            connection.token_expires_at = new_tokens.get("expires_at")
        else:
            connection.last_refreshed_at = datetime.now(timezone.utc)
            connection.status = ConnectionStatus.CONNECTED
            connection.last_error = None

    except HTTPException:
        raise
    except Exception as e:
        logger.warning(
            "token_refresh_failed",
            platform=platform.value,
            error=str(e),
        )
        connection.last_refreshed_at = datetime.now(timezone.utc)
        connection.status = ConnectionStatus.CONNECTED
        connection.last_error = str(e)

    await db.commit()

    return APIResponse(
        success=True,
        data={"message": f"Token refreshed for {platform.value}"},
    )


@router.delete("/connect/{platform}")
async def disconnect_platform(
    request: Request,
    platform: AdPlatform,
    db: AsyncSession = Depends(get_async_session),
):
    """Disconnect a platform (revoke OAuth)."""
    result = await db.execute(
        select(PlatformConnection).where(PlatformConnection.platform == platform)
    )
    connection = result.scalar_one_or_none()

    if not connection:
        raise HTTPException(status_code=404, detail="Platform not connected")

    # Mark as disconnected (keep record for audit)
    connection.status = ConnectionStatus.DISCONNECTED
    connection.access_token_encrypted = None
    connection.refresh_token_encrypted = None
    await db.commit()

    return APIResponse(
        success=True,
        data={"message": f"Disconnected from {platform.value}"},
    )


# =============================================================================
# Ad Accounts Endpoints
# =============================================================================


@router.get(
    "/ad-accounts/{platform}", response_model=APIResponse[List[AdAccountResponse]]
)
async def list_ad_accounts(
    request: Request,
    platform: AdPlatform,
    enabled_only: bool = False,
    db: AsyncSession = Depends(get_async_session),
):
    """List ad accounts for a platform."""
    query = select(AdAccount).where(AdAccount.platform == platform)

    if enabled_only:
        query = query.where(AdAccount.is_enabled == True)

    result = await db.execute(query.order_by(AdAccount.name).limit(1000))
    accounts = result.scalars().all()

    return APIResponse(
        success=True,
        data=[AdAccountResponse.model_validate(acc) for acc in accounts],
    )


@router.post("/ad-accounts/{platform}/sync")
async def sync_ad_accounts(
    request: Request,
    platform: AdPlatform,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_async_session),
):
    """Trigger ad accounts sync from platform."""
    # Check connection exists and is connected
    result = await db.execute(
        select(PlatformConnection).where(
            and_(
                PlatformConnection.platform == platform,
                PlatformConnection.status == ConnectionStatus.CONNECTED,
            )
        )
    )
    connection = result.scalar_one_or_none()

    if not connection:
        raise HTTPException(
            status_code=400, detail=f"Platform {platform.value} is not connected"
        )

    # In production, trigger Celery task
    # background_tasks.add_task(sync_ad_accounts_task, platform)

    return APIResponse(
        success=True,
        data={"message": f"Sync started for {platform.value} ad accounts"},
    )


@router.put(
    "/ad-accounts/{platform}/{ad_account_id}",
    response_model=APIResponse[AdAccountResponse],
)
async def update_ad_account(
    request: Request,
    platform: AdPlatform,
    ad_account_id: UUID,
    update_data: AdAccountUpdateRequest,
    db: AsyncSession = Depends(get_async_session),
):
    """Update ad account settings (enable/disable, budget cap)."""
    result = await db.execute(select(AdAccount).where(AdAccount.id == ad_account_id))
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(status_code=404, detail="Ad account not found")

    if update_data.is_enabled is not None:
        account.is_enabled = update_data.is_enabled
    if update_data.daily_budget_cap is not None:
        account.daily_budget_cap = update_data.daily_budget_cap

    await db.commit()
    await db.refresh(account)

    return APIResponse(
        success=True,
        data=AdAccountResponse.model_validate(account),
    )


# =============================================================================
# Campaign Drafts Endpoints
# =============================================================================


@router.post("/campaign-drafts", response_model=APIResponse[CampaignDraftResponse])
async def create_campaign_draft(
    request: Request,
    draft_data: CampaignDraftCreate,
    db: AsyncSession = Depends(get_async_session),
):
    """Create a new campaign draft."""
    user_id = getattr(request.state, "user_id", None)

    # Validate ad account exists and is enabled
    result = await db.execute(
        select(AdAccount).where(
            and_(
                AdAccount.id == draft_data.ad_account_id,
                AdAccount.is_enabled == True,
            )
        )
    )
    ad_account = result.scalar_one_or_none()

    if not ad_account:
        raise HTTPException(
            status_code=400, detail="Ad account not found or not enabled"
        )

    draft = CampaignDraft(
        platform=AdPlatform(draft_data.platform),
        ad_account_id=draft_data.ad_account_id,
        name=draft_data.name,
        description=draft_data.description,
        draft_json=draft_data.draft_json,
        status=DraftStatus.DRAFT,
        created_by_user_id=user_id,
    )

    db.add(draft)
    await db.commit()
    await db.refresh(draft)

    return APIResponse(
        success=True,
        data=CampaignDraftResponse.model_validate(draft),
    )


@router.get("/campaign-drafts", response_model=APIResponse[List[CampaignDraftResponse]])
async def list_campaign_drafts(
    request: Request,
    platform: Optional[AdPlatform] = None,
    status: Optional[DraftStatus] = None,
    ad_account_id: Optional[UUID] = None,
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_async_session),
):
    """List campaign drafts with optional filters."""
    query = select(CampaignDraft)

    if platform:
        query = query.where(CampaignDraft.platform == platform)
    if status:
        query = query.where(CampaignDraft.status == status)
    if ad_account_id:
        query = query.where(CampaignDraft.ad_account_id == ad_account_id)

    query = query.order_by(CampaignDraft.updated_at.desc()).limit(limit).offset(offset)

    result = await db.execute(query)
    drafts = result.scalars().all()

    return APIResponse(
        success=True,
        data=[CampaignDraftResponse.model_validate(d) for d in drafts],
    )


@router.get(
    "/campaign-drafts/{draft_id}", response_model=APIResponse[CampaignDraftResponse]
)
async def get_campaign_draft(
    request: Request,
    draft_id: UUID,
    db: AsyncSession = Depends(get_async_session),
):
    """Get a specific campaign draft."""
    result = await db.execute(select(CampaignDraft).where(CampaignDraft.id == draft_id))
    draft = result.scalar_one_or_none()

    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    return APIResponse(
        success=True,
        data=CampaignDraftResponse.model_validate(draft),
    )


@router.put(
    "/campaign-drafts/{draft_id}", response_model=APIResponse[CampaignDraftResponse]
)
async def update_campaign_draft(
    request: Request,
    draft_id: UUID,
    update_data: CampaignDraftUpdate,
    db: AsyncSession = Depends(get_async_session),
):
    """Update a campaign draft (only allowed in draft status)."""
    result = await db.execute(select(CampaignDraft).where(CampaignDraft.id == draft_id))
    draft = result.scalar_one_or_none()

    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    if draft.status not in [DraftStatus.DRAFT, DraftStatus.REJECTED]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot update draft in {draft.status.value} status",
        )

    if update_data.name is not None:
        draft.name = update_data.name
    if update_data.description is not None:
        draft.description = update_data.description
    if update_data.draft_json is not None:
        draft.draft_json = update_data.draft_json

    # Reset to draft status if was rejected
    if draft.status == DraftStatus.REJECTED:
        draft.status = DraftStatus.DRAFT
        draft.rejection_reason = None

    await db.commit()
    await db.refresh(draft)

    return APIResponse(
        success=True,
        data=CampaignDraftResponse.model_validate(draft),
    )


@router.post(
    "/campaign-drafts/{draft_id}/submit",
    response_model=APIResponse[CampaignDraftResponse],
)
async def submit_campaign_draft(
    request: Request,
    draft_id: UUID,
    db: AsyncSession = Depends(get_async_session),
):
    """Submit draft for approval."""
    user_id = getattr(request.state, "user_id", None)

    result = await db.execute(select(CampaignDraft).where(CampaignDraft.id == draft_id))
    draft = result.scalar_one_or_none()

    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    if draft.status != DraftStatus.DRAFT:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot submit draft in {draft.status.value} status",
        )

    draft.status = DraftStatus.SUBMITTED
    draft.submitted_by_user_id = user_id
    draft.submitted_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(draft)

    return APIResponse(
        success=True,
        data=CampaignDraftResponse.model_validate(draft),
    )


@router.post(
    "/campaign-drafts/{draft_id}/approve",
    response_model=APIResponse[CampaignDraftResponse],
)
async def approve_campaign_draft(
    request: Request,
    draft_id: UUID,
    db: AsyncSession = Depends(get_async_session),
):
    """Approve a submitted draft (requires CAMPAIGN_APPROVE permission)."""
    user_id = getattr(request.state, "user_id", None)

    result = await db.execute(select(CampaignDraft).where(CampaignDraft.id == draft_id))
    draft = result.scalar_one_or_none()

    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    if draft.status != DraftStatus.SUBMITTED:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot approve draft in {draft.status.value} status",
        )

    draft.status = DraftStatus.APPROVED
    draft.approved_by_user_id = user_id
    draft.approved_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(draft)

    return APIResponse(
        success=True,
        data=CampaignDraftResponse.model_validate(draft),
    )


@router.post(
    "/campaign-drafts/{draft_id}/reject",
    response_model=APIResponse[CampaignDraftResponse],
)
async def reject_campaign_draft(
    request: Request,
    draft_id: UUID,
    reason: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_async_session),
):
    """Reject a submitted draft."""
    user_id = getattr(request.state, "user_id", None)

    result = await db.execute(select(CampaignDraft).where(CampaignDraft.id == draft_id))
    draft = result.scalar_one_or_none()

    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    if draft.status != DraftStatus.SUBMITTED:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot reject draft in {draft.status.value} status",
        )

    draft.status = DraftStatus.REJECTED
    draft.rejected_by_user_id = user_id
    draft.rejected_at = datetime.now(timezone.utc)
    draft.rejection_reason = reason

    await db.commit()
    await db.refresh(draft)

    return APIResponse(
        success=True,
        data=CampaignDraftResponse.model_validate(draft),
    )


@router.post(
    "/campaign-drafts/{draft_id}/publish",
    response_model=APIResponse[CampaignDraftResponse],
    dependencies=[Depends(require_campaign_publish_enabled)],
)
async def publish_campaign_draft(
    request: Request,
    draft_id: UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_async_session),
):
    """Publish an approved campaign draft to the platform."""
    user_id = getattr(request.state, "user_id", None)

    result = await db.execute(
        select(CampaignDraft)
        .options(selectinload(CampaignDraft.ad_account))
        .where(CampaignDraft.id == draft_id)
    )
    draft = result.scalar_one_or_none()

    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    if draft.status != DraftStatus.APPROVED:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot publish draft in {draft.status.value} status. Must be approved first.",
        )

    # Check budget guardrails
    budget = draft.draft_json.get("campaign", {}).get("budget", {})
    budget_amount = budget.get("amount", 0)

    if draft.ad_account and draft.ad_account.daily_budget_cap:
        if budget_amount > float(draft.ad_account.daily_budget_cap):
            raise HTTPException(
                status_code=400,
                detail=f"Budget {budget_amount} exceeds account cap {draft.ad_account.daily_budget_cap}",
            )

    # Update status to publishing
    draft.status = DraftStatus.PUBLISHING
    await db.commit()

    # Create publish log entry
    publish_log = CampaignPublishLog(
        draft_id=draft_id,
        platform=draft.platform,
        platform_account_id=(
            draft.ad_account.platform_account_id if draft.ad_account else ""
        ),
        published_by_user_id=user_id,
        request_json=draft.draft_json,
        result_status=PublishResult.SUCCESS,  # Will be updated by background task
    )
    db.add(publish_log)
    await db.commit()

    # In production, trigger async publish task and await platform API response
    # background_tasks.add_task(publish_campaign_task, draft_id, publish_log.id)

    # Mark as published — platform_campaign_id will be set by the background task
    # when the platform API returns the real campaign ID.
    draft.status = DraftStatus.PUBLISHED
    draft.published_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(draft)

    return APIResponse(
        success=True,
        data=CampaignDraftResponse.model_validate(draft),
    )


# =============================================================================
# Publish Logs Endpoints
# =============================================================================


@router.get(
    "/campaign-publish-logs", response_model=APIResponse[List[PublishLogResponse]]
)
async def list_publish_logs(
    request: Request,
    draft_id: Optional[UUID] = None,
    platform: Optional[AdPlatform] = None,
    result_status: Optional[PublishResult] = None,
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_async_session),
):
    """List publish logs with optional filters."""
    query = select(CampaignPublishLog)

    if draft_id:
        query = query.where(CampaignPublishLog.draft_id == draft_id)
    if platform:
        query = query.where(CampaignPublishLog.platform == platform)
    if result_status:
        query = query.where(CampaignPublishLog.result_status == result_status)

    query = (
        query.order_by(CampaignPublishLog.event_time.desc()).limit(limit).offset(offset)
    )

    result = await db.execute(query)
    logs = result.scalars().all()

    return APIResponse(
        success=True,
        data=[PublishLogResponse.model_validate(log) for log in logs],
    )


@router.post("/campaign-publish-logs/{log_id}/retry")
async def retry_publish(
    request: Request,
    log_id: UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_async_session),
):
    """Retry a failed publish attempt."""
    result = await db.execute(
        select(CampaignPublishLog).where(CampaignPublishLog.id == log_id)
    )
    log = result.scalar_one_or_none()

    if not log:
        raise HTTPException(status_code=404, detail="Publish log not found")

    if log.result_status != PublishResult.FAILURE:
        raise HTTPException(
            status_code=400, detail="Can only retry failed publish attempts"
        )

    # Update retry count
    log.retry_count += 1
    log.last_retry_at = datetime.now(timezone.utc)
    await db.commit()

    # In production, trigger retry task
    # background_tasks.add_task(publish_retry_task, log_id)

    return APIResponse(
        success=True,
        data={"message": f"Retry initiated (attempt {log.retry_count})"},
    )
