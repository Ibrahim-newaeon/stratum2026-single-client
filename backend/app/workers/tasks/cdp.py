# =============================================================================
# Stratum AI - CDP (Customer Data Platform) Tasks
# =============================================================================
"""
Background tasks for CDP segment computation, RFM analysis, and funnels.

Security: Beat-scheduled tasks use distributed locks to prevent
duplicate execution across multiple Celery workers.
"""

from datetime import UTC, datetime
from typing import Any, Optional

from celery import shared_task
from celery.utils.log import get_task_logger
from sqlalchemy import func, select

from app.db.session import SyncSessionLocal
from app.workers.locks import with_distributed_lock
from app.workers.tasks.helpers import publish_event

logger = get_task_logger(__name__)

# Chunk size for paginated profile processing to limit memory usage
CHUNK_SIZE = 500


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def compute_cdp_segment(self, segment_id: str):
    """
    Compute membership for a CDP segment.

    Args:
        segment_id: Segment ID to compute
    """
    logger.info(f"Computing segment {segment_id}")

    # Import CDP models here to avoid circular imports
    from app.models.cdp import CDPProfile, CDPSegment

    with SyncSessionLocal() as db:
        segment = db.execute(
            select(CDPSegment).where(CDPSegment.id == segment_id)
        ).scalar_one_or_none()

        if not segment:
            logger.warning(f"Segment {segment_id} not found")
            return {"status": "not_found"}

        # Process profiles in chunks to limit memory usage
        base_query = (
            select(CDPProfile)
            .where(CDPProfile.is_deleted == False)
            .order_by(CDPProfile.id)
        )

        matched_profiles = []
        offset = 0
        max_iterations = 10_000  # Safety limit: 10k * CHUNK_SIZE = 5M profiles max
        iterations = 0
        while True:
            iterations += 1
            if iterations > max_iterations:
                logger.warning(
                    f"Segment {segment_id} hit max iteration limit ({max_iterations}), "
                    f"processed {offset} profiles"
                )
                break

            chunk = (
                db.execute(base_query.offset(offset).limit(CHUNK_SIZE)).scalars().all()
            )

            if not chunk:
                break

            for profile in chunk:
                result = _evaluate_segment_rules(profile, segment.rules)
                if result["matched"]:
                    matched_profiles.append(profile.id)

            offset += CHUNK_SIZE
            db.expire_all()  # Free ORM objects from identity map

        # Update segment membership
        segment = db.merge(segment)
        segment.profile_ids = matched_profiles
        segment.profile_count = len(matched_profiles)
        segment.last_computed_at = datetime.now(UTC)

        db.commit()

        publish_event(
            "segment_computed",
            {
                "segment_id": segment_id,
                "segment_name": segment.name,
                "profile_count": len(matched_profiles),
            },
        )

    logger.info(f"Segment {segment_id}: {len(matched_profiles)} profiles matched")
    return {"profile_count": len(matched_profiles)}


def _evaluate_segment_rules(profile, rules: dict[str, Any]) -> dict[str, Any]:
    """Evaluate segment rules against a profile."""
    if not rules:
        return {"matched": True, "reason": "no_rules"}

    conditions = rules.get("conditions", [])
    operator = rules.get("operator", "AND")

    results = []
    for condition in conditions:
        matched = _evaluate_condition_single(profile, condition)
        results.append(matched)

    if operator == "AND":
        return {"matched": all(results), "results": results}
    else:  # OR
        return {"matched": any(results), "results": results}


def _evaluate_condition_single(profile, condition: dict[str, Any]) -> bool:
    """Evaluate a single condition against a profile."""
    field = condition.get("field")
    op = condition.get("operator")
    value = condition.get("value")

    # Get field value from profile
    if "." in field:
        # Nested field (e.g., "traits.lifetime_value")
        parts = field.split(".")
        actual = profile
        for part in parts:
            if hasattr(actual, part):
                actual = getattr(actual, part)
            elif isinstance(actual, dict):
                actual = actual.get(part)
            else:
                return False
    else:
        actual = getattr(profile, field, None)

    if actual is None:
        return False

    # Evaluate condition
    if op == "equals":
        return actual == value
    elif op == "not_equals":
        return actual != value
    elif op == "greater_than":
        return float(actual) > float(value)
    elif op == "less_than":
        return float(actual) < float(value)
    elif op == "contains":
        return str(value).lower() in str(actual).lower()
    elif op == "in":
        return actual in value

    return False


@shared_task
@with_distributed_lock(timeout=3600)  # 1 hour lock timeout
def compute_all_cdp_segments():
    """
    Compute all active CDP segments for the org.
    Scheduled hourly by Celery beat.

    Uses distributed lock to prevent duplicate execution across workers.
    """
    logger.info("Computing all CDP segments")

    from app.models.cdp import CDPSegment

    with SyncSessionLocal() as db:
        segments = (
            db.execute(select(CDPSegment).where(CDPSegment.is_active == True))
            .scalars()
            .all()
        )

        task_count = 0
        for segment in segments:
            compute_cdp_segment.delay(str(segment.id))
            task_count += 1

    logger.info(f"Queued {task_count} segment computation tasks")
    return {"tasks_queued": task_count}


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=2,
)
def compute_cdp_rfm(self, config: Optional[dict] = None):
    """
    Compute RFM (Recency, Frequency, Monetary) scores for all profiles.

    Args:
        config: Optional RFM configuration overrides
    """
    logger.info("Computing RFM scores")

    from app.ml.rfm_segmenter import RFMSegmenter
    from app.models.cdp import CDPProfile

    with SyncSessionLocal() as db:
        base_query = (
            select(CDPProfile)
            .where(CDPProfile.is_deleted == False)
            .order_by(CDPProfile.id)
        )

        segmenter = RFMSegmenter()
        total_scored = 0
        all_results: dict[str, Any] = {}
        offset = 0
        max_iterations = 10_000

        for _iter in range(max_iterations):
            chunk = (
                db.execute(base_query.offset(offset).limit(CHUNK_SIZE)).scalars().all()
            )

            if not chunk:
                break

            results = segmenter.compute_rfm_scores(chunk, config)

            # Update profiles with RFM scores
            for profile in chunk:
                rfm = results.get(str(profile.id))
                if rfm:
                    profile.rfm_recency = rfm["recency"]
                    profile.rfm_frequency = rfm["frequency"]
                    profile.rfm_monetary = rfm["monetary"]
                    profile.rfm_segment = rfm["segment"]
                    profile.rfm_score = rfm["score"]
                    total_scored += 1

            all_results.update(results)
            offset += CHUNK_SIZE
            db.commit()
            db.expire_all()  # Free ORM objects from identity map

        if total_scored == 0:
            return {"status": "no_profiles"}

        publish_event(
            "rfm_computed",
            {
                "profiles_scored": total_scored,
                "segment_distribution": all_results.get("distribution", {}),
            },
        )

    logger.info(f"Computed RFM for {total_scored} profiles")
    return {"profiles_scored": total_scored}


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=2,
)
def compute_cdp_traits(self, trait_id: Optional[str] = None):
    """
    Compute computed traits for CDP profiles.

    Args:
        trait_id: Optional specific trait to compute (all if None)
    """
    logger.info("Computing CDP traits")

    from app.models.cdp import CDPComputedTrait, CDPProfile

    with SyncSessionLocal() as db:
        # Get trait definitions
        traits_query = select(CDPComputedTrait).where(
            CDPComputedTrait.is_active == True
        )
        if trait_id:
            traits_query = traits_query.where(CDPComputedTrait.id == trait_id)

        traits = db.execute(traits_query).scalars().all()

        if not traits:
            return {"status": "no_traits"}

        base_query = (
            select(CDPProfile)
            .where(CDPProfile.is_deleted == False)
            .order_by(CDPProfile.id)
        )

        computed_count = 0
        offset = 0
        max_iterations = 10_000

        for _iter in range(max_iterations):
            chunk = (
                db.execute(base_query.offset(offset).limit(CHUNK_SIZE)).scalars().all()
            )

            if not chunk:
                break

            for profile in chunk:
                for trait in traits:
                    try:
                        value = _compute_trait_value(db, profile, trait)
                        profile.computed_traits = profile.computed_traits or {}
                        profile.computed_traits[trait.name] = value
                        computed_count += 1
                    except (ValueError, TypeError, KeyError, AttributeError) as e:
                        logger.error(
                            f"Trait {trait.name} failed for profile {profile.id}: {e}"
                        )

            offset += CHUNK_SIZE
            db.commit()
            db.expire_all()  # Free ORM objects from identity map

    logger.info(f"Computed {computed_count} trait values")
    return {"computed": computed_count}


def _compute_trait_value(db, profile, trait) -> Any:
    """Compute a single trait value for a profile."""
    formula = trait.formula or {}
    trait_type = formula.get("type")

    if trait_type == "count":
        # Count events of a certain type
        event_type = formula.get("event_type")
        # Implementation would query events table
        return 0

    elif trait_type == "sum":
        # Sum a field from events
        field = formula.get("field")
        return 0

    elif trait_type == "last":
        # Get last value of a field
        field = formula.get("field")
        return getattr(profile, field, None)

    elif trait_type == "first":
        # Get first value of a field
        field = formula.get("field")
        return getattr(profile, field, None)

    return None


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=2,
)
def compute_cdp_funnel(self, funnel_id: str):
    """
    Compute conversion funnel metrics.

    Args:
        funnel_id: Funnel definition ID
    """
    logger.info(f"Computing funnel {funnel_id}")

    from app.models.cdp import CDPFunnel

    with SyncSessionLocal() as db:
        funnel = db.execute(
            select(CDPFunnel).where(CDPFunnel.id == funnel_id)
        ).scalar_one_or_none()

        if not funnel:
            return {"status": "not_found"}

        # Compute funnel metrics
        steps = funnel.steps or []
        results = {
            "funnel_id": funnel_id,
            "steps": [],
            "overall_conversion": 0,
        }

        previous_count = 0
        for i, step in enumerate(steps):
            # Count distinct profiles that completed this step's event
            event_name = step.get("event_name") or step.get("name")
            if event_name:
                from app.models.cdp import CDPEvent

                count_result = (
                    db.execute(
                        select(func.count(func.distinct(CDPEvent.profile_id))).where(
                            CDPEvent.event_name == event_name,
                            CDPEvent.profile_id.isnot(None),
                        )
                    ).scalar()
                    or 0
                )
                count = count_result
            else:
                count = 0

            conversion = (count / previous_count * 100) if previous_count > 0 else 100

            results["steps"].append(
                {
                    "step": i + 1,
                    "name": step.get("name"),
                    "count": count,
                    "conversion": round(conversion, 2),
                }
            )
            previous_count = count if count > 0 else previous_count

        # Update funnel with results
        funnel.last_computed_at = datetime.now(UTC)
        funnel.metrics = results

        db.commit()

        publish_event(
            "funnel_computed",
            {
                "funnel_id": funnel_id,
                "funnel_name": funnel.name,
            },
        )

    return results


@shared_task
@with_distributed_lock(timeout=7200)  # 2 hour lock timeout
def compute_all_cdp_funnels():
    """
    Compute all active CDP funnels for the org.
    Scheduled daily by Celery beat.

    Uses distributed lock to prevent duplicate execution across workers.
    """
    logger.info("Computing all CDP funnels")

    from app.models.cdp import CDPFunnel

    with SyncSessionLocal() as db:
        funnels = (
            db.execute(select(CDPFunnel).where(CDPFunnel.is_active == True))
            .scalars()
            .all()
        )

        task_count = 0
        for funnel in funnels:
            compute_cdp_funnel.delay(str(funnel.id))
            task_count += 1

    logger.info(f"Queued {task_count} funnel computation tasks")
    return {"tasks_queued": task_count}
