# =============================================================================
# ADs Growth System - Authentication & Authorization Module
# =============================================================================
"""
Authentication and authorization components including:
- RBAC permissions system
- JWT token handling
- Role and permission dependencies
"""

from app.auth.permissions import (
    ROLE_PERMISSIONS,
    Permission,
    get_user_permissions,
    has_permission,
    require_owner,
    require_permissions,
    require_role,
)

__all__ = [
    "ROLE_PERMISSIONS",
    "Permission",
    "get_user_permissions",
    "has_permission",
    "require_owner",
    "require_permissions",
    "require_role",
]
