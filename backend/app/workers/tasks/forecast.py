# =============================================================================
# ADs Growth System - Forecasting Tasks
# =============================================================================
"""
Background tasks for ML-based forecasting and predictions.
"""

from typing import Optional

from celery import shared_task
from celery.utils.log import get_task_logger
from sqlalchemy import select

from app.db.session import SyncSessionLocal
from app.models import Campaign
from app.workers.locks import with_distributed_lock

logger = get_task_logger(__name__)


@shared_task
def generate_forecast(campaign_ids: Optional[list[int]] = None):
    """
    Generate forecast for specified campaigns or all campaigns.

    Args:
        campaign_ids: Optional list of campaign IDs (all if None)

    NOTE: `PacingForecaster.__init__` takes an `AsyncSession` and has no
    `generate_campaign_forecast` method — this task's call is a pre-existing
    signature mismatch (sync task calling an async-only service incorrectly),
    unrelated to tenant scoping, left as documented technical debt.
    """
    logger.info("Generating forecast")

    with SyncSessionLocal() as db:
        query = select(Campaign).where(Campaign.is_deleted == False)

        if campaign_ids:
            query = query.where(Campaign.id.in_(campaign_ids))

        campaigns = db.execute(query).scalars().all()

        forecasts = []
        for campaign in campaigns:
            try:
                # Use the pacing forecaster service
                from app.services.pacing.forecasting import PacingForecaster

                forecaster = PacingForecaster(db)
                forecast = forecaster.generate_campaign_forecast(campaign.id)
                forecasts.append(
                    {
                        "campaign_id": campaign.id,
                        "forecast": forecast,
                    }
                )
            except (ValueError, TypeError, KeyError, RuntimeError) as e:
                logger.error(f"Forecast failed for campaign {campaign.id}: {e}")

    logger.info(f"Generated {len(forecasts)} forecasts")
    return {"forecasts_generated": len(forecasts)}


# Explicit name: this module was split out of the old app/workers/tasks.py;
# without it the auto-generated name gains the submodule segment and the
# beat schedule's task reference silently dispatches to nothing.
@shared_task(name="app.workers.tasks.generate_daily_forecasts")
@with_distributed_lock(timeout=1800)
def generate_daily_forecasts():
    """
    Generate daily forecasts for all active campaigns.
    Scheduled daily by Celery beat.
    """
    logger.info("Starting daily forecast generation")

    generate_forecast.delay()

    logger.info("Queued forecast task")
    return {"tasks_queued": 1}
