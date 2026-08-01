# =============================================================================
# ADs Growth System - Feature Flags unit tests
# =============================================================================
"""Unit tests for app.features.flags.

Pure feature-gating + autopilot-cap logic, no I/O. Covers org-level defaults,
override merging, feature checks, autopilot level/blocking, and action-cap
validation.

Single-Client conversion (STRAT-SC-001): plan-tier-parameterized defaults
(``PlanTier``, ``DEFAULT_FEATURES_BY_PLAN``) were removed — there is exactly
one organization and exactly one set of defaults (``DEFAULT_ORG_FEATURES``),
so ``get_default_features()`` no longer takes a plan argument.
"""

import pytest

from app.features.flags import (
    DEFAULT_ORG_FEATURES,
    AutopilotLevel,
    can,
    get_autopilot_caps,
    get_autopilot_level,
    get_default_features,
    is_autopilot_blocked,
    merge_features,
    validate_action_within_caps,
)

pytestmark = pytest.mark.unit


# =============================================================================
# Org defaults
# =============================================================================
class TestDefaults:
    def test_returns_the_org_defaults(self):
        feats = get_default_features()
        assert isinstance(feats, dict) and feats
        assert feats == DEFAULT_ORG_FEATURES

    def test_returns_a_copy(self):
        feats = get_default_features()
        feats["signal_health"] = "MUTATED"
        # original is unaffected
        assert get_default_features().get("signal_health") != "MUTATED"
        assert DEFAULT_ORG_FEATURES.get("signal_health") != "MUTATED"


# =============================================================================
# Merge
# =============================================================================
class TestMerge:
    def test_no_overrides_returns_copy(self):
        defaults = {"a": 1}
        merged = merge_features(defaults, None)
        assert merged == defaults
        assert merged is not defaults

    def test_overrides_applied(self):
        merged = merge_features({"a": 1, "b": 2}, {"b": 99})
        assert merged["b"] == 99
        assert merged["a"] == 1

    def test_none_override_ignored(self):
        merged = merge_features({"a": 1}, {"a": None})
        assert merged["a"] == 1


# =============================================================================
# can()
# =============================================================================
class TestCan:
    @pytest.mark.parametrize(
        "features,name,expected",
        [
            ({"f": True}, "f", True),
            ({"f": False}, "f", False),
            ({"f": 5}, "f", True),
            ({"f": 0}, "f", False),
            ({}, "missing", False),
            ({"f": "yes"}, "f", True),
        ],
    )
    def test_can(self, features, name, expected):
        assert can(features, name) is expected


# =============================================================================
# Autopilot caps + level
# =============================================================================
class TestAutopilot:
    def test_caps_shape(self):
        caps = get_autopilot_caps()
        assert caps["max_actions_per_day"] == 10
        assert caps["max_budget_pct_change"] == 30.0

    def test_level_from_features(self):
        assert (
            get_autopilot_level({"autopilot_level": 2})
            == AutopilotLevel.APPROVAL_REQUIRED
        )

    def test_invalid_level_defaults_suggest_only(self):
        assert (
            get_autopilot_level({"autopilot_level": 99}) == AutopilotLevel.SUGGEST_ONLY
        )

    def test_missing_level_defaults_suggest_only(self):
        assert get_autopilot_level({}) == AutopilotLevel.SUGGEST_ONLY


# =============================================================================
# Autopilot blocking
# =============================================================================
class TestBlocking:
    def test_suggest_only_never_blocked(self):
        feats = {"autopilot_level": int(AutopilotLevel.SUGGEST_ONLY)}
        assert is_autopilot_blocked(feats, "critical") is False

    def test_blocked_when_degraded(self):
        feats = {"autopilot_level": int(AutopilotLevel.APPROVAL_REQUIRED)}
        assert is_autopilot_blocked(feats, "degraded") is True

    def test_not_blocked_when_healthy(self):
        feats = {"autopilot_level": int(AutopilotLevel.APPROVAL_REQUIRED)}
        assert is_autopilot_blocked(feats, "healthy") is False


# =============================================================================
# Action caps
# =============================================================================
class TestActionCaps:
    def test_budget_increase_within_cap(self):
        valid, msg = validate_action_within_caps({}, "budget_increase", 20.0)
        assert valid is True
        assert msg is None

    def test_budget_increase_exceeds_cap(self):
        valid, msg = validate_action_within_caps({}, "budget_increase", 40.0)
        assert valid is False
        assert "exceeds" in msg

    def test_budget_decrease_exceeds_cap(self):
        valid, _ = validate_action_within_caps({}, "budget_decrease", 25.0)
        assert valid is False

    def test_custom_caps_respected(self):
        feats = {"max_budget_increase_pct": 50.0}
        valid, _ = validate_action_within_caps(feats, "budget_increase", 40.0)
        assert valid is True
