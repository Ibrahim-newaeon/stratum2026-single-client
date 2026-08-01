# =============================================================================
# ADs Growth System - Prometheus Metrics Configuration
# =============================================================================
"""
Prometheus metrics for ADs Growth System backend.

Exposes:
- Standard HTTP metrics (request count, latency histograms)
- Custom business metrics (EMQ scores, trust gate decisions)
- System health metrics

Integration:
- Uses prometheus-fastapi-instrumentator for HTTP metrics
- Custom collectors for business-specific metrics
"""

from typing import Optional

from fastapi import FastAPI
from prometheus_client import Counter, Gauge, Histogram
from prometheus_fastapi_instrumentator import Instrumentator, metrics

# =============================================================================
# Custom Business Metrics
# =============================================================================

# EMQ (Event Measurement Quality) Metrics
emq_score_gauge = Gauge(
    name="stratum_emq_score",
    documentation="Current EMQ score by platform",
    labelnames=["platform"],
)

emq_driver_gauge = Gauge(
    name="stratum_emq_driver_score",
    documentation="EMQ driver component scores",
    labelnames=["platform", "driver"],
)

emq_confidence_band = Gauge(
    name="stratum_emq_confidence_band",
    documentation="EMQ confidence band (0=unsafe, 1=directional, 2=reliable)",
)

# Trust Gate Metrics
trust_gate_decisions_total = Counter(
    name="stratum_trust_gate_decisions_total",
    documentation="Total trust gate decisions by outcome",
    labelnames=["decision", "action_type", "platform"],
)

trust_gate_evaluation_duration = Histogram(
    name="stratum_trust_gate_evaluation_duration_seconds",
    documentation="Time spent evaluating trust gate decisions",
    labelnames=["platform"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)

# Autopilot Metrics
autopilot_mode_gauge = Gauge(
    name="stratum_autopilot_mode",
    documentation="Current autopilot mode (0=frozen, 1=cuts_only, 2=limited, 3=normal)",
)

autopilot_actions_total = Counter(
    name="stratum_autopilot_actions_total",
    documentation="Total autopilot actions executed",
    labelnames=["action_type", "platform", "status"],
)

autopilot_budget_at_risk = Gauge(
    name="stratum_autopilot_budget_at_risk_usd",
    documentation="Budget at risk due to signal health issues",
)

# Signal Health Metrics
signal_health_score = Gauge(
    name="stratum_signal_health_score",
    documentation="Overall signal health score",
    labelnames=["platform"],
)

signal_health_component = Gauge(
    name="stratum_signal_health_component",
    documentation="Signal health component scores",
    labelnames=["platform", "component"],
)

signal_volatility_index = Gauge(
    name="stratum_signal_volatility_index",
    documentation="Signal Volatility Index (SVI)",
)

# Platform Integration Metrics
platform_api_requests_total = Counter(
    name="stratum_platform_api_requests_total",
    documentation="Total API requests to ad platforms",
    labelnames=["platform", "endpoint", "status"],
)

platform_api_latency = Histogram(
    name="stratum_platform_api_latency_seconds",
    documentation="Latency for ad platform API calls",
    labelnames=["platform", "endpoint"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
)

platform_sync_status = Gauge(
    name="stratum_platform_sync_status",
    documentation="Platform data sync status (0=failed, 1=success)",
    labelnames=["platform"],
)

platform_sync_last_success = Gauge(
    name="stratum_platform_sync_last_success_timestamp",
    documentation="Timestamp of last successful platform sync",
    labelnames=["platform"],
)

# Conversion API (CAPI) Metrics
capi_events_sent_total = Counter(
    name="stratum_capi_events_sent_total",
    documentation="Total conversion events sent via CAPI",
    labelnames=["platform", "event_type", "status"],
)

capi_match_rate = Gauge(
    name="stratum_capi_match_rate",
    documentation="CAPI event match rate percentage",
    labelnames=["platform"],
)

capi_latency = Histogram(
    name="stratum_capi_latency_seconds",
    documentation="Latency for CAPI event delivery",
    labelnames=["platform"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# Attribution Metrics
attribution_variance = Gauge(
    name="stratum_attribution_variance_pct",
    documentation="Attribution variance between platform and GA4",
    labelnames=["platform"],
)

# Incident Metrics
incidents_total = Counter(
    name="stratum_incidents_total",
    documentation="Total incidents by severity",
    labelnames=["severity", "platform"],
)

incidents_open = Gauge(
    name="stratum_incidents_open",
    documentation="Currently open incidents",
    labelnames=["severity"],
)

incident_mttr_seconds = Histogram(
    name="stratum_incident_mttr_seconds",
    documentation="Mean time to resolution for incidents",
    labelnames=["severity"],
    buckets=(300, 900, 1800, 3600, 7200, 14400, 28800, 86400),
)

# Celery Task Metrics
celery_task_duration = Histogram(
    name="stratum_celery_task_duration_seconds",
    documentation="Duration of Celery task execution",
    labelnames=["task_name", "status"],
    buckets=(0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 300.0),
)

celery_tasks_total = Counter(
    name="stratum_celery_tasks_total",
    documentation="Total Celery tasks by name and status",
    labelnames=["task_name", "status"],
)


# =============================================================================
# Helper Functions for Recording Metrics
# =============================================================================


def record_emq_score(
    platform: str,
    score: float,
    drivers: Optional[dict] = None,
) -> None:
    """
    Record EMQ score metrics.

    Args:
        platform: Ad platform (meta, google, tiktok, snapchat)
        score: EMQ score (0-100)
        drivers: Optional dict of driver scores
    """
    emq_score_gauge.labels(
        platform=platform.lower(),
    ).set(score)

    if drivers:
        for driver_name, driver_score in drivers.items():
            emq_driver_gauge.labels(
                platform=platform.lower(),
                driver=driver_name,
            ).set(driver_score)


def record_trust_gate_decision(
    decision: str,
    action_type: str,
    platform: str,
    evaluation_time: float,
) -> None:
    """
    Record trust gate decision metrics.

    Args:
        decision: Gate decision (pass, hold, block)
        action_type: Type of automation action
        platform: Ad platform
        evaluation_time: Time taken to evaluate (seconds)
    """
    trust_gate_decisions_total.labels(
        decision=decision.lower(),
        action_type=action_type,
        platform=platform.lower(),
    ).inc()

    trust_gate_evaluation_duration.labels(
        platform=platform.lower(),
    ).observe(evaluation_time)


def record_autopilot_action(
    action_type: str,
    platform: str,
    status: str,
) -> None:
    """
    Record autopilot action execution.

    Args:
        action_type: Type of action executed
        platform: Ad platform
        status: Execution status (success, failed, blocked)
    """
    autopilot_actions_total.labels(
        action_type=action_type,
        platform=platform.lower(),
        status=status.lower(),
    ).inc()


def record_signal_health(
    platform: str,
    overall_score: float,
    components: Optional[dict] = None,
) -> None:
    """
    Record signal health metrics.

    Args:
        platform: Ad platform
        overall_score: Overall health score (0-100)
        components: Optional dict of component scores (emq, freshness, variance, anomaly)
    """
    signal_health_score.labels(
        platform=platform.lower(),
    ).set(overall_score)

    if components:
        for component_name, component_score in components.items():
            signal_health_component.labels(
                platform=platform.lower(),
                component=component_name,
            ).set(component_score)


def record_platform_api_call(
    platform: str,
    endpoint: str,
    status: str,
    latency: float,
) -> None:
    """
    Record platform API call metrics.

    Args:
        platform: Ad platform name
        endpoint: API endpoint called
        status: Response status (success, error, timeout)
        latency: Request latency in seconds
    """
    platform_api_requests_total.labels(
        platform=platform.lower(),
        endpoint=endpoint,
        status=status.lower(),
    ).inc()

    platform_api_latency.labels(
        platform=platform.lower(),
        endpoint=endpoint,
    ).observe(latency)


def record_capi_event(
    platform: str,
    event_type: str,
    status: str,
    latency: Optional[float] = None,
) -> None:
    """
    Record CAPI event metrics.

    Args:
        platform: Ad platform name
        event_type: Type of conversion event
        status: Delivery status (sent, failed, deduplicated)
        latency: Optional delivery latency in seconds
    """
    capi_events_sent_total.labels(
        platform=platform.lower(),
        event_type=event_type,
        status=status.lower(),
    ).inc()

    if latency is not None:
        capi_latency.labels(
            platform=platform.lower(),
        ).observe(latency)


def record_incident(
    severity: str,
    platform: str,
    resolved: bool = False,
    resolution_time: Optional[float] = None,
) -> None:
    """
    Record incident metrics.

    Args:
        severity: Incident severity (critical, high, medium, low)
        platform: Affected platform
        resolved: Whether incident is resolved
        resolution_time: Optional time to resolution in seconds
    """
    incidents_total.labels(
        severity=severity.lower(),
        platform=platform.lower(),
    ).inc()

    if resolution_time is not None:
        incident_mttr_seconds.labels(
            severity=severity.lower(),
        ).observe(resolution_time)


# =============================================================================
# Instrumentator Setup
# =============================================================================


def create_instrumentator() -> Instrumentator:
    """
    Create and configure the Prometheus instrumentator.

    Returns:
        Configured Instrumentator instance
    """
    instrumentator = Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        should_respect_env_var=True,
        should_instrument_requests_inprogress=True,
        excluded_handlers=[
            "/health",
            "/health/ready",
            "/health/live",
            "/metrics",
            "/docs",
            "/redoc",
            "/openapi.json",
        ],
        env_var_name="ENABLE_METRICS",
        inprogress_name="stratum_http_requests_inprogress",
        inprogress_labels=True,
    )

    # Add default metrics (latency histogram).
    # metric_name overrides the library default ("http_request_duration_seconds")
    # because namespace+subsystem already contribute the "stratum_http_" prefix —
    # otherwise the emitted name doubles up as stratum_http_http_request_...
    # The resulting names must stay in sync with infrastructure/prometheus/alerts.yml
    # and infrastructure/grafana/dashboards/.
    instrumentator.add(
        metrics.latency(
            metric_name="request_duration_seconds",
            metric_namespace="stratum",
            metric_subsystem="http",
            buckets=(
                0.01,
                0.025,
                0.05,
                0.075,
                0.1,
                0.25,
                0.5,
                0.75,
                1.0,
                1.5,
                2.0,
                2.5,
                3.0,
                3.5,
                4.0,
                4.5,
                5.0,
                7.5,
                10.0,
                30.0,
                60.0,
            ),
        )
    )

    # Add request size metrics
    instrumentator.add(
        metrics.request_size(
            metric_name="request_size_bytes",
            metric_namespace="stratum",
            metric_subsystem="http",
        )
    )

    # Add response size metrics
    instrumentator.add(
        metrics.response_size(
            metric_name="response_size_bytes",
            metric_namespace="stratum",
            metric_subsystem="http",
        )
    )

    return instrumentator


def setup_metrics(app: FastAPI) -> Instrumentator:
    """
    Setup Prometheus metrics for the FastAPI application.

    This function:
    1. Creates the instrumentator with default HTTP metrics
    2. Instruments the app
    3. Exposes the /metrics endpoint

    Args:
        app: FastAPI application instance

    Returns:
        Configured Instrumentator instance
    """
    instrumentator = create_instrumentator()

    # Instrument the app
    instrumentator.instrument(app)

    # Expose the /metrics endpoint
    instrumentator.expose(
        app,
        endpoint="/metrics",
        include_in_schema=True,
        tags=["Monitoring"],
    )

    return instrumentator


# =============================================================================
# Autopilot Mode Mapping
# =============================================================================

AUTOPILOT_MODE_VALUES = {
    "frozen": 0,
    "cuts_only": 1,
    "limited": 2,
    "normal": 3,
}

CONFIDENCE_BAND_VALUES = {
    "unsafe": 0,
    "directional": 1,
    "reliable": 2,
}


def set_autopilot_mode_metric(mode: str) -> None:
    """
    Set the autopilot mode gauge.

    Args:
        mode: Autopilot mode (frozen, cuts_only, limited, normal)
    """
    mode_value = AUTOPILOT_MODE_VALUES.get(mode.lower(), 2)
    autopilot_mode_gauge.set(mode_value)


def set_confidence_band_metric(band: str) -> None:
    """
    Set the EMQ confidence band gauge.

    Args:
        band: Confidence band (unsafe, directional, reliable)
    """
    band_value = CONFIDENCE_BAND_VALUES.get(band.lower(), 1)
    emq_confidence_band.set(band_value)
