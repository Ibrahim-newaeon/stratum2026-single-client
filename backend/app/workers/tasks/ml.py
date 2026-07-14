# =============================================================================
# Stratum AI - ML Prediction Tasks
# =============================================================================
"""
Background tasks for ML predictions and ROAS alerts.
"""

from datetime import UTC, datetime

from celery import shared_task
from celery.utils.log import get_task_logger
from sqlalchemy import select

from app.db.session import SyncSessionLocal
from app.models import Campaign, MLPrediction
from app.workers.locks import with_distributed_lock
from app.workers.tasks.helpers import calculate_task_confidence, publish_event

logger = get_task_logger(__name__)


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=2,
)
def run_live_predictions(self):
    """
    Run live ML predictions for all active campaigns.

    Generates predictions for:
    - ROAS trajectory
    - Conversion probability
    - Budget optimization recommendations
    """
    logger.info("Running live predictions")

    with SyncSessionLocal() as db:
        campaigns = (
            db.execute(
                select(Campaign).where(
                    Campaign.is_deleted == False,
                    Campaign.status == "active",
                )
            )
            .scalars()
            .all()
        )

        if not campaigns:
            return {"status": "no_campaigns"}

        # Prepare campaign data for confidence calculation
        campaign_data = [
            {
                "id": c.id,
                "spend": c.total_spend_cents or 0,
                "roas": c.roas or 0,
            }
            for c in campaigns
        ]
        confidence = calculate_task_confidence(campaign_data, "portfolio")

        predictions = []
        for campaign in campaigns:
            try:
                # Use ROAS optimizer for predictions
                from app.ml.roas_optimizer import ROASOptimizer

                optimizer = ROASOptimizer()
                prediction = optimizer.predict_campaign(campaign.id)

                # Store prediction
                ml_pred = MLPrediction(
                    campaign_id=campaign.id,
                    prediction_type="roas_trajectory",
                    predicted_value=prediction.get("predicted_roas"),
                    confidence=prediction.get("confidence", confidence),
                    features=prediction.get("features"),
                    created_at=datetime.now(UTC),
                )
                db.add(ml_pred)
                predictions.append(prediction)

            except (ValueError, TypeError, KeyError, RuntimeError) as e:
                logger.error(f"Prediction failed for campaign {campaign.id}: {e}")

        db.commit()

        # Publish update event
        publish_event(
            "predictions_updated",
            {
                "count": len(predictions),
                "confidence": confidence,
            },
        )

    logger.info(f"Generated {len(predictions)} predictions")
    return {"predictions": len(predictions), "confidence": confidence}


# Explicit name: this module was split out of the old app/workers/tasks.py;
# without it the auto-generated name gains the submodule segment and the
# beat schedule's task reference silently dispatches to nothing.
@shared_task(name="app.workers.tasks.run_all_predictions")
@with_distributed_lock(timeout=1800)
def run_all_predictions():
    """
    Run predictions for the org.
    Scheduled every 6 hours by Celery beat.
    """
    logger.info("Starting predictions")

    run_live_predictions.delay()
    # Fan out anomaly/ROAS alerting on the same cadence so the safety-signal
    # alerts actually run (previously never dispatched).
    generate_roas_alerts.delay()

    logger.info("Queued predictions + ROAS alerts")
    return {"tasks_queued": 2}


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=2,
)
def generate_roas_alerts(self):
    """
    Generate ROAS/CPA/spend anomaly alerts for all active campaigns.

    Builds a per-campaign daily time series from ``campaign_metrics`` and runs
    the z-score anomaly detector, emitting HIGH/CRITICAL anomalies as real-time
    alerts.
    """
    from app.analytics.logic.anomalies import detect_anomalies
    from app.analytics.logic.types import AnomalyParams
    from app.base_models import CampaignMetric

    logger.info("Generating ROAS alerts")

    params = AnomalyParams(metrics_to_check=["roas", "cpa", "spend"])
    # Baseline window plus today's value.
    lookback = params.window_days + 1

    def _roas(m: "CampaignMetric") -> float:
        spend = (m.spend_cents or 0) / 100.0
        return ((m.revenue_cents or 0) / 100.0) / spend if spend > 0 else 0.0

    def _cpa(m: "CampaignMetric") -> float:
        conv = m.conversions or 0
        return ((m.spend_cents or 0) / 100.0) / conv if conv > 0 else 0.0

    def _spend(m: "CampaignMetric") -> float:
        return (m.spend_cents or 0) / 100.0

    with SyncSessionLocal() as db:
        campaigns = (
            db.execute(
                select(Campaign).where(
                    Campaign.is_deleted == False,
                    Campaign.status == "active",
                )
            )
            .scalars()
            .all()
        )

        alerts = []
        for campaign in campaigns:
            try:
                # Most-recent `lookback` daily rows, then order oldest -> newest.
                rows = (
                    db.execute(
                        select(CampaignMetric)
                        .where(CampaignMetric.campaign_id == campaign.id)
                        .order_by(CampaignMetric.date.desc())
                        .limit(lookback)
                    )
                    .scalars()
                    .all()
                )
                rows = list(reversed(rows))

                # Need >=3 baseline points plus today for a meaningful z-score.
                if len(rows) < 4:
                    continue

                history, today = rows[:-1], rows[-1]
                metrics_series = {
                    "roas": [_roas(m) for m in history],
                    "cpa": [_cpa(m) for m in history],
                    "spend": [_spend(m) for m in history],
                }
                current_values = {
                    "roas": _roas(today),
                    "cpa": _cpa(today),
                    "spend": _spend(today),
                }

                for anomaly in detect_anomalies(metrics_series, current_values, params):
                    if not anomaly.is_anomaly:
                        continue
                    severity = getattr(anomaly.severity, "value", anomaly.severity)
                    if severity not in ("high", "critical"):
                        continue

                    alert = {
                        "campaign_id": campaign.id,
                        "campaign_name": campaign.name,
                        "metric": anomaly.metric,
                        "severity": severity,
                        "z_score": anomaly.zscore,
                        "current_value": anomaly.current_value,
                        "baseline": anomaly.baseline_mean,
                    }
                    alerts.append(alert)

                    # Publish real-time alert
                    publish_event(
                        "roas_alert",
                        alert,
                    )

            # Narrow catch: data-shape issues skip one campaign. A call-signature
            # regression (TypeError) must NOT be swallowed here — that is exactly
            # what previously made this task silently emit zero alerts.
            except (ValueError, KeyError, ZeroDivisionError) as e:
                logger.error(f"Alert generation failed for campaign {campaign.id}: {e}")

    logger.info(f"Generated {len(alerts)} ROAS alerts")
    return {"alerts": len(alerts)}
