# =============================================================================
# Stratum AI - Daily Scoring Tasks
# =============================================================================
"""
Background tasks for daily score calculations (scaling, health, etc.).
"""

from datetime import UTC, datetime

from celery import shared_task
from celery.utils.log import get_task_logger
from sqlalchemy import select

from app.db.session import SyncSessionLocal
from app.models import Campaign
from app.workers.tasks.helpers import publish_event

logger = get_task_logger(__name__)


# Explicit name: this module was split out of the old app/workers/tasks.py;
# without it the auto-generated name gains the submodule segment and the
# beat schedule's task reference silently dispatches to nothing.
@shared_task(name="app.workers.tasks.calculate_daily_scores")
def calculate_daily_scores():
    """
    Calculate daily performance scores for all campaigns (org-wide).
    Scheduled daily by Celery beat.

    Calculates:
    - Scaling scores (scale/watch/fix recommendations)
    - Health scores (0-100 composite)
    - Signal health for trust engine

    NOTE: pre-existing, unrelated to tenant scoping — the real functions are
    `app.analytics.logic.scoring.scaling_score`, `app.ml.roas_optimizer.
    ROASOptimizer._calculate_health_score` (private, takes a campaign dict +
    thresholds, not a campaign_id), and `app.analytics.logic.signal_health.
    signal_health` (takes metrics, not IDs) — none match the names/signatures
    called below. Documented technical debt, not fixed here.
    """
    logger.info("Starting daily score calculations")

    with SyncSessionLocal() as db:
        campaigns = (
            db.execute(
                select(Campaign).where(
                    Campaign.is_deleted == False,
                    Campaign.status.in_(["active", "paused"]),
                )
            )
            .scalars()
            .all()
        )

        total_scored = 0
        for campaign in campaigns:
            try:
                # Calculate scaling score
                from app.analytics.logic.scoring import calculate_scaling_score

                scaling = calculate_scaling_score(campaign_id=campaign.id)
                campaign.scaling_score = scaling.get("score")
                campaign.scaling_recommendation = scaling.get("recommendation")

                # Calculate health score
                from app.ml.roas_optimizer import ROASOptimizer

                optimizer = ROASOptimizer()
                health = optimizer.calculate_health_score(campaign.id)
                campaign.health_score = health.get("score")

                # Calculate signal health for trust engine
                from app.analytics.logic.signal_health import (
                    calculate_signal_health,
                )

                signal = calculate_signal_health(campaign_id=campaign.id)
                campaign.signal_health = signal.get("score")
                campaign.signal_health_status = signal.get("status")

                total_scored += 1

            except (ValueError, TypeError, KeyError, RuntimeError) as e:
                logger.error(f"Scoring failed for campaign {campaign.id}: {e}")

        db.commit()

        # Publish scores updated event
        publish_event(
            "scores_updated",
            {
                "campaigns_scored": len(campaigns),
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )

    logger.info(f"Calculated scores for {total_scored} campaigns")
    return {"campaigns_scored": total_scored}
