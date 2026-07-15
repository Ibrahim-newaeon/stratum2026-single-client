# =============================================================================
# Stratum AI - Owner Console Dashboard Endpoints
# =============================================================================
"""
Owner console endpoints for platform-level management.

Features:
- System health monitoring
- Audit logging
- Environment-driven platform connection / demo-data seeding
- Credential presence health check
- Anomaly rollup
"""

from datetime import date, datetime, timedelta, timezone
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import get_async_session
from app.models import Campaign, User, UserRole
from app.schemas import APIResponse

logger = get_logger(__name__)
router = APIRouter()


# =============================================================================
# Dependencies
# =============================================================================
def require_owner(request: Request) -> int:
    """Verify user has owner role."""
    user_role = getattr(request.state, "role", None)
    user_id = getattr(request.state, "user_id", None)

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    if user_role != UserRole.OWNER.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner access required",
        )

    return user_id


# =============================================================================
# System Health Endpoints
# =============================================================================
@router.get("/system/health", response_model=APIResponse)
async def get_system_health(
    request: Request,
    db: AsyncSession = Depends(get_async_session),
):
    """
    Get system health metrics.
    Owner only.
    """
    require_owner(request)

    # Collect real system health where possible
    import redis.asyncio as aioredis

    from app.core.config import settings

    # Check Redis/Celery queue depth (real data)
    queue_depth = 0
    redis_healthy = False
    try:
        redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
        queue_depth = await redis_client.llen("celery") or 0
        redis_healthy = await redis_client.ping()
        await redis_client.close()
    except (ConnectionError, TimeoutError, OSError) as exc:
        logger.warning(f"Redis health check failed: {exc}")

    # Check DB connectivity (real data)
    db_healthy = False
    try:
        from sqlalchemy import text

        await db.execute(text("SELECT 1"))
        db_healthy = True
    except (ConnectionError, TimeoutError, OSError) as exc:
        logger.warning(f"DB health check failed: {exc}")

    # Honest metrics: only queue depth and DB/Redis service health are actually
    # measured here. Pipeline success, API latency/error, per-platform success
    # and host resource usage are NOT instrumented yet — return null instead of
    # fabricated 100%/0.0 so the UI shows "not available", never fake green.
    return APIResponse(
        success=True,
        data={
            "instrumented": {
                "queue_depth": True,
                "service_health": True,
                "pipeline": False,
                "api": False,
                "platforms": False,
                "resources": False,
            },
            "pipeline": {
                "success_rate_24h": None,
                "success_rate_7d": None,
                "jobs_total_24h": None,
                "jobs_failed_24h": None,
            },
            "api": {
                "requests_24h": None,
                "error_rate": None,
                "latency_p50_ms": None,
                "latency_p99_ms": None,
            },
            "queue": {
                "depth": queue_depth,
                "latency_ms": None,
            },
            "platforms": {
                "meta": {"status": "unknown", "success_rate": None},
                "google": {"status": "unknown", "success_rate": None},
                "tiktok": {"status": "unknown", "success_rate": None},
                "snap": {"status": "unknown", "success_rate": None},
            },
            "resources": {
                "cpu_percent": None,
                "memory_percent": None,
                "disk_percent": None,
            },
            "services": {
                "database": "healthy" if db_healthy else "unhealthy",
                "redis": "healthy" if redis_healthy else "unhealthy",
            },
        },
    )


# =============================================================================
# Audit Log Endpoints
# =============================================================================
@router.get("/audit", response_model=APIResponse)
async def get_audit_logs(
    request: Request,
    db: AsyncSession = Depends(get_async_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    action: Optional[str] = Query(None),
    user_id: Optional[int] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
):
    """
    Get audit logs with filtering.
    Owner only.
    """
    require_owner(request)

    try:
        # Build query for audit_logs table
        query = """
            SELECT id, timestamp, user_id, user_email, action,
                   resource_type, resource_id, details, ip_address, success, error_message
            FROM audit_logs
            WHERE 1=1
        """
        params = {}

        if action:
            query += " AND action ILIKE :action"
            params["action"] = f"%{action}%"
        if user_id:
            query += " AND user_id = :user_id"
            params["user_id"] = user_id
        if start_date:
            query += " AND timestamp >= :start_date"
            params["start_date"] = start_date
        if end_date:
            query += " AND timestamp <= :end_date"
            params["end_date"] = end_date

        query += " ORDER BY timestamp DESC LIMIT :limit OFFSET :skip"
        params["limit"] = limit
        params["skip"] = skip

        from sqlalchemy import text

        result = await db.execute(text(query), params)
        rows = result.fetchall()

        logs = []
        for row in rows:
            logs.append(
                {
                    "id": row[0],
                    "timestamp": row[1].isoformat() if row[1] else None,
                    "user_id": row[2],
                    "user_email": row[3],
                    "action": row[4],
                    "resource_type": row[5],
                    "resource_id": row[6],
                    "details": row[7],
                    "ip_address": row[8],
                    "success": row[9],
                    "error_message": row[10],
                }
            )

        # Get total count
        count_result = await db.execute(text("SELECT COUNT(*) FROM audit_logs"))
        total = count_result.scalar() or 0

        return APIResponse(
            success=True,
            data={
                "logs": logs,
                "total": total,
                "skip": skip,
                "limit": limit,
            },
        )
    except (SQLAlchemyError, ValueError) as e:
        logger.warning("audit_logs_query_failed", error=str(e))
        return APIResponse(
            success=True,
            data={
                "logs": [],
                "total": 0,
                "message": "Audit logs table not yet migrated",
            },
        )


async def create_audit_log(
    db: AsyncSession,
    action: str,
    user_id: Optional[int] = None,
    user_email: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    details: Optional[dict] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    success: bool = True,
    error_message: Optional[str] = None,
):
    """
    Create an audit log entry.
    Used by other endpoints to track admin actions.
    """
    try:
        import json

        from sqlalchemy import text

        query = text("""
            INSERT INTO audit_logs
            (timestamp, user_id, user_email, action, resource_type,
             resource_id, details, ip_address, user_agent, success, error_message)
            VALUES
            (NOW(), :user_id, :user_email, :action, :resource_type,
             :resource_id, :details, :ip_address, :user_agent, :success, :error_message)
        """)

        await db.execute(
            query,
            {
                "user_id": user_id,
                "user_email": user_email,
                "action": action,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "details": json.dumps(details) if details else None,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "success": success,
                "error_message": error_message,
            },
        )
        await db.commit()
    except (SQLAlchemyError, ValueError) as e:
        logger.warning("create_audit_log_failed", error=str(e))



# =============================================================================
# Dashboard Summary
# =============================================================================
@router.get("/dashboard", response_model=APIResponse)
async def get_owner_dashboard(
    request: Request,
    db: AsyncSession = Depends(get_async_session),
):
    """
    Get Owner dashboard summary.
    Combines usage, health, and alerts.

    NOTE(STRAT-SC-001/C3): the revenue/tenant-count/churn-risk sections were
    removed — their sole data source was the deleted ``Tenant`` model
    (single-org deployment has no MRR, tenant portfolio, or churn concept).
    """
    require_owner(request)

    # Get user count
    user_result = await db.execute(
        select(func.count(User.id)).where(User.is_deleted == False)
    )
    total_users = user_result.scalar() or 0

    # Get campaign count
    campaign_result = await db.execute(
        select(func.count(Campaign.id)).where(Campaign.is_deleted == False)
    )
    total_campaigns = campaign_result.scalar() or 0

    return APIResponse(
        success=True,
        data={
            "usage": {
                "total_users": total_users,
                "total_campaigns": total_campaigns,
            },
            "health": await _get_system_health(db),
            "alerts": await _get_alert_counts(db),
        },
    )


# =============================================================================
# System Health Helpers
# =============================================================================


async def _get_system_health(db: AsyncSession) -> dict:
    """Gather system health metrics from database and connections."""
    health = {
        "platform_status": "operational",
        "pipeline_success_rate": None,
        "api_uptime": None,
    }

    try:
        # Check platform connection health
        from app.models.campaign_builder import PlatformConnection

        result = await db.execute(
            select(PlatformConnection).where(
                PlatformConnection.is_connected == True
            )
        )
        connections = result.scalars().all()

        total_connections = len(connections)
        healthy_connections = sum(
            1 for c in connections if getattr(c, "is_healthy", True)
        )

        if total_connections > 0:
            health_rate = healthy_connections / total_connections
            if health_rate >= 0.9:
                health["platform_status"] = "operational"
            elif health_rate >= 0.7:
                health["platform_status"] = "degraded"
            else:
                health["platform_status"] = "critical"

            health["pipeline_success_rate"] = round(health_rate * 100, 1)
        else:
            health["platform_status"] = "no_connections"
            health["pipeline_success_rate"] = None

        # api_uptime is not instrumented (no real uptime tracker) — leave null
        # rather than reporting a fabricated 99.9.
        health["api_uptime"] = None
    except Exception as e:
        logger.warning("system_health_check_failed", error=str(e))
        health["platform_status"] = "unknown"

    return health


async def _get_alert_counts(db: AsyncSession) -> dict:
    """Get alert counts by severity from enforcement audit logs."""
    counts = {"critical": 0, "high": 0, "medium": 0}

    try:
        from sqlalchemy import text

        result = await db.execute(text("""
                SELECT
                    COALESCE(details->>'severity', 'medium') as severity,
                    COUNT(*) as cnt
                FROM enforcement_audit_logs
                WHERE timestamp > NOW() - INTERVAL '24 hours'
                GROUP BY COALESCE(details->>'severity', 'medium')
            """))
        for row in result.fetchall():
            sev = row[0]
            if sev in counts:
                counts[sev] = row[1]
    except Exception as e:
        logger.warning("alert_counts_query_failed", error=str(e))

    return counts


# =============================================================================
# Seed Platform Connections from Env Vars
# =============================================================================
class SeedPlatformsRequest(BaseModel):
    """Request to bootstrap platform connections from env vars."""

    trigger_sync: bool = True


@router.post("/seed-platforms", response_model=APIResponse)
async def seed_platforms(
    body: SeedPlatformsRequest,
    request: Request,
    db: AsyncSession = Depends(get_async_session),
):
    """
    Bootstrap PlatformConnection and AdAccount records from
    environment-variable tokens.  Owner only.

    This replaces the normal OAuth callback flow for initial setup when
    tokens are already provisioned as Railway env vars.
    """
    user_id = require_owner(request)

    from app.base_models import AdPlatform
    from app.core.config import settings
    from app.core.security import encrypt_pii
    from app.models.campaign_builder import (
        ConnectionStatus,
        AdAccount,
        PlatformConnection,
    )

    # Platform config: (platform, access_token_setting, account_ids_fn, extra_fields)
    platform_configs = [
        {
            "platform": "meta",
            "access_token": settings.meta_access_token,
            "account_ids_fn": lambda: _parse_meta_account_ids(
                settings.meta_ad_account_ids
            ),
            "extra": {
                "meta_app_id": settings.meta_app_id,
                "meta_app_secret": settings.meta_app_secret,
            },
        },
        {
            "platform": "google",
            "access_token": settings.google_ads_refresh_token,
            "account_ids_fn": lambda: _parse_google_account_ids(
                settings.google_ads_customer_id
            ),
            "extra": {
                "google_ads_developer_token": settings.google_ads_developer_token,
                "google_ads_client_id": settings.google_ads_client_id,
                "google_ads_client_secret": settings.google_ads_client_secret,
            },
        },
        {
            "platform": "tiktok",
            "access_token": settings.tiktok_access_token,
            "account_ids_fn": lambda: (
                [settings.tiktok_advertiser_id] if settings.tiktok_advertiser_id else []
            ),
            "extra": {
                "tiktok_app_id": settings.tiktok_app_id,
                "tiktok_secret": settings.tiktok_secret,
            },
        },
        {
            "platform": "snapchat",
            "access_token": settings.snapchat_access_token,
            "account_ids_fn": lambda: (
                [settings.snapchat_ad_account_id]
                if settings.snapchat_ad_account_id
                else []
            ),
            "extra": {
                "snapchat_client_id": settings.snapchat_client_id,
                "snapchat_client_secret": settings.snapchat_client_secret,
            },
        },
    ]

    connections_created = []
    accounts_created = []
    sync_results = []
    now = datetime.now(timezone.utc)

    for cfg in platform_configs:
        token = cfg["access_token"]
        if not token:
            continue

        platform_name = cfg["platform"]

        # --- Upsert PlatformConnection ---
        conn_result = await db.execute(
            select(PlatformConnection).where(
                PlatformConnection.platform == platform_name,
            )
        )
        conn = conn_result.scalar_one_or_none()

        if conn:
            conn.access_token_encrypted = encrypt_pii(token)
            conn.status = ConnectionStatus.CONNECTED.value
            conn.connected_at = now
            conn.updated_at = now
            conn.last_error = None
            conn.error_count = 0
        else:
            conn = PlatformConnection(
                id=uuid4(),
                platform=platform_name,
                status=ConnectionStatus.CONNECTED.value,
                access_token_encrypted=encrypt_pii(token),
                connected_at=now,
                granted_by_user_id=user_id,
                scopes=[],
            )
            db.add(conn)

        # Store refresh token for Google (uses refresh_token flow)
        if platform_name == "google" and settings.google_ads_refresh_token:
            conn.refresh_token_encrypted = encrypt_pii(
                settings.google_ads_refresh_token
            )

        # Flush to get conn.id for ad accounts
        await db.flush()
        connections_created.append(platform_name)

        # --- Create AdAccount records ---
        account_ids = cfg["account_ids_fn"]()
        for acct_id in account_ids:
            if not acct_id:
                continue
            acct_result = await db.execute(
                select(AdAccount).where(
                    AdAccount.platform == platform_name,
                    AdAccount.platform_account_id == acct_id,
                )
            )
            existing_acct = acct_result.scalar_one_or_none()

            if existing_acct:
                existing_acct.is_enabled = True
                existing_acct.connection_id = conn.id
                existing_acct.updated_at = now
            else:
                new_acct = AdAccount(
                    id=uuid4(),
                    connection_id=conn.id,
                    platform=platform_name,
                    platform_account_id=acct_id,
                    name=f"{platform_name.title()} - {acct_id}",
                    is_enabled=True,
                    currency="USD",
                    timezone="UTC",
                )
                db.add(new_acct)

            accounts_created.append({"platform": platform_name, "account_id": acct_id})

    await db.commit()

    # --- Trigger sync (optional) ---
    if body.trigger_sync and connections_created:
        from app.base_models import AdPlatform as AP
        from app.services.sync.orchestrator import PlatformSyncOrchestrator

        orchestrator = PlatformSyncOrchestrator(db)
        platform_map = {
            "meta": AP.META,
            "google": AP.GOOGLE,
            "tiktok": AP.TIKTOK,
            "snapchat": AP.SNAPCHAT,
        }
        for pname in connections_created:
            ap = platform_map.get(pname)
            if not ap:
                continue
            try:
                sr = await orchestrator.sync_platform(ap, days_back=30)
                sync_results.append(
                    {
                        "platform": pname,
                        "campaigns_synced": sr.campaigns_synced,
                        "metrics_upserted": sr.metrics_upserted,
                        "errors": sr.errors,
                        "duration_seconds": round(sr.duration_seconds, 2),
                    }
                )
            except (ConnectionError, TimeoutError, OSError, ValueError) as e:
                logger.error("seed_sync_failed", platform=pname, error=str(e))
                sync_results.append(
                    {
                        "platform": pname,
                        "campaigns_synced": 0,
                        "metrics_upserted": 0,
                        "errors": [str(e)],
                    }
                )

    # Audit log
    await create_audit_log(
        db,
        action="seed_platforms",
        user_id=user_id,
        resource_type="platform_connections",
        details={
            "connections": connections_created,
            "accounts": accounts_created,
        },
    )

    return APIResponse(
        success=True,
        data={
            "connections_created": connections_created,
            "accounts_created": accounts_created,
            "sync_results": sync_results,
        },
        message=f"Seeded {len(connections_created)} platform(s) with {len(accounts_created)} ad account(s)",
    )


def _parse_meta_account_ids(raw: Optional[str]) -> list[str]:
    """Parse comma-separated Meta ad account IDs, adding act_ prefix if missing."""
    if not raw:
        return []
    ids = []
    for part in raw.split(","):
        aid = part.strip()
        if not aid:
            continue
        if not aid.startswith("act_"):
            aid = f"act_{aid}"
        ids.append(aid)
    return ids


def _parse_google_account_ids(raw: Optional[str]) -> list[str]:
    """Parse Google Ads customer ID, stripping hyphens."""
    if not raw:
        return []
    return [raw.replace("-", "").strip()]


# =============================================================================
# Seed Demo Data
# =============================================================================
@router.post("/seed-demo-data", response_model=APIResponse)
async def seed_demo_data(
    request: Request,
    db: AsyncSession = Depends(get_async_session),
):
    """
    Seed realistic demo campaign data for the organization.
    Creates 14 campaigns across 5 platforms with 90 days of daily metrics.
    Owner only.
    """
    require_owner(request)

    from sqlalchemy import text

    # Each SQL statement must be executed separately (asyncpg limitation)
    sql_steps = [
        # Step 1: Clean existing demo data
        text("DELETE FROM fact_platform_daily"),
        text("DELETE FROM campaign_metrics"),
        text("DELETE FROM campaigns"),
        # Step 2: Insert campaigns
        text(
            """INSERT INTO campaigns (platform, external_id, account_id, name, status, objective, daily_budget_cents, total_spend_cents, impressions, clicks, conversions, revenue_cents, ctr, roas, start_date, currency, labels, created_at, updated_at)
VALUES
('meta',   'camp_meta_001',  'act_100001', 'Summer Sale - Lookalike Audiences',  'active', 'conversions', 15000, 1350000, 2800000, 56000, 1680, 5400000, 2.0, 4.0, CURRENT_DATE - 90, 'USD', '["high-performer","retargeting"]', NOW(), NOW()),
('google', 'camp_goog_001',  'act_200001', 'Brand Search - Exact Match',         'active', 'conversions', 12000, 1080000, 1500000, 105000, 3150, 4320000, 7.0, 4.0, CURRENT_DATE - 90, 'USD', '["brand","search"]', NOW(), NOW()),
('meta',   'camp_meta_002',  'act_100001', 'Retargeting - Cart Abandoners',      'active', 'conversions', 8000, 720000, 1200000, 36000, 1440, 2880000, 3.0, 4.0, CURRENT_DATE - 90, 'USD', '["retargeting"]', NOW(), NOW()),
('google', 'camp_goog_002',  'act_200001', 'Shopping - Product Listing Ads',     'active', 'sales',       20000, 1800000, 3500000, 52500, 1050, 3960000, 1.5, 2.2, CURRENT_DATE - 90, 'USD', '["shopping"]', NOW(), NOW()),
('tiktok', 'camp_tik_001',   'act_300001', 'UGC Creative - Gen Z Audience',      'active', 'conversions', 10000, 900000, 4500000, 67500, 900, 1800000, 1.5, 2.0, CURRENT_DATE - 90, 'USD', '["ugc","genZ"]', NOW(), NOW()),
('meta',   'camp_meta_003',  'act_100001', 'Video Views - Product Demo',         'active', 'video_views', 6000, 540000, 3200000, 32000, 480, 1080000, 1.0, 2.0, CURRENT_DATE - 90, 'USD', '["video","awareness"]', NOW(), NOW()),
('snapchat','camp_snap_001', 'act_400001', 'Story Ads - Flash Sale',             'active', 'conversions', 7000, 630000, 2100000, 42000, 630, 1260000, 2.0, 2.0, CURRENT_DATE - 90, 'USD', '["stories"]', NOW(), NOW()),
('linkedin','camp_li_001',   'act_500001', 'Lead Gen - Decision Makers',         'active', 'leads',       15000, 1350000, 800000, 8000, 400, 2700000, 1.0, 2.0, CURRENT_DATE - 90, 'USD', '["b2b","leads"]', NOW(), NOW()),
('google', 'camp_goog_003',  'act_200001', 'Display - Remarketing',              'active', 'conversions', 5000, 450000, 5000000, 25000, 375, 900000, 0.5, 2.0, CURRENT_DATE - 90, 'USD', '["display","remarketing"]', NOW(), NOW()),
('tiktok', 'camp_tik_002',   'act_300001', 'Spark Ads - Influencer Collab',      'active', 'engagement',  8000, 720000, 3800000, 57000, 570, 1440000, 1.5, 2.0, CURRENT_DATE - 90, 'USD', '["influencer"]', NOW(), NOW()),
('meta',   'camp_meta_004',  'act_100001', 'Cold Audience - Interest Targeting', 'active', 'conversions', 12000, 1080000, 2000000, 20000, 200, 540000, 1.0, 0.5, CURRENT_DATE - 90, 'USD', '["prospecting"]', NOW(), NOW()),
('snapchat','camp_snap_002', 'act_400001', 'AR Lens - Brand Awareness',          'paused', 'awareness',   9000, 810000, 1800000, 9000, 90, 324000, 0.5, 0.4, CURRENT_DATE - 90, 'USD', '["ar","awareness"]', NOW(), NOW()),
('google', 'camp_goog_004',  'act_200001', 'Broad Match - New Markets',          'active', 'conversions', 10000, 900000, 1800000, 18000, 180, 720000, 1.0, 0.8, CURRENT_DATE - 90, 'USD', '["expansion"]', NOW(), NOW()),
('tiktok', 'camp_tik_003',   'act_300001', 'Hashtag Challenge - Brand Launch',   'paused', 'awareness',   15000, 1350000, 6000000, 60000, 300, 675000, 1.0, 0.5, CURRENT_DATE - 90, 'USD', '["hashtag","brand"]', NOW(), NOW())"""
        ),
        # Step 3: Generate daily metrics
        text(
            """INSERT INTO campaign_metrics (campaign_id, date, impressions, clicks, conversions, spend_cents, revenue_cents)
SELECT c.id, d.date,
  GREATEST(100, (c.impressions / 90.0 * (0.7 + random() * 0.6))::INT),
  GREATEST(10, (c.clicks / 90.0 * (0.7 + random() * 0.6))::INT),
  GREATEST(0, (c.conversions / 90.0 * (0.6 + random() * 0.8))::INT),
  GREATEST(100, (c.total_spend_cents / 90.0 * (0.75 + random() * 0.5))::INT),
  GREATEST(0, (c.revenue_cents / 90.0 * (0.65 + random() * 0.7))::INT)
FROM campaigns c
CROSS JOIN generate_series(CURRENT_DATE - 89, CURRENT_DATE, '1 day'::interval) AS d(date)"""
        ),
        # Step 4: Populate analytics warehouse
        text(
            """INSERT INTO fact_platform_daily (date, platform, account_id, campaign_id, spend, impressions, clicks, conversions, revenue, ctr, cvr, cpm, cpc, cpa, roas, ingestion_time)
SELECT cm.date, c.platform::TEXT, c.account_id, c.external_id,
  cm.spend_cents / 100.0, cm.impressions, cm.clicks, cm.conversions, cm.revenue_cents / 100.0,
  CASE WHEN cm.impressions > 0 THEN ROUND((cm.clicks::NUMERIC / cm.impressions * 100)::NUMERIC, 2) ELSE 0 END,
  CASE WHEN cm.clicks > 0 THEN ROUND((cm.conversions::NUMERIC / cm.clicks * 100)::NUMERIC, 2) ELSE 0 END,
  CASE WHEN cm.impressions > 0 THEN ROUND((cm.spend_cents / 100.0 / cm.impressions * 1000)::NUMERIC, 2) ELSE 0 END,
  CASE WHEN cm.clicks > 0 THEN ROUND((cm.spend_cents / 100.0 / cm.clicks)::NUMERIC, 2) ELSE 0 END,
  CASE WHEN cm.conversions > 0 THEN ROUND((cm.spend_cents / 100.0 / cm.conversions)::NUMERIC, 2) ELSE 0 END,
  CASE WHEN cm.spend_cents > 0 THEN ROUND((cm.revenue_cents::NUMERIC / cm.spend_cents)::NUMERIC, 2) ELSE 0 END,
  NOW()
FROM campaign_metrics cm
JOIN campaigns c ON c.id = cm.campaign_id"""
        ),
        # Step 5: Update campaign aggregates
        text("""UPDATE campaigns SET
  total_spend_cents = sub.total_spend,
  impressions = sub.total_impressions,
  clicks = sub.total_clicks,
  conversions = sub.total_conversions,
  revenue_cents = sub.total_revenue,
  ctr = CASE WHEN sub.total_impressions > 0 THEN ROUND((sub.total_clicks::NUMERIC / sub.total_impressions * 100)::NUMERIC, 2) ELSE 0 END,
  roas = CASE WHEN sub.total_spend > 0 THEN ROUND((sub.total_revenue::NUMERIC / sub.total_spend)::NUMERIC, 2) ELSE 0 END,
  last_synced_at = NOW(), updated_at = NOW()
FROM (
  SELECT campaign_id, SUM(spend_cents) AS total_spend, SUM(impressions) AS total_impressions,
         SUM(clicks) AS total_clicks, SUM(conversions) AS total_conversions, SUM(revenue_cents) AS total_revenue
  FROM campaign_metrics GROUP BY campaign_id
) sub
WHERE campaigns.id = sub.campaign_id"""),
    ]

    try:
        for step in sql_steps:
            await db.execute(step)
        await db.commit()
    except (SQLAlchemyError, ValueError) as e:
        await db.rollback()
        logger.error("seed_demo_data_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Seed failed: {str(e)}")

    # Count results
    camp_count = (await db.execute(text("SELECT COUNT(*) FROM campaigns"))).scalar()
    metric_count = (
        await db.execute(text("SELECT COUNT(*) FROM campaign_metrics"))
    ).scalar()
    fact_count = (
        await db.execute(text("SELECT COUNT(*) FROM fact_platform_daily"))
    ).scalar()

    logger.info(
        "seed_demo_data_complete",
        campaigns=camp_count,
        metrics=metric_count,
        facts=fact_count,
    )

    return APIResponse(
        success=True,
        data={
            "campaigns_created": camp_count,
            "daily_metrics_rows": metric_count,
            "fact_rows": fact_count,
        },
        message=f"Seeded {camp_count} campaigns with {metric_count} daily metric rows",
    )


# =============================================================================
# Credential Health Check
# =============================================================================
# Returns presence-only flags for every secret the platform reads from
# Settings — no actual values, just `set: bool`. Lets the owner verify
# at a glance which Railway env vars are configured without having to
# read the dashboard. Powers /console/credentials in the frontend.


@router.get("/credentials/health", response_model=APIResponse)
async def credentials_health(request: Request):
    """Presence-only health check across every external-credential setting."""
    require_owner(request)

    def present(value: object) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        return bool(value)

    sections = {
        "ad_platforms": {
            "meta": {
                "app_id": present(settings.meta_app_id),
                "app_secret": present(settings.meta_app_secret),
                "api_version": settings.meta_api_version or None,
                "long_lived_token": present(settings.meta_access_token),
            },
            "google_ads": {
                "developer_token": present(settings.google_ads_developer_token),
                "client_id": present(settings.google_ads_client_id),
                "client_secret": present(settings.google_ads_client_secret),
                "refresh_token": present(settings.google_ads_refresh_token),
                "customer_id_default": present(settings.google_ads_customer_id),
            },
            "tiktok": {
                "app_id": present(settings.tiktok_app_id),
                "secret": present(settings.tiktok_secret),
                "long_lived_token": present(settings.tiktok_access_token),
                "advertiser_id_default": present(settings.tiktok_advertiser_id),
            },
            "snapchat": {
                "client_id": present(settings.snapchat_client_id),
                "client_secret": present(settings.snapchat_client_secret),
                "long_lived_token": present(settings.snapchat_access_token),
                "ad_account_id_default": present(settings.snapchat_ad_account_id),
            },
        },
        "email": {
            "smtp": {
                "host": present(settings.smtp_host),
                "user": present(settings.smtp_user),
                "password": present(settings.smtp_password),
            },
            "sendgrid": {
                "api_key": present(settings.sendgrid_api_key),
                "webhook_token": present(settings.sendgrid_webhook_token),
            },
        },
        "ai": {
            "anthropic": {
                "api_key": present(settings.anthropic_api_key),
                "llm_enabled": settings.copilot_llm_enabled,
                "model": settings.copilot_llm_model,
            },
        },
        "infra": {
            "oauth_redirect_base_url": settings.oauth_redirect_base_url,
            "frontend_url": settings.frontend_url,
            "sentry_dsn_set": present(settings.sentry_dsn),
            "pii_encryption_key_set": present(settings.pii_encryption_key),
        },
    }

    return APIResponse(
        success=True,
        data=sections,
        message="Credential presence check",
    )


# =============================================================================
# Anomalies Rollup
# =============================================================================
@router.get("/anomalies-rollup", response_model=APIResponse)
async def get_anomalies_rollup(
    request: Request,
    severity: Optional[str] = Query(
        default=None,
        description="Filter by severity: critical, high, medium, low",
    ),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Get the organization's anomaly rollup for the owner console.

    NOTE(STRAT-SC-001/C3): this used to fan out one anomaly-detection call
    per tenant across the whole platform (client-side, then server-side).
    Single-org deployment has exactly one organization, so this is now a
    single call.
    """
    require_owner(request)

    from app.api.v1.endpoints.insights import detect_campaign_anomalies

    target_date = date.today()

    try:
        anomalies = await detect_campaign_anomalies(db, target_date)
    except SQLAlchemyError as exc:
        logger.warning("anomalies_rollup_failed", error=str(exc))
        anomalies = []

    if severity:
        anomalies = [a for a in anomalies if a.get("severity") == severity]

    anomalies = anomalies[:limit]
    anomalies.sort(key=lambda a: a.get("detected_at", ""), reverse=True)

    by_severity = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for a in anomalies:
        sev = a.get("severity")
        if sev in by_severity:
            by_severity[sev] += 1

    return APIResponse(
        success=True,
        data={
            "date": target_date.isoformat(),
            "anomalies": anomalies,
            "total": len(anomalies),
            "by_severity": by_severity,
        },
    )
