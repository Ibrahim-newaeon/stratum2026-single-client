# =============================================================================
# ADs Growth System - Feature Flags API Router
# =============================================================================
"""
API endpoints for managing the organization's feature flags.

Routes:
- GET /features - Get the organization's features (any authenticated user)
- PUT /features - Update the organization's features (owner only)

Owner (console) routes:
- GET /console/features - Get org features (owner-only surface)
- PUT /console/features - Update org features
- POST /console/features/reset - Reset to defaults
- GET /console/feature-metadata - Get category/description metadata
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import CurrentUserDep, require_owner
from app.core.logging import get_logger
from app.db.session import get_async_session
from app.features.flags import (
    FEATURE_CATEGORIES,
    FEATURE_DESCRIPTIONS,
    FeatureFlagsUpdate,
)
from app.features.service import FeatureFlagsService
from app.schemas.response import APIResponse

logger = get_logger(__name__)


# =============================================================================
# Org Routes (de-tenanted; STRAT-SC-001/C3 — singleton org, no per-org path segment)
# =============================================================================
tenant_router = APIRouter(prefix="", tags=["feature-flags"])


@tenant_router.get("/features", response_model=APIResponse[Dict[str, Any]])
async def get_org_features_route(
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_async_session),
):
    """
    Get feature flags for the organization.
    Returns merged flags (org defaults + org overrides).
    """
    service = FeatureFlagsService(db)
    features = await service.get_org_features()

    return APIResponse(
        success=True,
        data={
            "features": features,
            "categories": FEATURE_CATEGORIES,
            "descriptions": FEATURE_DESCRIPTIONS,
        },
    )


@tenant_router.put("/features", response_model=APIResponse[Dict[str, Any]])
async def update_org_features_route(
    updates: FeatureFlagsUpdate,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_async_session),
    _owner=Depends(require_owner()),
):
    """
    Update feature flags for the organization.
    Requires owner role.

    SECURITY (STRAT-SC-001/C3 fix #2): previously gated on
    a request-state identifier that AuthContextMiddleware never sets —
    the guard was a permanent no-op (fail-open, any authenticated caller
    could mutate org feature flags). Replaced with the standard
    `require_owner` dependency.
    """
    service = FeatureFlagsService(db)
    features = await service.update_org_features(updates, current_user.id)

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
    "/features",
    response_model=APIResponse[Dict[str, Any]],
    dependencies=[Depends(require_owner())],  # DB-backed gate (fix 3-1)
)
async def owner_get_org_features(
    request: Request,
    db: AsyncSession = Depends(get_async_session),
):
    """
    Get feature flags for the organization (owner console surface).
    """
    user_role = getattr(request.state, "role", None)
    if user_role != "owner":
        raise HTTPException(status_code=403, detail="Owner role required")

    service = FeatureFlagsService(db)
    features = await service.get_org_features()

    return APIResponse(
        success=True,
        data={
            "features": features,
            "categories": FEATURE_CATEGORIES,
            "descriptions": FEATURE_DESCRIPTIONS,
        },
    )


@owner_router.put(
    "/features",
    response_model=APIResponse[Dict[str, Any]],
    dependencies=[Depends(require_owner())],  # DB-backed gate (fix 3-1)
)
async def owner_update_org_features(
    request: Request,
    updates: FeatureFlagsUpdate,
    db: AsyncSession = Depends(get_async_session),
):
    """
    Update feature flags for the organization (owner only).
    """
    user_role = getattr(request.state, "role", None)
    if user_role != "owner":
        raise HTTPException(status_code=403, detail="Owner role required")

    user_id = getattr(request.state, "user_id", None)
    service = FeatureFlagsService(db)
    features = await service.update_org_features(updates, user_id)

    # Audit log: record feature flag change
    logger.info(
        "feature_flags_updated",
        user_id=user_id,
        updated_flags=list(updates.model_dump(exclude_unset=True).keys()),
        action="UPDATE",
        resource_type="feature_flags",
    )

    return APIResponse(
        success=True,
        data={"features": features},
        message="Features updated successfully",
    )


@owner_router.post(
    "/features/reset",
    response_model=APIResponse[Dict[str, Any]],
    dependencies=[Depends(require_owner())],  # DB-backed gate (fix 3-1)
)
async def owner_reset_org_features(
    request: Request,
    db: AsyncSession = Depends(get_async_session),
):
    """
    Reset organization features to org defaults (owner only).
    """
    user_role = getattr(request.state, "role", None)
    if user_role != "owner":
        raise HTTPException(status_code=403, detail="Owner role required")

    service = FeatureFlagsService(db)
    features = await service.reset_org_features()

    return APIResponse(
        success=True,
        data={"features": features},
        message="Features reset to org defaults",
    )


@owner_router.get(
    "/feature-metadata",
    response_model=APIResponse[Dict[str, Any]],
    dependencies=[Depends(require_owner())],  # DB-backed gate (fix 3-1)
)
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
