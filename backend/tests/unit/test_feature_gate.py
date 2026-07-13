# =============================================================================
# Stratum AI - Feature Gate unit tests
# =============================================================================
"""
Direct unit coverage for ``app.core.feature_gate`` (STRAT-SC-001 gap fix).

Post single-client conversion, ``FeatureGate`` / ``require_feature`` are the
ONLY gating primitives in the platform: they check one boolean on
``app.core.config.settings`` and either allow the request through or hide
the feature behind a 404. No Redis, no DB, no network — settings flags are
monkeypatched directly on the shared ``settings`` singleton, matching the
seam ``feature_gate.py`` itself reads from (module-level
``from app.core.config import settings``, then ``getattr(settings, ...)``).
"""

import pytest
from fastapi import HTTPException

from app.core.config import settings
from app.core.feature_gate import (
    _FEATURE_SETTINGS_MAP,
    Feature,
    FeatureGate,
    is_feature_enabled,
    require_feature,
)

pytestmark = pytest.mark.unit


# =============================================================================
# is_feature_enabled()
# =============================================================================
class TestIsFeatureEnabled:
    def test_what_if_simulator_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(settings, "feature_what_if_simulator", True)
        assert is_feature_enabled(Feature.WHAT_IF_SIMULATOR) is True

    def test_what_if_simulator_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(settings, "feature_what_if_simulator", False)
        assert is_feature_enabled(Feature.WHAT_IF_SIMULATOR) is False

    def test_gdpr_tools_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(settings, "feature_gdpr_compliance", True)
        assert is_feature_enabled(Feature.GDPR_TOOLS) is True

    def test_gdpr_tools_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(settings, "feature_gdpr_compliance", False)
        assert is_feature_enabled(Feature.GDPR_TOOLS) is False


# =============================================================================
# FeatureGate (FastAPI dependency)
# =============================================================================
class TestFeatureGate:
    async def test_call_passes_when_enabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "feature_what_if_simulator", True)
        gate = FeatureGate(Feature.WHAT_IF_SIMULATOR)
        assert await gate() is None

    async def test_call_raises_404_when_disabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "feature_what_if_simulator", False)
        gate = FeatureGate(Feature.WHAT_IF_SIMULATOR)
        with pytest.raises(HTTPException) as exc:
            await gate()
        assert exc.value.status_code == 404

    async def test_gdpr_tools_call_raises_404_when_disabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "feature_gdpr_compliance", False)
        gate = FeatureGate(Feature.GDPR_TOOLS)
        with pytest.raises(HTTPException) as exc:
            await gate()
        assert exc.value.status_code == 404


# =============================================================================
# require_feature() decorator
# =============================================================================
class TestRequireFeature:
    async def test_wrapped_function_runs_when_enabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "feature_what_if_simulator", True)

        @require_feature(Feature.WHAT_IF_SIMULATOR)
        async def dummy_endpoint(x: int, y: int = 1) -> int:
            """Dummy docstring."""
            return x + y

        result = await dummy_endpoint(2, y=3)
        assert result == 5

    async def test_wrapped_function_raises_404_when_disabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "feature_what_if_simulator", False)

        @require_feature(Feature.WHAT_IF_SIMULATOR)
        async def dummy_endpoint() -> str:
            return "should not run"

        with pytest.raises(HTTPException) as exc:
            await dummy_endpoint()
        assert exc.value.status_code == 404

    async def test_wraps_preserves_function_name(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "feature_gdpr_compliance", True)

        @require_feature(Feature.GDPR_TOOLS)
        async def gdpr_export_endpoint() -> None:
            """Preserve me."""
            return None

        assert gdpr_export_endpoint.__name__ == "gdpr_export_endpoint"
        assert gdpr_export_endpoint.__doc__ == "Preserve me."


# =============================================================================
# Completeness: every Feature member is wired to a settings flag
# =============================================================================
class TestSettingsMapCompleteness:
    def test_every_feature_member_has_a_settings_entry(self) -> None:
        missing = [f for f in Feature if f not in _FEATURE_SETTINGS_MAP]
        assert missing == [], (
            f"Feature member(s) {missing} have no entry in "
            "_FEATURE_SETTINGS_MAP — add one or is_feature_enabled() will "
            "KeyError at request time."
        )

    def test_every_mapped_settings_attr_exists_on_settings(self) -> None:
        missing_attrs: list[str] = [
            flag_name
            for flag_name in _FEATURE_SETTINGS_MAP.values()
            if not hasattr(settings, flag_name)
        ]
        assert missing_attrs == []

    @pytest.mark.parametrize("feature", list(Feature))
    def test_is_feature_enabled_never_keyerrors(
        self, feature: Feature, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Force every mapped flag True so this doubles as a smoke check
        # that getattr() resolves a real attribute, not the getattr(...,
        # False) fallback masking a typo'd flag name.
        flag_name = _FEATURE_SETTINGS_MAP[feature]
        monkeypatch.setattr(settings, flag_name, True)
        assert is_feature_enabled(feature) is True

    def test_feature_enum_has_exactly_two_members(self) -> None:
        # Guards against silent drift between this test file's coverage
        # and the enum: if a member is added without updating the tests
        # above, this fails loudly instead of the new member going
        # untested.
        assert len(list(Feature)) == len(_FEATURE_SETTINGS_MAP) == 2
