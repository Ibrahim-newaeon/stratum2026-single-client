# =============================================================================
# ADs Growth System - Creative Fatigue Tasks
# =============================================================================
"""
Background tasks for creative fatigue analysis and alerting.
"""

from celery import shared_task
from celery.utils.log import get_task_logger
from sqlalchemy import select

from app.db.session import SyncSessionLocal
from app.models import CreativeAsset
from app.workers.tasks.helpers import publish_event

logger = get_task_logger(__name__)


# Explicit name: this module was split out of the old app/workers/tasks.py;
# without it the auto-generated name gains the submodule segment and the
# beat schedule's task reference silently dispatches to nothing.
@shared_task(name="app.workers.tasks.calculate_all_fatigue_scores")
def calculate_all_fatigue_scores():
    """
    Calculate creative fatigue scores for all active creatives.
    Scheduled daily by Celery beat.

    NOTE: `app.analytics.logic.fatigue.creative_fatigue` (the real scorer)
    takes `EntityMetrics`/`BaselineMetrics`, not an asset/tenant id lookup —
    this task's per-asset call is a pre-existing signature mismatch,
    unrelated to tenant scoping, left as documented technical debt.
    """
    logger.info("Starting creative fatigue calculation")

    with SyncSessionLocal() as db:
        assets = (
            db.execute(
                select(CreativeAsset).where(
                    CreativeAsset.is_deleted == False,
                    CreativeAsset.is_active == True,
                )
            )
            .scalars()
            .all()
        )

        total_updated = 0
        alerts_sent = 0

        for asset in assets:
            try:
                # Calculate fatigue score using the analytics logic
                from app.analytics.logic.fatigue import calculate_fatigue_score

                score = calculate_fatigue_score(asset_id=asset.id)

                # Update asset with new fatigue score
                asset.fatigue_score = score["score"]
                asset.fatigue_status = score["status"]
                total_updated += 1

                # Send alert if creative needs refresh
                if score["status"] == "REFRESH":
                    publish_event(
                        "creative_fatigue_alert",
                        {
                            "asset_id": asset.id,
                            "asset_name": asset.name,
                            "fatigue_score": score["score"],
                        },
                    )
                    alerts_sent += 1

            except (ValueError, TypeError, KeyError, RuntimeError) as e:
                logger.error(f"Fatigue calc failed for asset {asset.id}: {e}")

        db.commit()

    logger.info(f"Updated {total_updated} fatigue scores, sent {alerts_sent} alerts")
    return {"updated": total_updated, "alerts": alerts_sent}
