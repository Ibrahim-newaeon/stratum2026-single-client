# =============================================================================
# ADs Growth System - Platform App Credentials CRUD (owner/admin)
# =============================================================================
"""
Owner/admin management of per-deployment OAuth app credentials.

Secrets are write-only: accepted in PUT bodies, stored encrypted
(EncryptedString), and never serialized back in any response.
"""

import json
from typing import Optional

import httpx
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
from app.services.oauth.credentials import (
    ENV_CREDENTIAL_FIELDS,
    OAUTH_PLATFORMS,
    PLATFORM_FIELD_SPECS,
    PLATFORM_LABELS,
    CredentialsNotConfigured,
    resolve_app_credentials,
)
from app.services.whatsapp_client import refresh_whatsapp_credentials

logger = get_logger(__name__)

router = APIRouter(
    prefix="/platform-credentials",
    dependencies=[Depends(require_admin())],
)

_VALID_PLATFORMS = set(ENV_CREDENTIAL_FIELDS.keys())


def _callback_url(platform: str) -> str:
    base_url = settings.oauth_redirect_base_url.rstrip("/")
    if platform == "whatsapp":
        # No OAuth flow — surface the webhook verification URL the owner
        # must paste into the Meta app's WhatsApp webhook configuration.
        return f"{base_url}/api/v1/whatsapp/webhooks/verify"
    return f"{base_url}/api/v1/oauth/{platform}/callback"


class FieldSpecOut(BaseModel):
    key: str
    label: str
    required: bool
    secret: bool
    maps_to: str
    help: str = ""


def _field_specs(platform: str) -> list[FieldSpecOut]:
    return [
        FieldSpecOut(
            key=s.key,
            label=s.label,
            required=s.required,
            secret=s.secret,
            maps_to=s.maps_to,
            help=s.help,
        )
        for s in PLATFORM_FIELD_SPECS.get(platform, [])
    ]


def _valid_extra_keys(platform: str) -> set[str]:
    return {
        s.key for s in PLATFORM_FIELD_SPECS.get(platform, []) if s.maps_to == "extra"
    }


def _row_extra_dict(row: Optional[PlatformAppCredential]) -> dict[str, str]:
    if row is None or not row.extra_secrets:
        return {}
    try:
        parsed = json.loads(row.extra_secrets)
        return {str(k): str(v) for k, v in parsed.items() if v} if isinstance(parsed, dict) else {}
    except (ValueError, TypeError):
        return {}


class CredentialUpsertRequest(BaseModel):
    client_id: str = Field(..., min_length=1, max_length=255)
    client_secret: Optional[str] = Field(default=None, max_length=1024)
    developer_token: Optional[str] = Field(default=None, max_length=1024)
    # Platform-specific extra fields (validated against PLATFORM_FIELD_SPECS).
    # Send a key with an empty string to clear it; omit keys to keep them.
    extra: Optional[dict[str, str]] = Field(default=None)

    @field_validator("client_id")
    @classmethod
    def strip_client_id(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("client_id must not be blank")
        return v


class CredentialStatus(BaseModel):
    platform: str
    label: str
    configured: bool
    source: Optional[str]  # "database" | "environment" | None
    client_id: Optional[str]
    has_developer_token: bool
    callback_url: str
    oauth: bool  # True → connects via OAuth flow; False → direct API (WhatsApp)
    fields: list[FieldSpecOut]
    # Which optional extra fields currently hold a value (names only, never values)
    extra_configured: list[str]


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
                    label=PLATFORM_LABELS[platform],
                    configured=True,
                    source="database",
                    client_id=row.client_id,
                    has_developer_token=bool(row.developer_token),
                    callback_url=_callback_url(platform),
                    oauth=platform in OAUTH_PLATFORMS,
                    fields=_field_specs(platform),
                    extra_configured=sorted(_row_extra_dict(row).keys()),
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
                label=PLATFORM_LABELS[platform],
                configured=env_configured,
                source="environment" if env_configured else None,
                client_id=env_id if env_configured else None,
                has_developer_token=bool(
                    dev_attr and getattr(settings, dev_attr, None)
                ),
                callback_url=_callback_url(platform),
                oauth=platform in OAUTH_PLATFORMS,
                fields=_field_specs(platform),
                extra_configured=[],
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

    # Validate + merge extra fields against the platform's spec. Empty string
    # clears a key; omitted keys keep their stored value.
    extra_update = data.extra or {}
    invalid_keys = set(extra_update.keys()) - _valid_extra_keys(platform)
    if invalid_keys:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown extra fields for {platform}: {sorted(invalid_keys)}",
        )

    def _merged_extras(existing: dict[str, str]) -> Optional[str]:
        merged = dict(existing)
        for k, v in extra_update.items():
            v = v.strip()
            if v:
                merged[k] = v
            else:
                merged.pop(k, None)
        return json.dumps(merged) if merged else None

    created = row is None
    if row is None:
        row = PlatformAppCredential(
            platform=platform,
            client_id=data.client_id,
            client_secret=secret,
            developer_token=(data.developer_token or "").strip() or None,
            extra_secrets=_merged_extras({}),
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
        if data.extra is not None:
            row.extra_secrets = _merged_extras(_row_extra_dict(row))
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
            if data.extra is not None:
                row.extra_secrets = _merged_extras(_row_extra_dict(row))
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

    if platform == "whatsapp":
        # Keep the sync client factory's cache in step with the DB row.
        await refresh_whatsapp_credentials(db)

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
            label=PLATFORM_LABELS[platform],
            configured=True,
            source="database",
            client_id=data.client_id,
            has_developer_token=has_developer_token,
            callback_url=_callback_url(platform),
            oauth=platform in OAUTH_PLATFORMS,
            fields=_field_specs(platform),
            extra_configured=sorted(_row_extra_dict(row).keys()),
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

    if platform == "whatsapp":
        await refresh_whatsapp_credentials(db)
    logger.info(
        "platform_app_credentials_deleted",
        platform=platform,
        user_id=current_user.user.id,
    )
    return APIResponse(success=True, data={"platform": platform, "deleted": True})


# =============================================================================
# Connection test
# =============================================================================


class ConnectionTestResult(BaseModel):
    platform: str
    ok: bool
    # "valid" | "invalid" | "configured_unverified" | "not_configured" | "unreachable"
    status: str
    detail: str
    metadata: Optional[dict] = None


_GRAPH_TIMEOUT = httpx.Timeout(12.0)


async def _test_meta(creds) -> ConnectionTestResult:
    """Validate Meta credentials against the Graph API.

    Prefers the saved system-user access token (GET /me) when present;
    otherwise validates App ID + App Secret via the client_credentials grant.
    """
    version = settings.whatsapp_api_version or "v18.0"
    async with httpx.AsyncClient(timeout=_GRAPH_TIMEOUT) as client:
        access_token = (creds.extras or {}).get("access_token")
        if access_token:
            resp = await client.get(
                f"https://graph.facebook.com/{version}/me",
                params={"access_token": access_token, "fields": "id,name"},
            )
            body = resp.json() if resp.content else {}
            if resp.status_code == 200 and body.get("id"):
                return ConnectionTestResult(
                    platform="meta",
                    ok=True,
                    status="valid",
                    detail=f"Access token valid — authenticated as {body.get('name') or body['id']}.",
                    metadata={"tested": "system_user_token", "identity": body.get("name")},
                )
            err = (body.get("error") or {}).get("message", f"HTTP {resp.status_code}")
            return ConnectionTestResult(
                platform="meta",
                ok=False,
                status="invalid",
                detail=f"Access token rejected: {err}",
            )

        resp = await client.get(
            f"https://graph.facebook.com/{version}/oauth/access_token",
            params={
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
                "grant_type": "client_credentials",
            },
        )
        body = resp.json() if resp.content else {}
        if resp.status_code == 200 and body.get("access_token"):
            return ConnectionTestResult(
                platform="meta",
                ok=True,
                status="valid",
                detail="App ID and App Secret are valid. Use Connect to complete "
                "the OAuth flow for ad-account access.",
                metadata={"tested": "app_credentials"},
            )
        err = (body.get("error") or {}).get("message", f"HTTP {resp.status_code}")
        return ConnectionTestResult(
            platform="meta", ok=False, status="invalid",
            detail=f"App credentials rejected: {err}",
        )


async def _test_whatsapp(creds) -> ConnectionTestResult:
    """Validate WhatsApp Cloud API credentials by reading the phone number."""
    version = settings.whatsapp_api_version or "v18.0"
    async with httpx.AsyncClient(timeout=_GRAPH_TIMEOUT) as client:
        resp = await client.get(
            f"https://graph.facebook.com/{version}/{creds.client_id}",
            params={"fields": "display_phone_number,verified_name,quality_rating"},
            headers={"Authorization": f"Bearer {creds.client_secret}"},
        )
        body = resp.json() if resp.content else {}
        if resp.status_code == 200 and body.get("id"):
            name = body.get("verified_name")
            phone = body.get("display_phone_number")
            return ConnectionTestResult(
                platform="whatsapp",
                ok=True,
                status="valid",
                detail=f"Connected to {name or 'WhatsApp Business'} ({phone}).",
                metadata={
                    "verified_name": name,
                    "display_phone_number": phone,
                    "quality_rating": body.get("quality_rating"),
                },
            )
        err = (body.get("error") or {}).get("message", f"HTTP {resp.status_code}")
        return ConnectionTestResult(
            platform="whatsapp",
            ok=False,
            status="invalid",
            detail=f"WhatsApp API rejected the credentials: {err}",
        )


@router.post("/{platform}/test", response_model=APIResponse[ConnectionTestResult])
async def test_credentials(
    platform: str,
    current_user: VerifiedUserDep,
    db: AsyncSession = Depends(get_async_session),
):
    """Live connection test for saved (or env-configured) platform credentials.

    Meta and WhatsApp are verified against the Graph API. Google/TikTok/
    Snapchat cannot be verified without an OAuth exchange, so a configured
    credential set reports `configured_unverified` — the real proof is the
    Connect (OAuth) flow.
    """
    platform = _validate_platform(platform)
    try:
        creds = await resolve_app_credentials(platform, db)
    except CredentialsNotConfigured:
        return APIResponse(
            success=True,
            data=ConnectionTestResult(
                platform=platform,
                ok=False,
                status="not_configured",
                detail=f"{PLATFORM_LABELS[platform]} credentials are not configured yet.",
            ),
        )

    try:
        if platform == "meta":
            result = await _test_meta(creds)
        elif platform == "whatsapp":
            result = await _test_whatsapp(creds)
        else:
            missing = [
                s.label
                for s in PLATFORM_FIELD_SPECS[platform]
                if s.required and s.maps_to == "developer_token"
                and not creds.developer_token
            ]
            detail = (
                f"{PLATFORM_LABELS[platform]} credentials are saved. This platform "
                "can only be fully verified by completing the Connect (OAuth) flow."
            )
            if missing:
                detail += f" Warning: missing {', '.join(missing)}."
            result = ConnectionTestResult(
                platform=platform,
                ok=not missing,
                status="configured_unverified",
                detail=detail,
            )
    except httpx.HTTPError as e:
        result = ConnectionTestResult(
            platform=platform,
            ok=False,
            status="unreachable",
            detail=f"Could not reach the platform API: {e.__class__.__name__}. "
            "Check outbound network access and retry.",
        )

    logger.info(
        "platform_credentials_tested",
        platform=platform,
        status=result.status,
        ok=result.ok,
        user_id=current_user.user.id,
    )
    return APIResponse(success=True, data=result)
