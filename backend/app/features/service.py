# =============================================================================
# Stratum AI - Feature Flags Service
# =============================================================================
"""
Service layer for managing the organization's feature flags.
Handles fetching, updating, and caching of feature configurations.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.base_models import Organization, get_organization
from app.features.flags import (
    FEATURE_CATEGORIES,
    FEATURE_DESCRIPTIONS,
    PlanTier,
    FeatureFlags,
    FeatureFlagsUpdate,
    get_default_features,
    merge_features,
)

# Single-org deployment: there is no subscription tier, so defaults are drawn
# from the top plan tier rather than a per-org `plan` column (which no longer
# exists post STRAT-SC-001).
DEFAULT_PLAN_TIER = PlanTier.PROFESSIONAL.value


class FeatureFlagsService:
    """Service for managing the organization's feature flags."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_org_features(self) -> Dict[str, Any]:
        """
        Get complete feature flags for the organization.

        Returns:
            Merged feature flags (defaults + overrides)
        """
        org = await get_organization(self.db)
        defaults = get_default_features(DEFAULT_PLAN_TIER)
        return merge_features(defaults, org.feature_flags)

    async def get_feature_flags_model(self) -> FeatureFlags:
        """
        Get feature flags as a validated Pydantic model.

        Returns:
            FeatureFlags model
        """
        features = await self.get_org_features()
        return FeatureFlags(**features)

    async def update_org_features(
        self,
        updates: FeatureFlagsUpdate,
        updated_by_user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Update the organization's feature flags (merge with existing overrides).

        Args:
            updates: Feature flag updates
            updated_by_user_id: ID of user making the update

        Returns:
            Updated feature flags
        """
        org = await get_organization(self.db)
        current_overrides = org.feature_flags or {}

        update_dict = updates.model_dump(exclude_unset=True)
        new_overrides = {**current_overrides, **update_dict}

        await self.db.execute(
            update(Organization)
            .where(Organization.id == org.id)
            .values(
                feature_flags=new_overrides,
                updated_at=datetime.now(timezone.utc),
            )
        )
        await self.db.commit()

        return await self.get_org_features()

    async def reset_org_features(self) -> Dict[str, Any]:
        """
        Reset the organization's features to plan defaults.

        Returns:
            Default feature flags
        """
        org = await get_organization(self.db)
        await self.db.execute(
            update(Organization)
            .where(Organization.id == org.id)
            .values(
                feature_flags={},
                updated_at=datetime.now(timezone.utc),
            )
        )
        await self.db.commit()

        return await self.get_org_features()

    async def can(self, feature_name: str) -> bool:
        """
        Check if a feature is enabled for the organization.

        Args:
            feature_name: Feature name to check

        Returns:
            True if feature is enabled
        """
        features = await self.get_org_features()
        value = features.get(feature_name)

        if value is None:
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return value > 0
        return bool(value)

    def get_feature_categories(self) -> Dict[str, Any]:
        """Get feature categories for UI grouping."""
        return FEATURE_CATEGORIES

    def get_feature_descriptions(self) -> Dict[str, str]:
        """Get feature descriptions for UI display."""
        return FEATURE_DESCRIPTIONS


async def get_org_features(db: AsyncSession) -> Dict[str, Any]:
    """
    Convenience function to get the organization's features.

    Args:
        db: Database session

    Returns:
        Feature flags dict
    """
    service = FeatureFlagsService(db)
    return await service.get_org_features()


async def can_access_feature(db: AsyncSession, feature: str) -> bool:
    """
    Convenience function to check feature access.

    Args:
        db: Database session
        feature: Feature name

    Returns:
        True if feature is enabled
    """
    service = FeatureFlagsService(db)
    return await service.can(feature)
