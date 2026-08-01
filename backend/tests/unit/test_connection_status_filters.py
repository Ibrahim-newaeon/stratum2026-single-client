# =============================================================================
# ADs Growth System - PlatformConnection status-filter regression tests
# =============================================================================
"""Regression tests for the ``PlatformConnection.is_connected`` phantom
attribute (spec-audit P0-4). The model's source of truth is ``status ==
ConnectionStatus.CONNECTED``; filtering on the nonexistent ``is_connected``
column made ``update_metrics_all`` / ``calculate_all_signal_health`` raise
AttributeError inside their try blocks and report 0 platforms synced, and
made the console system-health helper report "no_connections" forever.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.campaign_builder import ConnectionStatus, PlatformConnection


def _conn(status: ConnectionStatus, last_error: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(platform="meta", status=status, last_error=last_error)


class TestModelContract:
    def test_platform_connection_has_no_is_connected_column(self):
        """The phantom attribute must not silently reappear."""
        assert not hasattr(PlatformConnection, "is_connected")
        assert hasattr(PlatformConnection, "status")

    def test_status_filter_compiles(self):
        """Building the corrected filter must not raise AttributeError."""
        from sqlalchemy import select

        stmt = select(PlatformConnection).where(
            PlatformConnection.status == ConnectionStatus.CONNECTED
        )
        assert "status" in str(stmt)


class TestUpdateMetricsAll:
    def test_counts_connected_platforms(self):
        from app.stratum.workers import data_sync

        connected = [
            _conn(ConnectionStatus.CONNECTED),
            _conn(ConnectionStatus.CONNECTED),
        ]

        db = MagicMock()
        db.execute.return_value.scalars.return_value.all.return_value = connected
        factory = MagicMock()
        factory.return_value.__enter__ = MagicMock(return_value=db)
        factory.return_value.__exit__ = MagicMock(return_value=False)

        with patch("app.db.session.SyncSessionLocal", factory):
            result = data_sync.update_metrics_all()

        assert result["status"] == "completed"
        assert result["platforms_synced"] == 2
        assert "error" not in result

        # The query itself must filter on the real status column.
        stmt = db.execute.call_args[0][0]
        assert "status" in str(stmt)


class TestCalculateAllSignalHealth:
    def test_counts_healthy_and_degraded(self):
        from app.stratum.workers import data_sync

        conns = [
            _conn(ConnectionStatus.CONNECTED),
            _conn(ConnectionStatus.CONNECTED, last_error="token expired"),
        ]

        exec_result = MagicMock()
        exec_result.scalars.return_value.all.return_value = conns

        db = AsyncMock()
        db.execute = AsyncMock(return_value=exec_result)
        factory = MagicMock()
        factory.return_value.__aenter__ = AsyncMock(return_value=db)
        factory.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("app.db.session.async_session_factory", factory):
            result = data_sync.calculate_all_signal_health()

        assert "error" not in result
        assert result["accounts_processed"] == 2
        assert result["healthy"] == 1
        assert result["degraded"] == 1


class TestConsoleSystemHealth:
    @pytest.mark.asyncio
    async def test_health_rate_from_status_column(self):
        from app.api.v1.endpoints.console import _get_system_health

        conns = [
            _conn(ConnectionStatus.CONNECTED),
            _conn(ConnectionStatus.CONNECTED),
            _conn(ConnectionStatus.ERROR, last_error="boom"),
        ]
        exec_result = MagicMock()
        exec_result.scalars.return_value.all.return_value = conns

        db = AsyncMock()
        db.execute = AsyncMock(return_value=exec_result)

        health = await _get_system_health(db)

        # 2 of 3 connections CONNECTED -> 66.7% -> "critical" bucket (<70%).
        assert health["pipeline_success_rate"] == 66.7
        assert health["platform_status"] == "critical"

    @pytest.mark.asyncio
    async def test_no_connections(self):
        from app.api.v1.endpoints.console import _get_system_health

        exec_result = MagicMock()
        exec_result.scalars.return_value.all.return_value = []

        db = AsyncMock()
        db.execute = AsyncMock(return_value=exec_result)

        health = await _get_system_health(db)
        assert health["platform_status"] == "no_connections"
        assert health["pipeline_success_rate"] is None
