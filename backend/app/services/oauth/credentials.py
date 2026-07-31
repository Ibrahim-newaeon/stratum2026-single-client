# =============================================================================
# Stratum AI - OAuth App Credential Resolution
# =============================================================================
"""
Resolve per-platform OAuth *application* credentials.

Order: PlatformAppCredential DB row (owner-managed, black-box deployments)
→ env settings fallback (vendor-managed) → CredentialsNotConfigured.
"""

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.platform_app_credential import PlatformAppCredential

PLATFORM_LABELS: dict[str, str] = {
    "meta": "Meta",
    "google": "Google Ads",
    "tiktok": "TikTok",
    "snapchat": "Snapchat",
}

# platform -> (settings attr: client_id, client_secret, developer_token|None)
ENV_CREDENTIAL_FIELDS: dict[str, tuple[str, str, Optional[str]]] = {
    "meta": ("meta_app_id", "meta_app_secret", None),
    "google": (
        "google_ads_client_id",
        "google_ads_client_secret",
        "google_ads_developer_token",
    ),
    "tiktok": ("tiktok_app_id", "tiktok_secret", None),
    "snapchat": ("snapchat_client_id", "snapchat_client_secret", None),
}


def credentials_message(platform: str) -> str:
    label = PLATFORM_LABELS.get(platform, platform)
    return (
        f"{label} app credentials are not configured. "
        "An owner or admin can add them under Settings → Integrations."
    )


class CredentialsNotConfigured(Exception):
    """No DB row and no env vars for this platform's OAuth app."""

    def __init__(self, platform: str) -> None:
        self.platform = platform
        super().__init__(credentials_message(platform))


@dataclass(frozen=True)
class AppCredentials:
    platform: str
    client_id: str
    client_secret: str
    developer_token: Optional[str]
    source: str  # "database" | "environment"


async def resolve_app_credentials(platform: str, db: AsyncSession) -> AppCredentials:
    """DB-first, env-fallback resolution of a platform's app credentials."""
    platform = platform.lower()
    if platform not in ENV_CREDENTIAL_FIELDS:
        raise CredentialsNotConfigured(platform)

    result = await db.execute(
        select(PlatformAppCredential).where(PlatformAppCredential.platform == platform)
    )
    row = result.scalar_one_or_none()
    if row is not None and row.client_id and row.client_secret:
        return AppCredentials(
            platform=platform,
            client_id=row.client_id,
            client_secret=row.client_secret,
            developer_token=row.developer_token,
            source="database",
        )

    id_attr, secret_attr, dev_attr = ENV_CREDENTIAL_FIELDS[platform]
    client_id = getattr(settings, id_attr, None)
    client_secret = getattr(settings, secret_attr, None)
    if client_id and client_secret:
        return AppCredentials(
            platform=platform,
            client_id=client_id,
            client_secret=client_secret,
            developer_token=getattr(settings, dev_attr, None) if dev_attr else None,
            source="environment",
        )

    raise CredentialsNotConfigured(platform)
