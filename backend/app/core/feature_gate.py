# =============================================================================
# Stratum AI - Feature Gate System
# =============================================================================
"""
Environment-driven feature gating.

Single-Client conversion (STRAT-SC-001): this module previously mixed two
gating systems — env-driven feature flags (kept) and subscription-tier /
402-payment-required gating (removed, along with ``core/tiers.py`` and
``core/subscription.py``). ``FeatureGate`` and ``require_feature`` are now
the ONLY gating primitives: they check a single boolean on ``settings`` and
either allow the request through or hide the feature behind a 404, the same
way an unregistered route would look to a caller.

Usage:
    @router.get("/predictive-churn")
    @require_feature(Feature.PREDICTIVE_CHURN)
    async def get_churn_prediction(...):
        ...

    # Or as a dependency
    @router.get("/churn")
    async def get_churn(
        _: None = Depends(FeatureGate(Feature.PREDICTIVE_CHURN))
    ):
        ...
"""

from collections.abc import Callable
from enum import Enum
from functools import wraps

from fastapi import HTTPException, status

from app.core.config import settings


class Feature(str, Enum):
    """Features gated behind a deployment env flag.

    Moved from the now-deleted ``core/tiers.py``. Only the members that are
    actually wired to a ``FeatureGate``/``require_feature`` call site
    survive the tier-mapping cleanup — see ``_FEATURE_SETTINGS_MAP`` below
    for the settings flag each one resolves to.
    """

    WHAT_IF_SIMULATOR = "what_if_simulator"
    GDPR_TOOLS = "gdpr_tools"


# Maps each gated feature to the boolean flag on ``app.core.config.settings``
# that controls it. Add an entry here (and a matching `Settings` field) to
# gate a new feature.
_FEATURE_SETTINGS_MAP: dict[Feature, str] = {
    Feature.WHAT_IF_SIMULATOR: "feature_what_if_simulator",
    Feature.GDPR_TOOLS: "feature_gdpr_compliance",
}


def is_feature_enabled(feature: Feature) -> bool:
    """Check whether a feature's env flag is enabled."""
    flag_name = _FEATURE_SETTINGS_MAP[feature]
    return bool(getattr(settings, flag_name, False))


class FeatureGate:
    """
    FastAPI dependency for env-driven feature gating.

    Usage:
        @router.get("/churn")
        async def get_churn(
            _: None = Depends(FeatureGate(Feature.PREDICTIVE_CHURN))
        ):
            ...
    """

    def __init__(self, feature: Feature):
        self.feature = feature

    async def __call__(self) -> None:
        if not is_feature_enabled(self.feature):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


def require_feature(feature: Feature) -> Callable:
    """
    Decorator for gating endpoints by feature flag.

    Usage:
        @router.get("/predictive-churn")
        @require_feature(Feature.PREDICTIVE_CHURN)
        async def get_churn_prediction(...):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not is_feature_enabled(feature):
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
            return await func(*args, **kwargs)

        return wrapper

    return decorator
