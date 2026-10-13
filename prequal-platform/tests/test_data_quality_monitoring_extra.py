"""Extra coverage for app.services.data_quality_monitoring (MID-676).

Covers the parts the existing data-quality suite missed:

* ``_parse_dt`` coercion edge cases,
* the dialect-portable SQL fragment helpers (SQLite vs PostgreSQL branches),
* ``log_pipeline_performance`` duration handling,
* ``refresh_data_quality_views`` (SQLite short-circuit + PostgreSQL
  concurrent->non-concurrent fallback),
* ``run_daily_data_quality_check`` orchestration,
* ``_persist_alert`` audit-emission failure being swallowed.

Fake sessions / dialect binds record what the code asks for; no real DB.
"""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy.dialects.sqlite.base import SQLiteDialect

from app.services import data_quality_monitoring as dqm


class _Bind:
    def __init__(self, dialect):
        self.dialect = dialect


class _DB:
    def __init__(self, dialect=None, res=None):
        self.bind = _Bind(dialect if dialect is not None else SQLiteDialect())
        self._res = res if res is not None else SimpleNamespace(rowcount=0)
        self.calls = []
        self.committed = False
        self.rolled_back = False

    async def execute(self, stmt, params=None):
        self.calls.append((str(stmt), dict(params or {})))
        if isinstance(self._res, Exception):
            raise self._res
        return self._res

    async def commit(self):
        self.committed = True

    async def rollback(self):
        self.rolled_back = True


def _pg_db(dialect=None):
    # Any non-SQLiteDialect object makes _is_sqlite() return False.
    return _DB(dialect=object())


# ---------------------------------------------------------------------------
# _parse_dt
# ---------------------------------------------------------------------------

def test_parse_dt_variants() -> None:
    assert dqm._parse_dt(None) is None
    aware = datetime(2025, 1, 15, 10, 0, tzinfo=timezone.utc)
    out = dqm._parse_dt(aware)
    assert out == datetime(2025, 1, 15, 10, 0) and out.tzinfo is None
    assert dqm._parse_dt("2025-01-15T10:00:00Z") == datetime(2025, 1, 15, 10, 0)
    assert dqm._parse_dt("2025-01-15 10:00:00") == datetime(2025, 1, 15, 10, 0)
    assert dqm._parse_dt("not-a-date") is None


# ---------------------------------------------------------------------------
# Dialect-portable SQL fragments
# ---------------------------------------------------------------------------

def test_sql_fragments_sqlite() -> None:
    db = _DB()
    assert "date('now'" in dqm._days_ago_date_expr(db)
    assert "datetime('now'" in dqm._age_comparison(db, "computed_at", "25 hours")
    assert "julianday" in dqm._duration_seconds_expr(db, "started_at", "completed_at")
    assert "REAL" in dqm._ratio_round_expr(db, "a", "b")


def test_sql_fragments_postgres() -> None:
    db = _pg_db()
    assert dqm._days_ago_date_expr(db) == "(CURRENT_DATE - CAST(:days AS integer))"
    assert dqm._age_comparison(db, "computed_at", "25 hours") == "computed_at < (NOW() - INTERVAL '25 hours')"
    assert "EXTRACT(EPOCH" in dqm._duration_seconds_expr(db, "started_at", "completed_at")
    assert "NUMERIC" in dqm._ratio_round_expr(db, "a", "b")


# ---------------------------------------------------------------------------
# log_pipeline_performance
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_log_pipeline_performance_with_timestamps() -> None:
    db = _DB()
    start = datetime(2025, 1, 1, 0, 0, 0)
    end = datetime(2025, 1, 1, 0, 0, 2, 500000)
    await dqm.log_pipeline_performance(
        db,
        run_id="run-1",
        job_name="osha",
        job_type="etl",
        stage_name="extract",
        started_at=start,
        completed_at=end,
        records_in=10,
        records_out=9,
    )
    assert db.committed is True
    _stmt, params = db.calls[0]
    assert params["duration_ms"] == 2500
    assert params["records_in"] == 10


@pytest.mark.asyncio
async def test_log_pipeline_performance_without_timestamps() -> None:
    db = _DB()
    await dqm.log_pipeline_performance(
        db, run_id="run-2", job_name="osha", job_type="etl", stage_name="load"
    )
    _stmt, params = db.calls[0]
    assert params["duration_ms"] is None


# ---------------------------------------------------------------------------
# refresh_data_quality_views
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_refresh_data_quality_views_sqlite_skips() -> None:
    db = _DB()  # sqlite dialect
    await dqm.refresh_data_quality_views(db)
    assert db.calls == []


@pytest.mark.asyncio
async def test_refresh_data_quality_views_postgres_and_fallback() -> None:
    db = _pg_db()
    # First view's CONCURRENTLY refresh fails -> rollback + non-concurrent retry.
    calls = {"n": 0}
    orig = db.execute

    async def _execute(stmt, params=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("no unique index")
        return await orig(stmt, params)

    db.execute = _execute
    await dqm.refresh_data_quality_views(db)
    assert db.rolled_back is True
    # 6 views; first is refreshed twice (concurrent + non-concurrent), rest once.
    assert calls["n"] == 7


# ---------------------------------------------------------------------------
# run_daily_data_quality_check
# ---------------------------------------------------------------------------

class _Session:
    def __init__(self):
        self.closed = False

    async def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_run_daily_data_quality_check_orchestrates(monkeypatch) -> None:
    session = _Session()
    called = {}

    async def _health(_db):
        called["health"] = True
        return {"alerts_triggered": []}

    async def _refresh(_db):
        called["refresh"] = True

    async def _archive_sync(_db):
        called["archive_sync"] = True
        return {"archived": 3}

    async def _archive_dqr(_db):
        called["archive_dqr"] = True
        return {"archived": 1}

    monkeypatch.setattr(dqm, "AsyncSessionLocal", lambda: session)
    monkeypatch.setattr(dqm, "run_data_quality_health_check", _health)
    monkeypatch.setattr(dqm, "refresh_data_quality_views", _refresh)
    monkeypatch.setattr(dqm, "archive_old_sync_logs", _archive_sync)
    monkeypatch.setattr(dqm, "archive_old_data_quality_results", _archive_dqr)

    results = await dqm.run_daily_data_quality_check()
    assert called == {"health": True, "refresh": True, "archive_sync": True, "archive_dqr": True}
    assert results["archived"] == {"sync_logs": {"archived": 3}, "data_quality_results": {"archived": 1}}
    assert session.closed is True


# ---------------------------------------------------------------------------
# _persist_alert audit emission
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_persist_alert_swallows_audit_failure(monkeypatch) -> None:
    db = _DB()

    def _boom(*args, **kwargs):
        raise RuntimeError("audit down")

    import app.services.audit_logging as audit

    monkeypatch.setattr(audit, "log_data_access", _boom)
    # Must not raise even though the audit emission fails.
    await dqm._persist_alert(
        db, {"alert_type": "stale", "severity": "high", "source_table": "sync_run_logs", "message": "m"}
    )
    assert db.committed is True
