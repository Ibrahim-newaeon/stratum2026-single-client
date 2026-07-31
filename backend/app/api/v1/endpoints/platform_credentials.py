# =============================================================================
# Stratum AI - Platform App Credentials CRUD (owner/admin)
# =============================================================================
"""
Owner/admin management of per-deployment OAuth app credentials.

Secrets are write-only: accepted in PUT bodies, stored encrypted
(EncryptedString), and never serialized back in any response.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import VerifiedUserDep, require_admin
from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import get_async_session
from app.models import AuditAction, AuditLog
from app.models.platform_app_credential import PlatformAppCredential
from app.schemas import APIResponse
from app.services.oauth.credentials import ENV_CREDENTIAL_FIELDS, PLATFORM_LABELS

logger = get_logger(__name__)

router = APIRouter(
    prefix="/platform-credentials",
    dependencies=[Depends(require_admin())],
)

_VALID_PLATFORMS = set(ENV_CREDENTIAL_FIELDS.keys())


def _callback_url(platform: str) -> str:
    base_url = settings.oauth_redirect_base_url.rstrip("/")
    return f"{base_url}/api/v1/oauth/{platform}/callback"


class CredentialUpsertRequest(BaseModel):
    client_id: str = Field(..., min_length=1, max_length=255)
    client_secret: Optional[str] = Field(default=None, max_length=1024)
    developer_token: Optional[str] = Field(default=None, max_length=1024)

    @field_validator("client_id")
    @classmethod
    def strip_client_id(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("client_id must not be blank")
        return v


class CredentialStatus(BaseModel):
    platform: str
    configured: bool
    source: Optional[str]  # "database" | "environment" | None
    client_id: Optional[str]
    has_developer_token: bool
    callback_url: str


def _validate_platform(platform: str) -> str:
    platform = platform.lower()
    if platform not in _VALID_PLATFORMS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown platform: {platform}",
        )
    return platform


@router.get("", response_model=APIResponse[list[CredentialStatus]])
async def list_credentials(
    current_user: VerifiedUserDep,
    db: AsyncSession = Depends(get_async_session),
):
    result = await db.execute(select(PlatformAppCredential))
    rows = {r.platform: r for r in result.scalars().all()}

    statuses: list[CredentialStatus] = []
    for platform in sorted(_VALID_PLATFORMS):
        row = rows.get(platform)
        if row is not None:
            statuses.append(
                CredentialStatus(
                    platform=platform,
                    configured=True,
                    source="database",
                    client_id=row.client_id,
                    has_developer_token=bool(row.developer_token),
                    callback_url=_callback_url(platform),
                )
            )
            continue
        id_attr, secret_attr, dev_attr = ENV_CREDENTIAL_FIELDS[platform]
        env_id = getattr(settings, id_attr, None)
        env_secret = getattr(settings, secret_attr, None)
        env_configured = bool(env_id and env_secret)
        statuses.append(
            CredentialStatus(
                platform=platform,
                configured=env_configured,
                source="environment" if env_configured else None,
                client_id=env_id if env_configured else None,
                has_developer_token=bool(
                    dev_attr and getattr(settings, dev_attr, None)
                ),
                callback_url=_callback_url(platform),
            )
        )
    return APIResponse(success=True, data=statuses)


@router.put("/{platform}", response_model=APIResponse[CredentialStatus])
async def upsert_credentials(
    platform: str,
    data: CredentialUpsertRequest,
    request: Request,
    current_user: VerifiedUserDep,
    db: AsyncSession = Depends(get_async_session),
):
    platform = _validate_platform(platform)
    result = await db.execute(
        select(PlatformAppCredential).where(PlatformAppCredential.platform == platform)
    )
    row = result.scalar_one_or_none()

    secret = (data.client_secret or "").strip()
    if row is None and not secret:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="client_secret is required when adding credentials",
        )

    created = row is None
    if row is None:
        row = PlatformAppCredential(
            platform=platform,
            client_id=data.client_id,
            client_secret=secret,
            developer_token=(data.developer_token or "").strip() or None,
            updated_by_user_id=current_user.user.id,
        )
        db.add(row)
        action = AuditAction.CREATE
    else:
        row.client_id = data.client_id
        if secret:
            row.client_secret = secret
        if data.developer_token is not None:
            row.developer_token = data.developer_token.strip() or None
        row.updated_by_user_id = current_user.user.id
        action = AuditAction.UPDATE

    db.add(
        AuditLog(
            user_id=current_user.user.id,
            action=action,
            resource_type="platform_app_credential",
            resource_id=platform,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("User-Agent", "")[:500],
        )
    )

    if created:
        try:
            await db.commit()
        except IntegrityError:
            # Another concurrent request won the race on the unique
            # `platform` constraint between our SELECT and our INSERT.
            # Roll back, re-select the row that now exists, and apply the
            # same field updates as the update branch instead of a 500.
            await db.rollback()
            result = await db.execute(
                select(PlatformAppCredential).where(
                    PlatformAppCredential.platform == platform
                )
            )
            row = result.scalar_one_or_none()
            if row is None:
                raise
            row.client_id = data.client_id
            if secret:
                row.client_secret = secret
            if data.developer_token is not None:
                row.developer_token = data.developer_token.strip() or None
            row.updated_by_user_id = current_user.user.id
            db.add(
                AuditLog(
                    user_id=current_user.user.id,
                    action=AuditAction.UPDATE,
                    resource_type="platform_app_credential",
                    resource_id=platform,
                    ip_address=request.client.host if request.client else None,
                    user_agent=request.headers.get("User-Agent", "")[:500],
                )
            )
            await db.commit()
    else:
        await db.commit()

    logger.info(
        "platform_app_credentials_saved",
        platform=platform,
        source="database",
        user_id=current_user.user.id,
    )

    has_developer_token = bool(
        (data.developer_token or "").strip() or (row.developer_token if row else None)
    )
    message = f"{PLATFORM_LABELS[platform]} credentials saved"
    if platform == "google" and not has_developer_token:
        message = (
            "Google Ads credentials saved. Warning: no developer token set — "
            "Google Ads API calls will fail until one is added."
        )

    return APIResponse(
        success=True,
        data=CredentialStatus(
            platform=platform,
            configured=True,
            source="database",
            client_id=data.client_id,
            has_developer_token=has_developer_token,
            callback_url=_callback_url(platform),
        ),
        message=message,
    )


@router.delete("/{platform}", response_model=APIResponse[dict])
async def delete_credentials(
    platform: str,
    request: Request,
    current_user: VerifiedUserDep,
    db: AsyncSession = Depends(get_async_session),
):
    platform = _validate_platform(platform)
    result = await db.execute(
        select(PlatformAppCredential).where(PlatformAppCredential.platform == platform)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No stored credentials for {platform}",
        )
    await db.delete(row)
    db.add(
        AuditLog(
            user_id=current_user.user.id,
            action=AuditAction.DELETE,
            resource_type="platform_app_credential",
            resource_id=platform,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("User-Agent", "")[:500],
        )
    )
    await db.commit()
    logger.info(
        "platform_app_credentials_deleted",
        platform=platform,
        user_id=current_user.user.id,
    )
    return APIResponse(success=True, data={"platform": platform, "deleted": True})
