from app.auth.permissions import ROLE_HIERARCHY, require_owner  # noqa: F401
from app.base_models import UserRole


def test_owner_role_replaces_superadmin() -> None:
    assert UserRole.OWNER.value == "owner"
    assert not hasattr(UserRole, "SUPERADMIN")
    assert ROLE_HIERARCHY[UserRole.OWNER] == 100
