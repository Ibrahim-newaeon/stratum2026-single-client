# =============================================================================
# ADs Growth System - OAuth App Credential Resolution
# =============================================================================
"""
Resolve per-platform OAuth *application* credentials.

Order: PlatformAppCredential DB row (owner-managed, black-box deployments)
→ env settings fallback (vendor-managed) → CredentialsNotConfigured.
"""

import json
from dataclasses import dataclass, field
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
    "whatsapp": "WhatsApp Business",
}

# platform -> (settings attr: client_id, client_secret, developer_token|None)
# For WhatsApp the three storage slots hold: phone_number_id, access_token,
# business_account_id — the Cloud API has no OAuth app-credential pair.
ENV_CREDENTIAL_FIELDS: dict[str, tuple[str, str, Optional[str]]] = {
    "meta": ("meta_app_id", "meta_app_secret", None),
    "google": (
        "google_ads_client_id",
        "google_ads_client_secret",
        "google_ads_developer_token",
    ),
    "tiktok": ("tiktok_app_id", "tiktok_secret", None),
    "snapchat": ("snapchat_client_id", "snapchat_client_secret", None),
    "whatsapp": (
        "whatsapp_phone_number_id",
        "whatsapp_access_token",
        "whatsapp_business_account_id",
    ),
}

# Platforms that connect via the OAuth authorize/callback flow. WhatsApp is
# direct-API (token-based) and never appears in /oauth/* routes.
OAUTH_PLATFORMS: frozenset[str] = frozenset({"meta", "google", "tiktok", "snapchat"})


@dataclass(frozen=True)
class CredentialFieldSpec:
    """One input the Integrations UI renders for a platform."""

    key: str  # payload key: client_id | client_secret | developer_token | extra.<name>
    label: str
    required: bool
    secret: bool
    maps_to: str  # "client_id" | "client_secret" | "developer_token" | "extra"
    help: str = ""


# Single source of truth for what each platform needs. The frontend renders
# these verbatim; the upsert endpoint validates `extra` keys against them.
PLATFORM_FIELD_SPECS: dict[str, list[CredentialFieldSpec]] = {
    "meta": [
        CredentialFieldSpec("client_id", "App ID", True, False, "client_id",
                            "Meta for Developers → your app → Settings → Basic"),
        CredentialFieldSpec("client_secret", "App Secret", True, True, "client_secret",
                            "Same page as App ID — click Show"),
        CredentialFieldSpec("access_token", "System User Access Token", False, True, "extra",
                            "Long-lived token from Business Settings → System Users; "
                            "enables direct Marketing API access without the OAuth flow"),
        CredentialFieldSpec("ad_account_id", "Ad Account ID", False, False, "extra",
                            "act_XXXXXXXXX from Ads Manager"),
        CredentialFieldSpec("pixel_id", "Pixel ID", False, False, "extra",
                            "Events Manager → your pixel (used by CAPI)"),
    ],
    "whatsapp": [
        CredentialFieldSpec("client_id", "Phone Number ID", True, False, "client_id",
                            "WhatsApp Manager → API Setup → Phone Number ID"),
        CredentialFieldSpec("client_secret", "Access Token", True, True, "client_secret",
                            "Permanent token from a System User with whatsapp_business_messaging"),
        CredentialFieldSpec("developer_token", "Business Account ID (WABA)", True, False,
                            "developer_token",
                            "WhatsApp Business Account ID from Business Settings"),
        CredentialFieldSpec("app_secret", "App Secret", False, True, "extra",
                            "Validates X-Hub-Signature-256 on inbound webhooks"),
        CredentialFieldSpec("verify_token", "Webhook Verify Token", False, True, "extra",
                            "Any string you choose; must match the token entered in the "
                            "Meta app's webhook configuration"),
    ],
    "google": [
        CredentialFieldSpec("client_id", "OAuth Client ID", True, False, "client_id",
                            "Google Cloud Console → Credentials → OAuth 2.0 Client"),
        CredentialFieldSpec("client_secret", "OAuth Client Secret", True, True, "client_secret"),
        CredentialFieldSpec("developer_token", "Developer Token", True, True, "developer_token",
                            "Google Ads → Tools → API Center (Basic/Standard access)"),
        CredentialFieldSpec("login_customer_id", "Login Customer ID (MCC)", False, False, "extra",
                            "Manager account ID without dashes, if you access client "
                            "accounts through an MCC"),
    ],
    "tiktok": [
        CredentialFieldSpec("client_id", "App ID", True, False, "client_id",
                            "TikTok for Business → Developer portal → your app"),
        CredentialFieldSpec("client_secret", "App Secret", True, True, "client_secret"),
        CredentialFieldSpec("advertiser_id", "Advertiser ID", False, False, "extra",
                            "Default advertiser account to operate on"),
    ],
    "snapchat": [
        CredentialFieldSpec("client_id", "Client ID", True, False, "client_id",
                            "Snap Business → Business Details → OAuth Apps"),
        CredentialFieldSpec("client_secret", "Client Secret", True, True, "client_secret"),
        CredentialFieldSpec("organization_id", "Organization ID", False, False, "extra"),
        CredentialFieldSpec("ad_account_id", "Ad Account ID", False, False, "extra"),
    ],
}


def credentials_message(platform: str) -> str:
    label = PLATFORM_LABELS.get(platform, platform)
    return (
        f"{label} app credentials are not configured. "
        "An owner or admin can add them on the Integrations page."
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
    extras: dict[str, str] = field(default_factory=dict)


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
        extras: dict[str, str] = {}
        if row.extra_secrets:
            try:
                parsed = json.loads(row.extra_secrets)
                if isinstance(parsed, dict):
                    extras = {str(k): str(v) for k, v in parsed.items() if v}
            except (ValueError, TypeError):
                extras = {}
        return AppCredentials(
            platform=platform,
            client_id=row.client_id,
            client_secret=row.client_secret,
            developer_token=row.developer_token,
            source="database",
            extras=extras,
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
