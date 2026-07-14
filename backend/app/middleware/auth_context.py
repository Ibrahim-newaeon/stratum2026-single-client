# =============================================================================
# Stratum AI - Auth Context Middleware
# =============================================================================
"""
Middleware that decodes the request's JWT (if any) and establishes the
authenticated-user context for downstream handlers.

STRAT-SC-001 (single-client conversion, Task C2): this replaces the previous
multi-tenant middleware. All tenant extraction (JWT claim, tenant header,
subdomain lookup, per-request tenant/bypass state) is gone —
there is exactly one organization now, so there is nothing to disambiguate.
What's preserved verbatim from the predecessor's dispatch(): the
PUBLIC_ENDPOINTS allowlist + _is_public_endpoint prefix rules, the JWT decode,
and the AUTH-001 token-type/blacklist enforcement (failing OPEN if Redis is
down, but still rejecting non-"access" token types regardless of Redis).
"""

import re
from typing import Callable, Optional

import jwt
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from jwt.exceptions import PyJWTError as JWTError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Endpoints that don't require auth context
PUBLIC_ENDPOINTS = {
    "/health",
    "/health/ready",
    "/health/live",
    # Prometheus scrapes without auth (see infrastructure/prometheus). Keep
    # /metrics blocked from the public internet at the ingress/ALB layer.
    "/metrics",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/api/v1/auth/login",
    # MFA second step: the client only holds the challenge mfa_token from the
    # login response body (no bearer token yet) — the endpoint
    # self-authenticates by decoding that token.
    "/api/v1/auth/login/mfa",
    "/api/v1/auth/register",
    "/api/v1/auth/refresh",
    "/api/v1/auth/forgot-password",
    "/api/v1/auth/reset-password",
    "/api/v1/auth/accept-invite",
    "/api/v1/auth/verify-email",
    "/api/v1/auth/resend-verification",
    "/api/v1/auth/email/send-otp",
    "/api/v1/auth/email/verify-otp",
    "/api/v1/auth/whatsapp/send-otp",
    "/api/v1/auth/whatsapp/verify-otp",
}


class AuthContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware that decodes the JWT (if present) and enforces token validity.

    Sets request.state.user_id/role/cms_role for downstream handlers.
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Decode the JWT once, enforce AUTH-001, and set the user context."""

        # Always allow CORS preflight requests through (they carry no auth)
        if request.method == "OPTIONS":
            return await call_next(request)

        # Skip public endpoints
        if self._is_public_endpoint(request.url.path):
            return await call_next(request)

        # Decode JWT once and cache the payload on request.state
        jwt_payload = self._decode_jwt_once(request)

        # SECURITY (AUTH-001): a decoded token is not enough — it must be an
        # *access* token and must not have been revoked (logout / password
        # reset / forced sign-out add the token's jti to the Redis blacklist).
        # Without this, a revoked or refresh token sails through until it
        # naturally expires.
        if jwt_payload is not None:
            if jwt_payload.get("type") != "access":
                return self._reject(
                    "Invalid token type",
                    "This endpoint requires an access token",
                )
            if await self._is_revoked(jwt_payload, request):
                return self._reject(
                    "Token revoked",
                    "Your session has ended. Please sign in again.",
                )

        request.state._jwt_payload = jwt_payload

        user_id = jwt_payload.get("sub") if jwt_payload else None
        if user_id is not None:
            try:
                user_id = int(user_id)
            except (ValueError, TypeError):
                user_id = None
        role = jwt_payload.get("role") if jwt_payload else None
        cms_role = jwt_payload.get("cms_role") if jwt_payload else None

        # Set user and role context on request state
        request.state.user_id = user_id
        request.state.role = role or "analyst"  # Default role if not in token
        request.state.cms_role = cms_role  # CMS role (None if not a CMS user)

        # Bind to structured logging context
        import structlog

        structlog.contextvars.bind_contextvars(user_id=user_id, role=role)

        return await call_next(request)

    def _decode_jwt_once(self, request: Request) -> Optional[dict]:
        """Decode the JWT token once and return the payload dict, or None."""
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return None

        token = auth_header.split(" ")[1]

        try:
            return jwt.decode(
                token,
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm],
            )
        except JWTError:
            return None

    @staticmethod
    def _reject(error: str, message: str) -> JSONResponse:
        """Build a 401 for a token that decoded but is not usable."""
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"success": False, "error": error, "message": message},
        )

    async def _is_revoked(self, payload: dict, request: Request) -> bool:
        """Return True if this token has been blacklisted (AUTH-001).

        Fails OPEN on Redis unavailability: a blacklist outage must not turn
        into a total auth outage, and tokens still expire on their own. The
        gap is logged so the degradation is visible rather than silent.
        """
        from app.core.security import is_token_blacklisted

        auth_header = request.headers.get("Authorization", "")
        token = auth_header.split(" ", 1)[1] if " " in auth_header else ""
        try:
            return await is_token_blacklisted(payload, token)
        except (ConnectionError, TimeoutError, OSError) as exc:
            logger.warning(
                "token_blacklist_check_unavailable",
                error=str(exc),
                detail="Allowing request; revocation not enforced this hop",
            )
            return False

    def _is_public_endpoint(self, path: str) -> bool:
        """Check if the endpoint is public (no auth context needed)."""
        if path in PUBLIC_ENDPOINTS:
            return True
        if path.startswith("/docs") or path.startswith("/redoc"):
            return True
        # OAuth provider callbacks arrive as browser redirects from the ad
        # platform with no JWT header; auth comes from the Redis-stored
        # state token the endpoint validates (CSRF check).
        if re.fullmatch(r"/api/v1/oauth/[^/]+/callback", path):
            return True
        # Allow webhook endpoints (they authenticate via signature/verify-token, not JWT).
        # STRAT-SC-001 (E1): a blanket `/api/v1/webhooks/` prefix match here used to
        # also swallow the owner-gated webhooks-management router (same /webhooks
        # prefix, see app/api/v1/endpoints/webhooks.py) — every sub-route
        # (/event-types, /{id}, /{id}/test, /{id}/deliveries) skipped auth-context
        # setup and 401'd unconditionally. Narrowed to the exact two inbound
        # SendGrid receiver routes (app/api/v1/endpoints/sendgrid_webhook.py),
        # which self-authenticate via a URL token, not JWT.
        if path in ("/api/v1/webhooks/sendgrid", "/api/v1/webhooks/sendgrid/test"):
            return True
        # WhatsApp platform webhooks (self-authenticate via Meta HMAC signature /
        # hub.verify_token challenge, not JWT).
        if path.startswith("/api/v1/whatsapp/webhooks/"):
            return True
        # Programmatic API — authenticates via the X-API-Key header, not a JWT.
        # The api-key dependency (get_api_key_principal) validates the key.
        # Every /programmatic/* route MUST depend on APIKeyPrincipalDep /
        # require_api_key_scope so auth context is always established downstream.
        if path.startswith("/api/v1/programmatic/"):
            return True
        # CMS public endpoints — content is global, read-only
        if path.startswith("/api/v1/cms/") and "/admin/" not in path:
            return True
        # Landing CMS — public, read-only published marketing content
        if path.startswith("/api/v1/landing-cms"):
            return True
        return False
