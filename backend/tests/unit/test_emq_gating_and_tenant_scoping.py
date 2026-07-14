# =============================================================================
# Stratum AI - EMQ Mode Gating Tests
# =============================================================================
"""
Unit tests for EMQ mode gating rules (autopilot mode restrictions based on
EMQ score). These tests verify critical business rules and safety
constraints.

NOTE(STRAT-SC-001/C3): the tenant-scoping test class this file used to carry
(TestTenantScoping) has been removed — it exercised only local mock
helpers (execute_query/verify_tenant_access/etc., all defined in this file,
never imported from production code) that simulated multi-tenant
isolation. Single-org deployment has no tenant dimension left to isolate,
so those tests and their fictitious tenant/exception scaffolding
(TenantScopingError, TenantAccessDeniedError, TenantMismatchError, etc.)
were deleted outright rather than "re-scoped" — there is nothing real for
them to re-scope to. The EMQ gating logic below is untouched and does not
reference tenant_id at all.
"""

from typing import Any, Dict

import pytest

# =============================================================================
# EMQ Mode Gating Rules Tests
# =============================================================================


class TestEmqModeGating:
    """
    Tests for EMQ mode gating rules.

    Rules:
    - EMQ >= 90: Full autopilot allowed
    - EMQ 80-89: Supervised mode only (human approval required)
    - EMQ 70-79: Alert-only mode (no automatic actions)
    - EMQ < 70: Automation suspended
    """

    def test_full_autopilot_allowed_above_90(self):
        """EMQ >= 90 should allow full autopilot mode."""
        result = determine_allowed_mode(emq_score=95)
        assert result["allowed_modes"] == ["full", "supervised", "alert_only", "off"]
        assert result["max_mode"] == "full"
        assert not result["automation_suspended"]

    def test_supervised_only_between_80_and_89(self):
        """EMQ 80-89 should restrict to supervised mode."""
        result = determine_allowed_mode(emq_score=85)
        assert "full" not in result["allowed_modes"]
        assert result["max_mode"] == "supervised"
        assert not result["automation_suspended"]
        assert (
            "EMQ below threshold" in result["restrictions"][0]
            if result["restrictions"]
            else True
        )

    def test_alert_only_between_70_and_79(self):
        """EMQ 70-79 should restrict to alert-only mode."""
        result = determine_allowed_mode(emq_score=75)
        assert "full" not in result["allowed_modes"]
        assert "supervised" not in result["allowed_modes"]
        assert result["max_mode"] == "alert_only"
        assert not result["automation_suspended"]

    def test_automation_suspended_below_70(self):
        """EMQ < 70 should suspend all automation."""
        result = determine_allowed_mode(emq_score=65)
        assert result["automation_suspended"] == True
        assert result["max_mode"] == "off"
        assert result["allowed_modes"] == ["off"]
        assert len(result["alerts"]) > 0

    def test_mode_downgrade_on_emq_drop(self):
        """Mode should be automatically downgraded when EMQ drops."""
        # Currently in full autopilot mode
        current_mode = "full"

        # EMQ drops to 82
        new_emq = 82
        result = handle_emq_change(current_mode, new_emq, previous_emq=92)

        assert result["mode_changed"] == True
        assert result["new_mode"] == "supervised"
        assert result["reason"] == "EMQ dropped below full autopilot threshold"
        assert result["alert_created"] == True

    def test_no_mode_upgrade_without_approval(self):
        """Mode should not auto-upgrade even if EMQ improves."""
        # Currently in supervised mode
        current_mode = "supervised"

        # EMQ rises to 95
        new_emq = 95
        result = handle_emq_change(current_mode, new_emq, previous_emq=82)

        # Should NOT auto-upgrade
        assert result["mode_changed"] == False
        assert result["new_mode"] == "supervised"
        assert result["upgrade_available"] == True
        assert "manual approval" in result["message"].lower()

    def test_api_health_overrides_emq(self):
        """API health issues should override EMQ gating."""
        result = determine_allowed_mode(emq_score=95, api_health=False)

        assert result["automation_suspended"] == True
        assert result["max_mode"] == "off"
        assert "API health" in str(result["alerts"])

    def test_event_loss_impacts_mode(self):
        """High event loss should restrict mode."""
        # High EMQ but high event loss
        result = determine_allowed_mode(emq_score=92, event_loss_pct=20)

        # Should restrict due to event loss
        assert result["max_mode"] != "full"
        assert "event loss" in str(result["restrictions"]).lower()

    def test_boundary_conditions(self):
        """Test exact boundary values."""
        # Exactly 90
        result_90 = determine_allowed_mode(emq_score=90)
        assert result_90["max_mode"] == "full"

        # Exactly 89.9
        result_89 = determine_allowed_mode(emq_score=89.9)
        assert result_89["max_mode"] == "supervised"

        # Exactly 80
        result_80 = determine_allowed_mode(emq_score=80)
        assert result_80["max_mode"] == "supervised"

        # Exactly 79.9
        result_79 = determine_allowed_mode(emq_score=79.9)
        assert result_79["max_mode"] == "alert_only"

        # Exactly 70
        result_70 = determine_allowed_mode(emq_score=70)
        assert result_70["max_mode"] == "alert_only"

        # Exactly 69.9
        result_69 = determine_allowed_mode(emq_score=69.9)
        assert result_69["automation_suspended"] == True

    def test_mode_gating_with_feature_flags(self):
        """Feature flags should be able to override gating."""
        # With override flag enabled
        result = determine_allowed_mode(
            emq_score=75, feature_flags={"emq_gating_override": True}
        )

        # Should allow full mode despite low EMQ
        assert result["max_mode"] == "full"
        assert result["override_active"] == True
        assert "override" in str(result["warnings"]).lower()


# =============================================================================
# Helper Functions (Mocked implementations for testing)
# =============================================================================


def determine_allowed_mode(
    emq_score: float,
    api_health: bool = True,
    event_loss_pct: float = 0,
    feature_flags: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """Determine allowed autopilot modes based on EMQ and health."""
    feature_flags = feature_flags or {}

    # Check for override
    if feature_flags.get("emq_gating_override"):
        return {
            "allowed_modes": ["full", "supervised", "alert_only", "off"],
            "max_mode": "full",
            "automation_suspended": False,
            "override_active": True,
            "warnings": ["EMQ gating override is active"],
            "restrictions": [],
            "alerts": [],
        }

    result = {
        "allowed_modes": [],
        "max_mode": "off",
        "automation_suspended": False,
        "override_active": False,
        "warnings": [],
        "restrictions": [],
        "alerts": [],
    }

    # API health overrides everything
    if not api_health:
        result["automation_suspended"] = True
        result["max_mode"] = "off"
        result["allowed_modes"] = ["off"]
        result["alerts"].append("API health check failed - automation suspended")
        return result

    # High event loss restricts mode
    if event_loss_pct > 10:
        result["restrictions"].append(
            f"High event loss ({event_loss_pct}%) restricts autopilot"
        )
        emq_score = min(emq_score, 85)  # Cap effective EMQ

    # EMQ-based gating
    if emq_score >= 90:
        result["allowed_modes"] = ["full", "supervised", "alert_only", "off"]
        result["max_mode"] = "full"
    elif emq_score >= 80:
        result["allowed_modes"] = ["supervised", "alert_only", "off"]
        result["max_mode"] = "supervised"
        result["restrictions"].append("EMQ below threshold for full autopilot")
    elif emq_score >= 70:
        result["allowed_modes"] = ["alert_only", "off"]
        result["max_mode"] = "alert_only"
        result["restrictions"].append("EMQ below threshold for supervised mode")
    else:
        result["allowed_modes"] = ["off"]
        result["max_mode"] = "off"
        result["automation_suspended"] = True
        result["alerts"].append(f"Automation suspended: EMQ ({emq_score}) below 70")

    return result


def handle_emq_change(
    current_mode: str, new_emq: float, previous_emq: float
) -> Dict[str, Any]:
    """Handle EMQ score changes and mode adjustments."""
    allowed = determine_allowed_mode(new_emq)

    result = {
        "mode_changed": False,
        "new_mode": current_mode,
        "reason": None,
        "alert_created": False,
        "upgrade_available": False,
        "message": "",
    }

    # Check if current mode is still allowed
    if current_mode not in allowed["allowed_modes"]:
        result["mode_changed"] = True
        result["new_mode"] = allowed["max_mode"]
        result["reason"] = "EMQ dropped below full autopilot threshold"
        result["alert_created"] = True

    # Check if upgrade is available
    if (
        allowed["max_mode"] != current_mode
        and allowed["allowed_modes"].index(allowed["max_mode"])
        < allowed["allowed_modes"].index(current_mode)
        if current_mode in allowed["allowed_modes"]
        else True
    ):
        result["upgrade_available"] = True
        result["message"] = "Upgrade available but requires manual approval"

    return result


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
