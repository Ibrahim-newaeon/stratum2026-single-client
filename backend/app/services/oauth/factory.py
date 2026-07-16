# =============================================================================
# Stratum AI - OAuth Service Factory
# =============================================================================
"""
Factory function to get the appropriate OAuth service for a platform.
"""

from typing import Optional

from app.services.oauth.base import OAuthService
from app.services.oauth.credentials import AppCredentials
from app.services.oauth.google import GoogleOAuthService
from app.services.oauth.meta import MetaOAuthService
from app.services.oauth.snapchat import SnapchatOAuthService
from app.services.oauth.tiktok import TikTokOAuthService

# Registry of OAuth services by platform
_OAUTH_SERVICES: dict[str, type[OAuthService]] = {
    "meta": MetaOAuthService,
    "google": GoogleOAuthService,
    "tiktok": TikTokOAuthService,
    "snapchat": SnapchatOAuthService,
}


def get_oauth_service(
    platform: str, credentials: Optional[AppCredentials] = None
) -> OAuthService:
    """
    Get a fresh OAuth service instance for a platform.

    A new instance is built on every call (no singleton cache) so that
    per-request resolved app credentials (DB-first, env-fallback) never
    leak across requests. When `credentials` is omitted, the service
    falls back to whatever it read from settings in `__init__` (unchanged
    behavior for callers that don't yet resolve credentials, e.g. workers).

    Args:
        platform: Platform identifier (meta, google, tiktok, snapchat)
        credentials: Optional resolved app credentials to inject

    Returns:
        OAuthService instance for the platform

    Raises:
        ValueError: If platform is not supported
    """
    platform_lower = platform.lower()

    service_class = _OAUTH_SERVICES.get(platform_lower)
    if service_class is None:
        raise ValueError(
            f"Unsupported platform: {platform}. "
            f"Supported platforms: {', '.join(_OAUTH_SERVICES.keys())}"
        )

    service = service_class()
    if credentials is not None:
        service.apply_credentials(credentials)
    return service


def get_supported_platforms() -> list[str]:
    """Get list of supported OAuth platforms."""
    return list(_OAUTH_SERVICES.keys())
