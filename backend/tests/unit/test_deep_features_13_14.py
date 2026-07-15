# =============================================================================
# Stratum AI - Deep Endpoint Tests: Features 13 & 14
# =============================================================================
"""
Deep endpoint tests for:
  Feature 13 -- Automated Reporting (templates, schedules, executions)
  Feature 14 -- Owner console dashboard & Owner console Analytics

Each test exercises the FULL request/response cycle via httpx.AsyncClient,
passing through AuthContextMiddleware (real JWT decode) while
mocking services / DB at the endpoint-handler level.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from tests.unit.conftest import (
    make_auth_headers,
    make_scalar_result,
    make_scalars_result,
)

pytestmark = pytest.mark.asyncio

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_NOW = datetime.now(timezone.utc)
_UUID1 = uuid.uuid4()
_UUID2 = uuid.uuid4()
_UUID3 = uuid.uuid4()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_user(*, user_id: int = 1, role: str = "admin") -> MagicMock:
    u = MagicMock()
    u.id = user_id
    u.role = role
    u.email = "test@example.com"
    u.is_deleted = False
    return u


def _fake_template(
    *,
    template_id: uuid.UUID | None = None,
    name: str = "Monthly Perf",
    is_system: bool = False,
    is_active: bool = True,
) -> MagicMock:
    tpl = MagicMock()
    tpl.id = template_id or _UUID1
    tpl.name = name
    tpl.description = "Test template"
    tpl.report_type = "campaign_performance"
    tpl.config = {}
    tpl.default_format = "pdf"
    tpl.available_formats = ["pdf", "csv"]
    tpl.is_active = is_active
    tpl.is_system = is_system
    tpl.created_at = _NOW
    tpl.updated_at = _NOW
    tpl.__dict__.update(
        {
            "id": tpl.id,
            "name": tpl.name,
            "description": tpl.description,
            "report_type": tpl.report_type,
            "config": tpl.config,
            "default_format": tpl.default_format,
            "available_formats": tpl.available_formats,
            "is_active": tpl.is_active,
            "is_system": tpl.is_system,
            "created_at": tpl.created_at,
            "updated_at": tpl.updated_at,
        }
    )
    return tpl


def _fake_schedule(
    *,
    schedule_id: uuid.UUID | None = None,
    template_id: uuid.UUID | None = None,
) -> MagicMock:
    s = MagicMock()
    s.id = schedule_id or _UUID2
    s.template_id = template_id or _UUID1
    s.name = "Weekly report"
    s.description = None
    s.frequency = "weekly"
    s.timezone = "UTC"
    s.day_of_week = 1
    s.day_of_month = None
    s.hour = 8
    s.minute = 0
    s.cron_expression = None
    s.format_override = None
    s.date_range_type = "last_7_days"
    s.delivery_channels = ["email"]
    s.is_active = True
    s.is_paused = False
    s.last_run_at = None
    s.last_run_status = None
    s.next_run_at = None
    s.run_count = 0
    s.failure_count = 0
    s.created_at = _NOW
    s.__dict__.update(
        {
            "id": s.id,
            "template_id": s.template_id,
            "name": s.name,
            "description": s.description,
            "frequency": s.frequency,
            "timezone": s.timezone,
            "day_of_week": s.day_of_week,
            "day_of_month": s.day_of_month,
            "hour": s.hour,
            "minute": s.minute,
            "cron_expression": s.cron_expression,
            "format_override": s.format_override,
            "date_range_type": s.date_range_type,
            "delivery_channels": s.delivery_channels,
            "is_active": s.is_active,
            "is_paused": s.is_paused,
            "last_run_at": s.last_run_at,
            "last_run_status": s.last_run_status,
            "next_run_at": s.next_run_at,
            "run_count": s.run_count,
            "failure_count": s.failure_count,
            "created_at": s.created_at,
        }
    )
    return s


def _fake_execution(
    *,
    execution_id: uuid.UUID | None = None,
    status: str = "completed",
) -> MagicMock:
    e = MagicMock()
    e.id = execution_id or _UUID3
    e.template_id = _UUID1
    e.schedule_id = _UUID2
    e.execution_type = "manual"
    e.status = status
    e.started_at = _NOW
    e.completed_at = _NOW
    e.duration_seconds = 3.5
    e.report_type = "campaign_performance"
    e.format = "pdf"
    e.date_range_start = date(2026, 1, 1)
    e.date_range_end = date(2026, 1, 31)
    e.file_url = "https://s3.example.com/report.pdf"
    e.file_size_bytes = 102400
    e.row_count = 50
    e.metrics_summary = {"total_spend": 5000}
    e.error_message = None
    e.__dict__.update(
        {
            "id": e.id,
            "template_id": e.template_id,
            "schedule_id": e.schedule_id,
            "execution_type": e.execution_type,
            "status": e.status,
            "started_at": e.started_at,
            "completed_at": e.completed_at,
            "duration_seconds": e.duration_seconds,
            "report_type": e.report_type,
            "format": e.format,
            "date_range_start": e.date_range_start,
            "date_range_end": e.date_range_end,
            "file_url": e.file_url,
            "file_size_bytes": e.file_size_bytes,
            "row_count": e.row_count,
            "metrics_summary": e.metrics_summary,
            "error_message": e.error_message,
        }
    )
    return e


# ---------------------------------------------------------------------------
# Fixtures: reporting endpoints resolve the user via app.auth.deps
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def reporting_client(test_app, mock_db):
    """
    httpx.AsyncClient with overrides for the app.db.session AND
    app.auth.deps dependency functions used by reporting endpoints.
    """
    from app.auth.deps import get_current_user
    from app.db.session import get_async_session
    from app.db.session import get_db as db_session_get_db

    fake_user = _fake_user()

    async def override_session():
        yield mock_db

    async def override_current_user():
        return fake_user

    test_app.dependency_overrides[get_async_session] = override_session
    test_app.dependency_overrides[db_session_get_db] = override_session
    test_app.dependency_overrides[get_current_user] = override_current_user

    async with AsyncClient(
        transport=ASGITransport(app=test_app),
        base_url="http://testserver",
    ) as ac:
        yield ac

    test_app.dependency_overrides.clear()


# ============================================================================
# FEATURE 13 -- REPORTING
# ============================================================================


class TestReportingTemplatesNoAuth:
    """Reporting endpoints must reject unauthenticated requests."""

    async def test_list_templates_no_auth(self, api_client):
        r = await api_client.get("/api/v1/reporting/templates")
        assert r.status_code == 401

    async def test_create_template_no_auth(self, api_client):
        r = await api_client.post(
            "/api/v1/reporting/templates",
            json={
                "name": "X",
                "report_type": "campaign_performance",
            },
        )
        assert r.status_code == 401

    async def test_get_template_no_auth(self, api_client):
        r = await api_client.get(f"/api/v1/reporting/templates/{_UUID1}")
        assert r.status_code == 401

    async def test_patch_template_no_auth(self, api_client):
        r = await api_client.patch(
            f"/api/v1/reporting/templates/{_UUID1}",
            json={"name": "X"},
        )
        assert r.status_code == 401

    async def test_delete_template_no_auth(self, api_client):
        r = await api_client.delete(f"/api/v1/reporting/templates/{_UUID1}")
        assert r.status_code == 401


class TestReportingTemplatesCRUD:
    """CRUD operations on report templates (authenticated)."""

    async def test_create_template_happy(
        self,
        reporting_client,
        mock_db,
        admin_headers,
    ):
        tpl = _fake_template()

        def _populate(obj):
            # The endpoint adds + commits but never refreshes; a real DB would
            # populate id / timestamps / column defaults on flush. Mirror that
            # on add() so the response model validates.
            for attr in (
                "id",
                "name",
                "description",
                "report_type",
                "config",
                "default_format",
                "available_formats",
                "is_active",
                "is_system",
                "created_at",
                "updated_at",
            ):
                setattr(obj, attr, getattr(tpl, attr))

        mock_db.add = MagicMock(side_effect=_populate)

        r = await reporting_client.post(
            "/api/v1/reporting/templates",
            json={
                "name": "Monthly Perf",
                "report_type": "campaign_performance",
                "config": {},
                "default_format": "pdf",
            },
            headers=admin_headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["name"] == "Monthly Perf"
        assert body["is_active"] is True

    async def test_list_templates_happy(
        self,
        reporting_client,
        mock_db,
        admin_headers,
    ):
        tpl = _fake_template()
        mock_db.execute = AsyncMock(return_value=make_scalars_result([tpl]))

        r = await reporting_client.get(
            "/api/v1/reporting/templates",
            headers=admin_headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body, list)
        assert len(body) == 1
        assert body[0]["name"] == "Monthly Perf"

    async def test_list_templates_empty(
        self,
        reporting_client,
        mock_db,
        admin_headers,
    ):
        mock_db.execute = AsyncMock(return_value=make_scalars_result([]))
        r = await reporting_client.get(
            "/api/v1/reporting/templates",
            headers=admin_headers,
        )
        assert r.status_code == 200
        assert r.json() == []

    async def test_list_templates_with_report_type_filter(
        self,
        reporting_client,
        mock_db,
        admin_headers,
    ):
        mock_db.execute = AsyncMock(return_value=make_scalars_result([]))
        r = await reporting_client.get(
            "/api/v1/reporting/templates?report_type=pacing_status",
            headers=admin_headers,
        )
        assert r.status_code == 200

    async def test_get_template_happy(
        self,
        reporting_client,
        mock_db,
        admin_headers,
    ):
        tpl = _fake_template()
        mock_db.get = AsyncMock(return_value=tpl)

        r = await reporting_client.get(
            f"/api/v1/reporting/templates/{_UUID1}",
            headers=admin_headers,
        )
        assert r.status_code == 200
        assert r.json()["name"] == "Monthly Perf"

    async def test_get_template_not_found(
        self,
        reporting_client,
        mock_db,
        admin_headers,
    ):
        mock_db.get = AsyncMock(return_value=None)
        r = await reporting_client.get(
            f"/api/v1/reporting/templates/{uuid.uuid4()}",
            headers=admin_headers,
        )
        assert r.status_code == 404

    async def test_update_template_happy(
        self,
        reporting_client,
        mock_db,
        admin_headers,
    ):
        tpl = _fake_template()
        mock_db.get = AsyncMock(return_value=tpl)

        async def _refresh(obj, *a, **kw):
            obj.name = "Updated Name"

        mock_db.refresh = AsyncMock(side_effect=_refresh)

        r = await reporting_client.patch(
            f"/api/v1/reporting/templates/{_UUID1}",
            json={"name": "Updated Name"},
            headers=admin_headers,
        )
        assert r.status_code == 200
        assert r.json()["name"] == "Updated Name"

    async def test_update_system_template_blocked(
        self,
        reporting_client,
        mock_db,
        admin_headers,
    ):
        tpl = _fake_template(is_system=True)
        mock_db.get = AsyncMock(return_value=tpl)

        r = await reporting_client.patch(
            f"/api/v1/reporting/templates/{_UUID1}",
            json={"name": "Hacked"},
            headers=admin_headers,
        )
        assert r.status_code == 400
        assert "system" in r.json()["detail"].lower()

    async def test_update_template_not_found(
        self,
        reporting_client,
        mock_db,
        admin_headers,
    ):
        mock_db.get = AsyncMock(return_value=None)
        r = await reporting_client.patch(
            f"/api/v1/reporting/templates/{uuid.uuid4()}",
            json={"name": "X"},
            headers=admin_headers,
        )
        assert r.status_code == 404

    async def test_delete_template_happy(
        self,
        reporting_client,
        mock_db,
        admin_headers,
    ):
        tpl = _fake_template()
        mock_db.get = AsyncMock(return_value=tpl)

        r = await reporting_client.delete(
            f"/api/v1/reporting/templates/{_UUID1}",
            headers=admin_headers,
        )
        assert r.status_code == 200
        assert r.json()["status"] == "deleted"

    async def test_delete_system_template_blocked(
        self,
        reporting_client,
        mock_db,
        admin_headers,
    ):
        tpl = _fake_template(is_system=True)
        mock_db.get = AsyncMock(return_value=tpl)

        r = await reporting_client.delete(
            f"/api/v1/reporting/templates/{_UUID1}",
            headers=admin_headers,
        )
        assert r.status_code == 400


class TestReportingSchedules:
    """Scheduled report CRUD tests."""

    async def test_create_schedule_no_auth(self, api_client):
        r = await api_client.post(
            "/api/v1/reporting/schedules",
            json={
                "template_id": str(_UUID1),
                "name": "Weekly",
                "frequency": "weekly",
            },
        )
        assert r.status_code == 401

    @patch("app.api.v1.endpoints.reporting.ReportScheduler")
    async def test_create_schedule_happy(
        self,
        MockScheduler,
        reporting_client,
        mock_db,
        admin_headers,
    ):
        sched = _fake_schedule()
        instance = MockScheduler.return_value
        instance.create_schedule = AsyncMock(return_value=sched)

        r = await reporting_client.post(
            "/api/v1/reporting/schedules",
            json={
                "template_id": str(_UUID1),
                "name": "Weekly report",
                "frequency": "weekly",
                "day_of_week": 1,
                "hour": 8,
                "minute": 0,
            },
            headers=admin_headers,
        )
        assert r.status_code == 200
        assert r.json()["name"] == "Weekly report"

    @patch("app.api.v1.endpoints.reporting.ReportScheduler")
    async def test_create_schedule_invalid_template(
        self,
        MockScheduler,
        reporting_client,
        mock_db,
        admin_headers,
    ):
        instance = MockScheduler.return_value
        instance.create_schedule = AsyncMock(
            side_effect=ValueError("Template not found")
        )

        r = await reporting_client.post(
            "/api/v1/reporting/schedules",
            json={
                "template_id": str(uuid.uuid4()),
                "name": "Bad",
                "frequency": "daily",
            },
            headers=admin_headers,
        )
        assert r.status_code == 400

    @patch("app.api.v1.endpoints.reporting.ReportScheduler")
    async def test_list_schedules_happy(
        self,
        MockScheduler,
        reporting_client,
        mock_db,
        admin_headers,
    ):
        sched = _fake_schedule()
        instance = MockScheduler.return_value
        instance.list_schedules = AsyncMock(return_value=([sched], 1))

        r = await reporting_client.get(
            "/api/v1/reporting/schedules",
            headers=admin_headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body, list)
        assert len(body) == 1

    @patch("app.api.v1.endpoints.reporting.ReportScheduler")
    async def test_get_schedule_happy(
        self,
        MockScheduler,
        reporting_client,
        mock_db,
        admin_headers,
    ):
        sched = _fake_schedule()
        instance = MockScheduler.return_value
        instance.get_schedule = AsyncMock(return_value=sched)

        r = await reporting_client.get(
            f"/api/v1/reporting/schedules/{_UUID2}",
            headers=admin_headers,
        )
        assert r.status_code == 200
        assert r.json()["frequency"] == "weekly"

    @patch("app.api.v1.endpoints.reporting.ReportScheduler")
    async def test_get_schedule_not_found(
        self,
        MockScheduler,
        reporting_client,
        mock_db,
        admin_headers,
    ):
        instance = MockScheduler.return_value
        instance.get_schedule = AsyncMock(return_value=None)

        r = await reporting_client.get(
            f"/api/v1/reporting/schedules/{uuid.uuid4()}",
            headers=admin_headers,
        )
        assert r.status_code == 404

    @patch("app.api.v1.endpoints.reporting.ReportScheduler")
    async def test_update_schedule_happy(
        self,
        MockScheduler,
        reporting_client,
        mock_db,
        admin_headers,
    ):
        sched = _fake_schedule()
        sched.name = "Renamed"
        sched.__dict__["name"] = "Renamed"
        instance = MockScheduler.return_value
        instance.update_schedule = AsyncMock(return_value=sched)

        r = await reporting_client.patch(
            f"/api/v1/reporting/schedules/{_UUID2}",
            json={"name": "Renamed"},
            headers=admin_headers,
        )
        assert r.status_code == 200
        assert r.json()["name"] == "Renamed"

    @patch("app.api.v1.endpoints.reporting.ReportScheduler")
    async def test_update_schedule_not_found(
        self,
        MockScheduler,
        reporting_client,
        mock_db,
        admin_headers,
    ):
        instance = MockScheduler.return_value
        instance.update_schedule = AsyncMock(
            side_effect=ValueError("Schedule not found"),
        )

        r = await reporting_client.patch(
            f"/api/v1/reporting/schedules/{uuid.uuid4()}",
            json={"name": "X"},
            headers=admin_headers,
        )
        assert r.status_code == 404

    @patch("app.api.v1.endpoints.reporting.ReportScheduler")
    async def test_run_schedule_now_happy(
        self,
        MockScheduler,
        reporting_client,
        mock_db,
        admin_headers,
    ):
        exe = _fake_execution()
        instance = MockScheduler.return_value
        instance.run_now = AsyncMock(return_value=exe)

        r = await reporting_client.post(
            f"/api/v1/reporting/schedules/{_UUID2}/run-now",
            headers=admin_headers,
        )
        assert r.status_code == 200
        assert r.json()["status"] == "completed"

    @patch("app.api.v1.endpoints.reporting.ReportScheduler")
    async def test_run_schedule_now_not_found(
        self,
        MockScheduler,
        reporting_client,
        mock_db,
        admin_headers,
    ):
        instance = MockScheduler.return_value
        instance.run_now = AsyncMock(side_effect=ValueError("Schedule not found"))

        r = await reporting_client.post(
            f"/api/v1/reporting/schedules/{uuid.uuid4()}/run-now",
            headers=admin_headers,
        )
        assert r.status_code == 404

    @patch("app.api.v1.endpoints.reporting.ReportScheduler")
    async def test_delete_schedule_happy(
        self,
        MockScheduler,
        reporting_client,
        mock_db,
        admin_headers,
    ):
        instance = MockScheduler.return_value
        instance.delete_schedule = AsyncMock(return_value=True)

        r = await reporting_client.delete(
            f"/api/v1/reporting/schedules/{_UUID2}",
            headers=admin_headers,
        )
        assert r.status_code == 200
        assert r.json()["status"] == "deleted"

    @patch("app.api.v1.endpoints.reporting.ReportScheduler")
    async def test_delete_schedule_not_found(
        self,
        MockScheduler,
        reporting_client,
        mock_db,
        admin_headers,
    ):
        instance = MockScheduler.return_value
        instance.delete_schedule = AsyncMock(return_value=False)

        r = await reporting_client.delete(
            f"/api/v1/reporting/schedules/{uuid.uuid4()}",
            headers=admin_headers,
        )
        assert r.status_code == 404


class TestReportingExecutions:
    """Execution history and detail tests."""

    async def test_list_executions_no_auth(self, api_client):
        r = await api_client.get("/api/v1/reporting/executions")
        assert r.status_code == 401

    async def test_list_executions_happy(
        self,
        reporting_client,
        mock_db,
        admin_headers,
    ):
        exe = _fake_execution()
        mock_db.execute = AsyncMock(return_value=make_scalars_result([exe]))

        r = await reporting_client.get(
            "/api/v1/reporting/executions",
            headers=admin_headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body, list)
        assert len(body) == 1

    async def test_list_executions_empty(
        self,
        reporting_client,
        mock_db,
        admin_headers,
    ):
        mock_db.execute = AsyncMock(return_value=make_scalars_result([]))
        r = await reporting_client.get(
            "/api/v1/reporting/executions",
            headers=admin_headers,
        )
        assert r.status_code == 200
        assert r.json() == []

    async def test_list_executions_with_status_filter(
        self,
        reporting_client,
        mock_db,
        admin_headers,
    ):
        mock_db.execute = AsyncMock(return_value=make_scalars_result([]))
        r = await reporting_client.get(
            "/api/v1/reporting/executions?status=completed",
            headers=admin_headers,
        )
        assert r.status_code == 200

    async def test_get_execution_happy(
        self,
        reporting_client,
        mock_db,
        admin_headers,
    ):
        exe = _fake_execution()
        mock_db.get = AsyncMock(return_value=exe)

        r = await reporting_client.get(
            f"/api/v1/reporting/executions/{_UUID3}",
            headers=admin_headers,
        )
        assert r.status_code == 200
        assert r.json()["execution_type"] == "manual"

    async def test_get_execution_not_found(
        self,
        reporting_client,
        mock_db,
        admin_headers,
    ):
        mock_db.get = AsyncMock(return_value=None)
        r = await reporting_client.get(
            f"/api/v1/reporting/executions/{uuid.uuid4()}",
            headers=admin_headers,
        )
        assert r.status_code == 404


class TestReportingReportTypes:
    """The /report-types info endpoint."""

    async def test_report_types_no_auth(self, api_client):
        r = await api_client.get("/api/v1/reporting/report-types")
        assert r.status_code == 401

    async def test_report_types_happy(
        self,
        reporting_client,
        admin_headers,
    ):
        r = await reporting_client.get(
            "/api/v1/reporting/report-types",
            headers=admin_headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert "report_types" in body
        assert "formats" in body
        assert "frequencies" in body
        assert "delivery_channels" in body
        assert len(body["report_types"]) >= 5


class TestOwnerConsoleSystemHealth:
    """GET /api/v1/console/system/health."""

    async def test_health_no_auth(self, api_client):
        r = await api_client.get("/api/v1/console/system/health")
        assert r.status_code == 401

    async def test_health_non_owner(self, api_client, admin_headers):
        r = await api_client.get(
            "/api/v1/console/system/health",
            headers=admin_headers,
        )
        assert r.status_code == 403

    async def test_health_happy(self, api_client, mock_db, owner_headers):
        mock_redis = AsyncMock()
        mock_redis.llen = AsyncMock(return_value=5)
        mock_redis.ping = AsyncMock(return_value=True)
        mock_redis.close = AsyncMock()

        with patch("redis.asyncio.from_url", return_value=mock_redis):
            r = await api_client.get(
                "/api/v1/console/system/health",
                headers=owner_headers,
            )
        assert r.status_code == 200
        data = r.json()["data"]
        assert "services" in data
        assert "queue" in data
        assert data["services"]["redis"] == "healthy"
        # Honest empty state: uninstrumented infra metrics are null (not a
        # fabricated 100%/0.0), and flagged as not-instrumented.
        assert data["pipeline"]["success_rate_24h"] is None
        assert data["api"]["latency_p50_ms"] is None
        assert data["resources"]["cpu_percent"] is None
        assert data["platforms"]["meta"]["success_rate"] is None
        assert data["instrumented"]["pipeline"] is False
        assert data["instrumented"]["service_health"] is True


# ============================================================================
# FEATURE 14 -- OWNER CONSOLE ANALYTICS
# ============================================================================
#
# console_analytics.py router has prefix="/console" and is mounted
# at /api/v1/console/analytics, giving:
#   /api/v1/console/analytics/console/<endpoint>
#
# Auth: every route depends on require_owner() — unauthenticated requests
# get 401, authenticated non-owner users get 403, owners get through.


class TestOwnerConsoleAnalyticsPlatformOverview:
    """GET /api/v1/console/analytics/console/platform-overview."""

    _URL = "/api/v1/console/analytics/console/platform-overview"

    async def test_no_auth(self, api_client):
        r = await api_client.get(self._URL)
        assert r.status_code == 401

    async def test_non_owner_forbidden(self, api_client, admin_headers):
        r = await api_client.get(self._URL, headers=admin_headers)
        assert r.status_code == 403

    async def test_owner_access_allowed(
        self,
        api_client,
        owner_headers,
        mock_db,
    ):
        """
        Middleware now sets is_superadmin=True for role=owner,
        so the endpoint is reachable and returns 200.
        """
        from unittest.mock import MagicMock

        row = MagicMock(total=0, applied=0, failed=0)
        first_r = MagicMock()
        first_r.first.return_value = row
        empty_iter = MagicMock()
        empty_iter.__iter__ = lambda s: iter([])
        mock_db.execute.side_effect = [first_r, empty_iter, empty_iter]

        r = await api_client.get(self._URL, headers=owner_headers)
        assert r.status_code == 200
        assert r.json()["success"] is True


class TestOwnerConsoleAnalyticsSignalHealthTrends:
    """GET /api/v1/console/analytics/console/signal-health-trends."""

    _URL = "/api/v1/console/analytics/console/signal-health-trends"

    async def test_no_auth(self, api_client):
        r = await api_client.get(self._URL)
        assert r.status_code == 401

    async def test_non_owner_forbidden(self, api_client, admin_headers):
        r = await api_client.get(self._URL, headers=admin_headers)
        assert r.status_code == 403

    async def test_owner_access_allowed(
        self,
        api_client,
        owner_headers,
        mock_db,
    ):
        """Owner can access signal health trends."""
        from unittest.mock import MagicMock

        empty_iter = MagicMock()
        empty_iter.__iter__ = lambda s: iter([])
        mock_db.execute.return_value = empty_iter

        r = await api_client.get(self._URL, headers=owner_headers)
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["trend_direction"] == "insufficient_data"


class TestOwnerConsoleAnalyticsActionsAnalytics:
    """GET /api/v1/console/analytics/console/actions-analytics."""

    _URL = "/api/v1/console/analytics/console/actions-analytics"

    async def test_no_auth(self, api_client):
        r = await api_client.get(self._URL)
        assert r.status_code == 401

    async def test_non_owner_forbidden(self, api_client, admin_headers):
        r = await api_client.get(self._URL, headers=admin_headers)
        assert r.status_code == 403

    async def test_owner_access_allowed(
        self,
        api_client,
        owner_headers,
        mock_db,
    ):
        """Owner can access actions analytics."""
        from unittest.mock import MagicMock

        empty_iter = MagicMock()
        empty_iter.__iter__ = lambda s: iter([])
        mock_db.execute.return_value = empty_iter

        r = await api_client.get(self._URL, headers=owner_headers)
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["total_actions"] == 0
