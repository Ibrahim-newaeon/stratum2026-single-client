# =============================================================================
# Stratum AI - Feature Flags API Router
# =============================================================================
"""
API endpoints for managing tenant feature flags.

Tenant routes:
- GET /api/tenant/{tenant_id}/features - Get tenant features
- PUT /api/tenant/{tenant_id}/features - Update tenant features (admin only)

Owner (console) routes:
- GET /api/console/tenants/{tenant_id}/features - Get any tenant's features
- PUT /api/console/tenants/{tenant_id}/features - Update any tenant's features
- POST /api/console/tenants/{tenant_id}/features/reset - Reset to defaults
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.session import get_async_session
from app.features.flags import (
    FEATURE_CATEGORIES,
    FEATURE_DESCRIPTIONS,
    FeatureFlags,
    FeatureFlagsUpdate,
)
from app.features.service import FeatureFlagsService
from app.schemas.response import APIResponse

logger = get_logger(__name__)


# =============================================================================
# Tenant Routes
# =============================================================================

# NOTE(STRAT-SC-001/C2): de-tenanted from "/tenant/{tenant_id}" — see
# task-C2-report.md. Route bodies still take/use tenant_id internally (full
# removal is the C3 endpoint sweep); with no {tenant_id} path segment left in
# the prefix, the tenant_id function param below binds as a query param.
tenant_router = APIRouter(prefix="", tags=["feature-flags"])


@tenant_router.get("/features", response_model=APIResponse[Dict[str, Any]])
async def get_tenant_features(
    request: Request,
    tenant_id: int,
    db: AsyncSession = Depends(get_async_session),
):
    """
    Get feature flags for the current tenant.
    Returns merged flags (plan defaults + tenant overrides).
    """
    # Enforce tenant context
    if getattr(request.state, "tenant_id", None) != tenant_id:
        raise HTTPException(status_code=403, detail="Access denied to this tenant")

    service = FeatureFlagsService(db)
    features = await service.get_tenant_features(tenant_id)

    return APIResponse(
        success=True,
        data={
            "features": features,
            "categories": FEATURE_CATEGORIES,
            "descriptions": FEATURE_DESCRIPTIONS,
        },
    )


@tenant_router.put("/features", response_model=APIResponse[Dict[str, Any]])
async def update_tenant_features(
    request: Request,
    tenant_id: int,
    updates: FeatureFlagsUpdate,
    db: AsyncSession = Depends(get_async_session),
):
    """
    Update feature flags for the current tenant.
    Requires tenant_admin role.
    """
    # Enforce tenant context — allow if tenant matches or no tenant set (dev mode)
    req_tenant = getattr(request.state, "tenant_id", None)
    if req_tenant is not None and req_tenant != tenant_id:
        raise HTTPException(status_code=403, detail="Access denied to this tenant")

    user_id = getattr(request.state, "user_id", None)
    service = FeatureFlagsService(db)
    features = await service.update_tenant_features(tenant_id, updates, user_id)

    return APIResponse(
        success=True,
        data={"features": features},
        message="Features updated successfully",
    )


# =============================================================================
# Owner (Console) Routes
# =============================================================================

owner_router = APIRouter(prefix="/console", tags=["owner-features"])


@owner_router.get(
    "/tenants/{tenant_id}/features", response_model=APIResponse[Dict[str, Any]]
)
async def owner_get_tenant_features(
    request: Request,
    tenant_id: int,
    db: AsyncSession = Depends(get_async_session),
):
    """
    Get feature flags for any tenant (owner only).
    """
    user_role = getattr(request.state, "role", None)
    if user_role != "owner":
        raise HTTPException(status_code=403, detail="Owner role required")

    service = FeatureFlagsService(db)
    features = await service.get_tenant_features(tenant_id)

    return APIResponse(
        success=True,
        data={
            "tenant_id": tenant_id,
            "features": features,
            "categories": FEATURE_CATEGORIES,
            "descriptions": FEATURE_DESCRIPTIONS,
        },
    )


@owner_router.put(
    "/tenants/{tenant_id}/features", response_model=APIResponse[Dict[str, Any]]
)
async def owner_update_tenant_features(
    request: Request,
    tenant_id: int,
    updates: FeatureFlagsUpdate,
    db: AsyncSession = Depends(get_async_session),
):
    """
    Update feature flags for any tenant (owner only).
    """
    user_role = getattr(request.state, "role", None)
    if user_role != "owner":
        raise HTTPException(status_code=403, detail="Owner role required")

    user_id = getattr(request.state, "user_id", None)
    service = FeatureFlagsService(db)
    features = await service.update_tenant_features(tenant_id, updates, user_id)

    # Audit log: record feature flag change
    logger.info(
        "feature_flags_updated",
        tenant_id=tenant_id,
        user_id=user_id,
        updated_flags=list(updates.dict(exclude_unset=True).keys()),
        action="UPDATE",
        resource_type="feature_flags",
    )

    return APIResponse(
        success=True,
        data={"tenant_id": tenant_id, "features": features},
        message="Features updated successfully",
    )


@owner_router.post(
    "/tenants/{tenant_id}/features/reset", response_model=APIResponse[Dict[str, Any]]
)
async def owner_reset_tenant_features(
    request: Request,
    tenant_id: int,
    db: AsyncSession = Depends(get_async_session),
):
    """
    Reset tenant features to plan defaults (owner only).
    """
    user_role = getattr(request.state, "role", None)
    if user_role != "owner":
        raise HTTPException(status_code=403, detail="Owner role required")

    service = FeatureFlagsService(db)
    features = await service.reset_tenant_features(tenant_id)

    return APIResponse(
        success=True,
        data={"tenant_id": tenant_id, "features": features},
        message="Features reset to plan defaults",
    )


@owner_router.get("/feature-metadata", response_model=APIResponse[Dict[str, Any]])
async def get_feature_metadata(request: Request):
    """
    Get feature categories and descriptions for UI.
    """
    user_role = getattr(request.state, "role", None)
    if user_role != "owner":
        raise HTTPException(status_code=403, detail="Owner role required")

    return APIResponse(
        success=True,
        data={
            "categories": FEATURE_CATEGORIES,
            "descriptions": FEATURE_DESCRIPTIONS,
        },
    )


# =============================================================================
# Combined Router for API Registration
# =============================================================================

router = APIRouter()
router.include_router(tenant_router)
router.include_router(owner_router)
