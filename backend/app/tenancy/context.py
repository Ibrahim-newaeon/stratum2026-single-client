# =============================================================================
# Stratum AI - Tenant Context
# =============================================================================
"""
TenantContext dataclass and extraction utilities.

The TenantContext contains all tenant-scoped information needed for
request processing, including tenant_id, user_id, role, and workspace.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from fastapi import Request


@dataclass
class TenantContext:
    """
    Request-scoped tenant context.

    Contains all information needed for tenant isolation and RBAC.
    This is extracted from JWT claims and request headers.
    """

    # Required fields
    tenant_id: int
    user_id: int
    role: str

    # Optional fields
    workspace_id: Optional[int] = None
    email: Optional[str] = None

    # Super admin bypass flag
    is_super_admin_bypass: bool = False

    # Request metadata
    request_id: Optional[str] = None
    request_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_super_admin(self) -> bool:
        """Check if the user is a super admin.

        NOTE(fix-loop/STRAT-SC-001): this module is on the Phase-C skip
        list (rewritten/deleted wholesale in C2) but is still live/mounted
        pre-Phase-C — tenant_dashboard.py's routes depend on it. B1 renamed
        the RBAC role string "superadmin" -> "owner" everywhere else; this
        checks both literals (rather than renaming outright) so real
        "owner"-role tokens get the same bypass treatment without breaking
        the frozen "superadmin" literal still asserted by
        test_exceptions_tenant_context.py (deliberately left untouched by
        B1 since it tests this skip-listed module directly).
        """
        return self.role.lower() in ("owner", "superadmin")

    @property
    def is_tenant_admin(self) -> bool:
        """Check if the user is a tenant admin or higher."""
        return self.role.lower() in ("owner", "superadmin", "admin")

    @property
    def can_bypass_tenant(self) -> bool:
        """Check if this context allows cross-tenant access."""
        return self.is_super_admin and self.is_super_admin_bypass

    def to_audit_dict(self) -> dict:
        """
        Convert context to dictionary for audit logging.

        Returns:
            Dictionary with audit-relevant fields
        """
        return {
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "role": self.role,
            "workspace_id": self.workspace_id,
            "is_super_admin_bypass": self.is_super_admin_bypass,
            "request_id": self.request_id,
            "request_time": self.request_time.isoformat(),
        }


def get_tenant_context(request: Request) -> Optional[TenantContext]:
    """
    Extract TenantContext from a FastAPI request.

    This function reads from request.state which is populated
    by authentication middleware.

    Args:
        request: FastAPI Request object

    Returns:
        TenantContext if available, None otherwise
    """
    # Check if tenant context is already cached
    cached_context = getattr(request.state, "tenant_context", None)
    if cached_context:
        return cached_context

    # Extract required fields
    tenant_id = getattr(request.state, "tenant_id", None)
    user_id = getattr(request.state, "user_id", None)
    role = getattr(request.state, "role", None)

    # All required fields must be present
    if tenant_id is None or user_id is None or not role:
        return None

    # Check for super admin bypass header
    is_bypass = request.headers.get("X-Superadmin-Bypass", "").lower() == "true"

    # Only super admins can use the bypass
    # NOTE(fix-loop/STRAT-SC-001): accept both "owner" (post-B1-rename) and
    # the legacy "superadmin" literal here — see is_super_admin docstring
    # above for why this file keeps both instead of a straight rename.
    if is_bypass and role.lower() not in ("owner", "superadmin"):
        is_bypass = False

    # Build context
    context = TenantContext(
        tenant_id=tenant_id,
        user_id=user_id,
        role=role,
        workspace_id=getattr(request.state, "workspace_id", None),
        email=getattr(request.state, "email", None),
        is_super_admin_bypass=is_bypass,
        request_id=request.headers.get("X-Request-ID"),
    )

    # Cache in request state
    request.state.tenant_context = context

    return context


def create_system_context(tenant_id: int) -> TenantContext:
    """
    Create a system-level tenant context for background tasks.

    This context has super admin privileges and is used for
    Celery tasks and internal operations.

    Args:
        tenant_id: The tenant ID for the operation

    Returns:
        TenantContext with system privileges
    """
    return TenantContext(
        tenant_id=tenant_id,
        user_id=0,  # System user
        role="superadmin",
        is_super_admin_bypass=True,
        request_id="system",
    )
