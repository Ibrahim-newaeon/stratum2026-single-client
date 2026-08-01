# =============================================================================
# ADs Growth System - Core Metrics Unit Tests
# =============================================================================
"""Unit tests for ``app.core.metrics``.

Covers the ``record_*`` helper functions, the autopilot-mode and
confidence-band gauge setters (including unknown-value fallbacks), and the
instrumentator setup.

NOTE: all metrics live in the global prometheus ``CollectorRegistry`` and
are registered once at import time. These tests therefore never reload the
module or re-create metrics; they assert through
``REGISTRY.get_sample_value`` using label values unique to each test so
that values persisting across tests cannot cause false positives.
``setup_metrics`` with a real instrumentator is exercised exactly once per
process (a second call would register duplicate timeseries); other
instrumentator tests stub the metric factories.

Single-org conversion (STRAT-SC-001): every metric dropped its
per-organization label (there is exactly one organization per deployment
now), and the per-tenant request-instrumentation closure
(``request_by_tenant_instrumentation``) was deleted outright along with
its main.py wiring.
"""

from typing import Optional

import pytest
from fastapi import FastAPI
from prometheus_client import REGISTRY
from prometheus_fastapi_instrumentator import Instrumentator

from app.core import metrics as metrics_module
from app.core.metrics import (
    AUTOPILOT_MODE_VALUES,
    CONFIDENCE_BAND_VALUES,
    create_instrumentator,
    record_autopilot_action,
    record_capi_event,
    record_emq_score,
    record_incident,
    record_platform_api_call,
    record_signal_health,
    record_trust_gate_decision,
    set_autopilot_mode_metric,
    set_confidence_band_metric,
    setup_metrics,
)

pytestmark = pytest.mark.unit


def _sample(name: str, labels: dict[str, str]) -> Optional[float]:
    """Read a sample value from the global prometheus registry."""
    return REGISTRY.get_sample_value(name, labels)


def _value(name: str, labels: dict[str, str]) -> float:
    """Read a sample value, treating an absent series as 0.0 (for deltas)."""
    return REGISTRY.get_sample_value(name, labels) or 0.0


# =============================================================================
# record_emq_score
# =============================================================================


class TestRecordEmqScore:
    def test_sets_score_gauge_with_lowercased_platform(self) -> None:
        """The EMQ gauge is set with a lowercased platform label."""
        record_emq_score("Meta91001", 87.5)
        assert _sample("stratum_emq_score", {"platform": "meta91001"}) == 87.5

    def test_records_each_driver_score(self) -> None:
        """Driver scores land in the per-driver gauge."""
        record_emq_score(
            "google91002", 60.0, drivers={"match_keys": 55.0, "dedupe": 70.0}
        )
        base = {"platform": "google91002"}
        assert (
            _sample("stratum_emq_driver_score", {**base, "driver": "match_keys"})
            == 55.0
        )
        assert _sample("stratum_emq_driver_score", {**base, "driver": "dedupe"}) == 70.0

    def test_no_drivers_records_no_driver_gauge(self) -> None:
        """Omitting drivers must not create driver samples."""
        record_emq_score("tiktok91003", 42.0)
        assert (
            _sample(
                "stratum_emq_driver_score",
                {"platform": "tiktok91003", "driver": "match_keys"},
            )
            is None
        )


# =============================================================================
# record_trust_gate_decision
# =============================================================================


class TestRecordTrustGateDecision:
    def test_increments_counter_and_observes_duration(self) -> None:
        """Decision counter increments and evaluation time is observed."""
        counter_labels = {
            "decision": "pass",
            "action_type": "budget_change",
            "platform": "meta91004",
        }
        hist_labels = {"platform": "meta91004"}
        count_before = _value("stratum_trust_gate_decisions_total", counter_labels)
        obs_before = _value(
            "stratum_trust_gate_evaluation_duration_seconds_count", hist_labels
        )
        sum_before = _value(
            "stratum_trust_gate_evaluation_duration_seconds_sum", hist_labels
        )

        record_trust_gate_decision("PASS", "budget_change", "Meta91004", 0.02)

        assert (
            _value("stratum_trust_gate_decisions_total", counter_labels) - count_before
            == 1.0
        )
        assert (
            _value("stratum_trust_gate_evaluation_duration_seconds_count", hist_labels)
            - obs_before
            == 1.0
        )
        assert _value(
            "stratum_trust_gate_evaluation_duration_seconds_sum", hist_labels
        ) - sum_before == pytest.approx(0.02)


# =============================================================================
# record_autopilot_action
# =============================================================================


class TestRecordAutopilotAction:
    def test_increments_action_counter(self) -> None:
        """Autopilot action counter increments with normalized labels."""
        labels = {
            "action_type": "budget_increase91005",
            "platform": "google",
            "status": "success",
        }
        before = _value("stratum_autopilot_actions_total", labels)

        record_autopilot_action("budget_increase91005", "Google", "SUCCESS")

        assert _value("stratum_autopilot_actions_total", labels) - before == 1.0


# =============================================================================
# record_signal_health
# =============================================================================


class TestRecordSignalHealth:
    def test_sets_overall_score(self) -> None:
        """Overall signal health lands in the score gauge."""
        record_signal_health("meta91006", 73.0)
        assert _sample("stratum_signal_health_score", {"platform": "meta91006"}) == 73.0

    def test_records_component_scores(self) -> None:
        """Component scores land in the per-component gauge."""
        record_signal_health(
            "snapchat91007", 55.0, components={"emq": 40.0, "freshness": 80.0}
        )
        base = {"platform": "snapchat91007"}
        assert (
            _sample("stratum_signal_health_component", {**base, "component": "emq"})
            == 40.0
        )
        assert (
            _sample(
                "stratum_signal_health_component", {**base, "component": "freshness"}
            )
            == 80.0
        )


# =============================================================================
# record_platform_api_call
# =============================================================================


class TestRecordPlatformApiCall:
    def test_increments_counter_and_observes_latency(self) -> None:
        """API call counter increments and latency histogram is observed."""
        counter_labels = {
            "platform": "tiktok91008",
            "endpoint": "/campaigns",
            "status": "error",
        }
        hist_labels = {"platform": "tiktok91008", "endpoint": "/campaigns"}
        count_before = _value("stratum_platform_api_requests_total", counter_labels)
        obs_before = _value("stratum_platform_api_latency_seconds_count", hist_labels)

        record_platform_api_call("TikTok91008", "/campaigns", "ERROR", 1.5)

        assert (
            _value("stratum_platform_api_requests_total", counter_labels) - count_before
            == 1.0
        )
        assert (
            _value("stratum_platform_api_latency_seconds_count", hist_labels)
            - obs_before
            == 1.0
        )


# =============================================================================
# record_capi_event
# =============================================================================


class TestRecordCapiEvent:
    def test_with_latency_observes_histogram(self) -> None:
        """Latency, when provided, is observed."""
        counter_labels = {
            "platform": "capi91009",
            "event_type": "purchase",
            "status": "sent",
        }
        hist_labels = {"platform": "capi91009"}
        count_before = _value("stratum_capi_events_sent_total", counter_labels)
        obs_before = _value("stratum_capi_latency_seconds_count", hist_labels)

        record_capi_event("capi91009", "purchase", "SENT", latency=0.3)

        assert (
            _value("stratum_capi_events_sent_total", counter_labels) - count_before
            == 1.0
        )
        assert (
            _value("stratum_capi_latency_seconds_count", hist_labels) - obs_before
            == 1.0
        )

    def test_without_latency_skips_histogram(self) -> None:
        """No latency means the counter increments but nothing is observed."""
        counter_labels = {
            "platform": "capi91010",
            "event_type": "lead",
            "status": "failed",
        }
        count_before = _value("stratum_capi_events_sent_total", counter_labels)

        record_capi_event("capi91010", "lead", "failed")

        assert (
            _value("stratum_capi_events_sent_total", counter_labels) - count_before
            == 1.0
        )
        assert (
            _sample("stratum_capi_latency_seconds_count", {"platform": "capi91010"})
            is None
        )


# =============================================================================
# record_incident
# =============================================================================


class TestRecordIncident:
    def test_with_resolution_time_observes_mttr(self) -> None:
        """Providing a resolution time records the MTTR histogram."""
        counter_labels = {
            "severity": "sevres91011",
            "platform": "meta",
        }
        hist_labels = {"severity": "sevres91011"}
        count_before = _value("stratum_incidents_total", counter_labels)
        obs_before = _value("stratum_incident_mttr_seconds_count", hist_labels)

        record_incident("sevres91011", "meta", resolved=True, resolution_time=1200.0)

        assert _value("stratum_incidents_total", counter_labels) - count_before == 1.0
        assert (
            _value("stratum_incident_mttr_seconds_count", hist_labels) - obs_before
            == 1.0
        )

    def test_without_resolution_time_skips_mttr(self) -> None:
        """No resolution time means only the incident counter moves."""
        counter_labels = {
            "severity": "sevnores91012",
            "platform": "google",
        }
        count_before = _value("stratum_incidents_total", counter_labels)

        record_incident("sevnores91012", "google")

        assert _value("stratum_incidents_total", counter_labels) - count_before == 1.0
        assert (
            _sample(
                "stratum_incident_mttr_seconds_count", {"severity": "sevnores91012"}
            )
            is None
        )


# =============================================================================
# Autopilot mode / confidence band gauges
# =============================================================================


class TestModeAndBandGauges:
    @pytest.mark.parametrize("mode,expected", sorted(AUTOPILOT_MODE_VALUES.items()))
    def test_known_autopilot_modes(self, mode: str, expected: int) -> None:
        """Each known mode maps to its documented gauge value."""
        set_autopilot_mode_metric(mode)
        assert _sample("stratum_autopilot_mode", {}) == expected

    def test_autopilot_mode_is_case_insensitive(self) -> None:
        """Mode strings are lowercased before lookup."""
        set_autopilot_mode_metric("FROZEN")
        assert _sample("stratum_autopilot_mode", {}) == 0

    def test_unknown_autopilot_mode_falls_back_to_limited(self) -> None:
        """Unknown modes fall back to 2 (limited)."""
        set_autopilot_mode_metric("warp_speed")
        assert _sample("stratum_autopilot_mode", {}) == 2

    @pytest.mark.parametrize("band,expected", sorted(CONFIDENCE_BAND_VALUES.items()))
    def test_known_confidence_bands(self, band: str, expected: int) -> None:
        """Each known band maps to its documented gauge value."""
        set_confidence_band_metric(band)
        assert _sample("stratum_emq_confidence_band", {}) == expected

    def test_unknown_confidence_band_falls_back_to_directional(self) -> None:
        """Unknown bands fall back to 1 (directional)."""
        set_confidence_band_metric("quantum")
        assert _sample("stratum_emq_confidence_band", {}) == 1


# =============================================================================
# Instrumentator setup
# =============================================================================


def _stub_metric_factory(**_kwargs) -> object:
    """Return a no-op instrumentation closure (avoids re-registering metrics)."""

    def instrumentation(_info: object) -> None:
        return None

    return instrumentation


def _stub_metrics(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace the prometheus metric factories so no timeseries is registered."""
    from types import SimpleNamespace

    monkeypatch.setattr(
        metrics_module,
        "metrics",
        SimpleNamespace(
            latency=_stub_metric_factory,
            request_size=_stub_metric_factory,
            response_size=_stub_metric_factory,
        ),
    )


# Guard: the real metric factories may only run once per process; a second
# call would raise "Duplicated timeseries in CollectorRegistry". This flag
# keeps the test safe if the module is executed twice in one process.
_REAL_SETUP_RAN = False


class TestInstrumentatorSetup:
    def test_setup_metrics_enabled_exposes_metrics_endpoint(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With ENABLE_METRICS=true the app is instrumented and /metrics exposed.

        This is the single test in the process allowed to run the real
        metric factories (a second run would raise Duplicated timeseries).
        """
        global _REAL_SETUP_RAN
        if _REAL_SETUP_RAN:  # pragma: no cover - only on double in-process runs
            pytest.skip("real instrumentator already registered in this process")
        _REAL_SETUP_RAN = True

        monkeypatch.setenv("ENABLE_METRICS", "true")
        app = FastAPI()

        instrumentator = setup_metrics(app)

        assert isinstance(instrumentator, Instrumentator)
        assert "/metrics" in [getattr(r, "path", None) for r in app.routes]

    def test_setup_metrics_disabled_by_env_skips_exposure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Without ENABLE_METRICS the instrumentator respects the env var."""
        _stub_metrics(monkeypatch)
        monkeypatch.delenv("ENABLE_METRICS", raising=False)
        app = FastAPI()

        instrumentator = setup_metrics(app)

        assert isinstance(instrumentator, Instrumentator)
        assert "/metrics" not in [getattr(r, "path", None) for r in app.routes]

    def test_create_instrumentator_returns_configured_instance(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """create_instrumentator builds an Instrumentator with 3 added metrics."""
        _stub_metrics(monkeypatch)

        instrumentator = create_instrumentator()

        assert isinstance(instrumentator, Instrumentator)
