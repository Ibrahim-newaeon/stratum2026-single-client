# =============================================================================
# ADs Growth System - Feature Flags System
# =============================================================================
"""
Org-level feature flag system for the single-client deployment.

Single-Client conversion (STRAT-SC-001): this module previously keyed
defaults off a subscription ``PlanTier`` (free/starter/professional/
enterprise/custom) — tiers and plans no longer exist post-conversion (see
``app.core.feature_gate`` for the env-driven kill-switch layer that replaced
tier/402-gating). There is exactly one organization, so there is exactly one
set of defaults: ``DEFAULT_ORG_FEATURES``. ``Organization.feature_flags``
(a JSONB column) stores only the *overrides* the owner has made from those
defaults; ``merge_features()`` combines the two the same way it always did.

Feature Flags:
- signal_health: Trust layer signal health monitoring
- attribution_variance: Trust layer attribution variance tracking
- ai_recommendations: Intelligence layer recommendations
- anomaly_alerts: Intelligence layer anomaly detection alerts
- creative_fatigue: Intelligence layer creative fatigue detection
- campaign_builder: Execution layer campaign builder
- autopilot_level: Execution layer automation level (0-2)
- owner_profitability: Owner-only profitability views
"""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class AutopilotLevel(int, Enum):
    """Autopilot automation levels."""

    SUGGEST_ONLY = 0  # No automatic writes, only suggestions
    GUARDED_AUTO = 1  # Safe actions within caps, requires signal health OK
    APPROVAL_REQUIRED = 2  # All actions require approval before execution


# =============================================================================
# Default Org Feature Flags
# =============================================================================
# The full feature set, enabled by default for the single organization
# (previously the "professional" tier's defaults — preserved as-is so this
# refactor changes no runtime behavior, just removes the now-meaningless
# tier indirection).
DEFAULT_ORG_FEATURES: Dict[str, Any] = {
    "signal_health": True,
    "attribution_variance": True,
    "ai_recommendations": True,
    "anomaly_alerts": True,
    "creative_fatigue": True,
    "campaign_builder": True,
    "autopilot_level": AutopilotLevel.GUARDED_AUTO,
    "owner_profitability": False,
    "max_campaigns": 100,
    "max_users": 20,
    "data_retention_days": 365,
}


# =============================================================================
# Feature Flag Models
# =============================================================================


class FeatureFlags(BaseModel):
    """Complete feature flags configuration for the organization."""

    model_config = ConfigDict(use_enum_values=True)

    # Trust Layer
    signal_health: bool = Field(default=False, description="Signal health monitoring")
    attribution_variance: bool = Field(
        default=False, description="Attribution variance tracking"
    )

    # Intelligence Layer
    ai_recommendations: bool = Field(
        default=False, description="AI-powered recommendations"
    )
    anomaly_alerts: bool = Field(default=True, description="Anomaly detection alerts")
    creative_fatigue: bool = Field(
        default=False, description="Creative fatigue detection"
    )

    # Execution Layer
    campaign_builder: bool = Field(default=False, description="Campaign builder access")
    autopilot_level: int = Field(
        default=0, ge=0, le=2, description="Autopilot automation level"
    )

    # Platform
    owner_profitability: bool = Field(
        default=False, description="Owner profitability views"
    )

    # Limits
    max_campaigns: int = Field(default=20, description="Maximum number of campaigns")
    max_users: int = Field(default=5, description="Maximum number of users")
    data_retention_days: int = Field(default=90, description="Data retention in days")


class FeatureFlagsUpdate(BaseModel):
    """Request model for updating feature flags."""

    signal_health: Optional[bool] = None
    attribution_variance: Optional[bool] = None
    ai_recommendations: Optional[bool] = None
    anomaly_alerts: Optional[bool] = None
    creative_fatigue: Optional[bool] = None
    campaign_builder: Optional[bool] = None
    autopilot_level: Optional[int] = Field(default=None, ge=0, le=2)
    owner_profitability: Optional[bool] = None
    max_campaigns: Optional[int] = None
    max_users: Optional[int] = None
    data_retention_days: Optional[int] = None


# =============================================================================
# Feature Flag Helpers
# =============================================================================


def get_default_features() -> Dict[str, Any]:
    """
    Get the organization's default feature flags.

    Returns:
        A copy of ``DEFAULT_ORG_FEATURES`` (safe to mutate).
    """
    return DEFAULT_ORG_FEATURES.copy()


def merge_features(
    defaults: Dict[str, Any], overrides: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Merge default features with the organization's overrides.

    Args:
        defaults: Default feature flags (see ``DEFAULT_ORG_FEATURES``)
        overrides: Org-specific overrides (from ``Organization.feature_flags`` jsonb)

    Returns:
        Merged feature flags
    """
    if not overrides:
        return defaults.copy()

    merged = defaults.copy()
    for key, value in overrides.items():
        if value is not None:
            merged[key] = value
    return merged


def can(features: Dict[str, Any], feature_name: str) -> bool:
    """
    Check if a feature is enabled.

    Args:
        features: Feature flags dict
        feature_name: Name of feature to check

    Returns:
        True if feature is enabled
    """
    value = features.get(feature_name)
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value > 0
    return bool(value)


def get_autopilot_caps() -> Dict[str, Any]:
    """
    Get default caps for autopilot actions.

    Returns:
        Dict with cap values:
        - max_daily_budget_change: Max absolute budget change per day
        - max_budget_pct_change: Max percentage budget change per action
        - max_actions_per_day: Max automated actions per day
    """
    return {
        "max_daily_budget_change": 500.0,  # Max $500 per day
        "max_budget_pct_change": 30.0,  # Max 30% change per action
        "max_actions_per_day": 10,  # Max 10 automated actions per day
    }


def get_autopilot_level(features: Dict[str, Any]) -> AutopilotLevel:
    """
    Get the autopilot level from features.

    Args:
        features: Feature flags dict

    Returns:
        AutopilotLevel enum value
    """
    level = features.get("autopilot_level", 0)
    try:
        return AutopilotLevel(level)
    except ValueError:
        return AutopilotLevel.SUGGEST_ONLY


def is_autopilot_blocked(features: Dict[str, Any], signal_health_status: str) -> bool:
    """
    Check if autopilot should be blocked due to signal health.

    Args:
        features: Feature flags dict
        signal_health_status: Current signal health status (healthy/risk/degraded/critical)

    Returns:
        True if autopilot should be blocked
    """
    autopilot_level = get_autopilot_level(features)

    # Suggest-only never auto-executes, so not "blocked"
    if autopilot_level == AutopilotLevel.SUGGEST_ONLY:
        return False

    # Block if signal health is degraded or critical
    if signal_health_status in ["degraded", "critical"]:
        return True

    return False


def validate_action_within_caps(
    features: Dict[str, Any],
    action_type: str,
    change_pct: float,
) -> tuple[bool, Optional[str]]:
    """
    Validate if an action is within allowed caps.

    Default caps:
    - Budget increase: max 30% per day
    - Budget decrease: max 20% per day

    Args:
        features: Feature flags dict
        action_type: Type of action (budget_increase, budget_decrease)
        change_pct: Percentage change

    Returns:
        Tuple of (is_valid, error_message)
    """
    max_increase = features.get("max_budget_increase_pct", 30.0)
    max_decrease = features.get("max_budget_decrease_pct", 20.0)

    if action_type == "budget_increase" and change_pct > max_increase:
        return False, f"Budget increase {change_pct:.1f}% exceeds max {max_increase}%"

    if action_type == "budget_decrease" and change_pct > max_decrease:
        return False, f"Budget decrease {change_pct:.1f}% exceeds max {max_decrease}%"

    return True, None


# =============================================================================
# Feature Categories (for UI grouping)
# =============================================================================

FEATURE_CATEGORIES = {
    "trust_layer": {
        "name": "Trust Layer",
        "description": "Data quality and transparency features",
        "features": ["signal_health", "attribution_variance"],
    },
    "intelligence_layer": {
        "name": "Intelligence Layer",
        "description": "AI-powered insights and recommendations",
        "features": ["ai_recommendations", "anomaly_alerts", "creative_fatigue"],
    },
    "execution_layer": {
        "name": "Execution Layer",
        "description": "Campaign building and automation",
        "features": ["campaign_builder", "autopilot_level"],
    },
    "platform": {
        "name": "Platform Features",
        "description": "Platform-level features",
        "features": ["owner_profitability"],
    },
    "limits": {
        "name": "Usage Limits",
        "description": "Account usage limits",
        "features": ["max_campaigns", "max_users", "data_retention_days"],
    },
}


FEATURE_DESCRIPTIONS = {
    "signal_health": "Monitor data quality with EMQ scores and event loss tracking",
    "attribution_variance": "Track differences between platform and GA4 attribution",
    "ai_recommendations": "Get AI-powered recommendations for campaign optimization",
    "anomaly_alerts": "Receive alerts when metrics show unusual patterns",
    "creative_fatigue": "Detect when creatives are losing effectiveness",
    "campaign_builder": "Create and publish campaigns directly from ADs Growth System",
    "autopilot_level": "Automation level: 0=Suggest, 1=Auto with caps, 2=Approval required",
    "owner_profitability": "Access platform-wide profitability and usage analytics",
    "max_campaigns": "Maximum number of active campaigns",
    "max_users": "Maximum number of team members",
    "data_retention_days": "How long historical data is kept",
}
