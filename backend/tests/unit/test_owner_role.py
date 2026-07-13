from starlette.requests import Request

from app.base_models import UserRole
from app.auth.permissions import ROLE_HIERARCHY, require_owner  # noqa: F401
from app.tenancy.context import TenantContext, get_tenant_context


def test_owner_role_replaces_superadmin() -> None:
    assert UserRole.OWNER.value == "owner"
    assert not hasattr(UserRole, "SUPERADMIN")
    assert ROLE_HIERARCHY[UserRole.OWNER] == 100


def test_owner_role_honors_tenancy_bypass_flags() -> None:
    """app/tenancy/context.py is skip-listed (dies in Phase C) but is still
    live/mounted pre-Phase-C: tenant_dashboard.py's 8 routes depend on
    TenantContext.can_bypass_tenant. Before this fix, the property only
    matched the retired "superadmin" literal, so a real "owner"-role
    token would silently lose cross-tenant bypass (403 instead of
    succeeding). Mirrors TestTenantContext.test_super_admin_flags in
    test_exceptions_tenant_context.py, using the new role string.
    """
    ctx = TenantContext(
        tenant_id=1, user_id=2, role="owner", is_super_admin_bypass=True
    )
    assert ctx.is_super_admin is True
    assert ctx.is_tenant_admin is True
    assert ctx.can_bypass_tenant is True


def test_owner_bypass_header_honored_in_get_tenant_context() -> None:
    """Mirrors TestGetTenantContext.test_superadmin_bypass_header_honored
    in test_exceptions_tenant_context.py, but with role="owner" to cover
    the X-Superadmin-Bypass check inside get_tenant_context (the other
    half of the same regression)."""
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "query_string": b"",
        "headers": [(b"x-superadmin-bypass", b"true")],
        "client": ("127.0.0.1", 1234),
    }
    req = Request(scope)
    req.state.tenant_id = 1
    req.state.user_id = 2
    req.state.role = "owner"

    ctx = get_tenant_context(req)
    assert ctx.is_super_admin_bypass is True
    assert ctx.can_bypass_tenant is True
