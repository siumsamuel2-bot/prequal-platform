"""Extra coverage for app.services.external_compliance_pipeline (MID-676).

Targets the parts not exercised by ``test_external_compliance_pipeline.py``:

* the ``find_subcontractor_by_*`` lookup helpers (guards, normalisation, name
  fallback),
* ``record_pipeline_metric`` (success + swallowed failure),
* ``_parse_dt`` / ``parse_date`` coercion edge cases,
* ``_refresh_materialized_view`` concurrent->non-concurrent fallback,
* ``refresh_analytics_views`` (SQLite short-circuit + PostgreSQL path),
* ``run_full_pipeline`` orchestration (success, OSHA failure, per-state
  failure, and auto state discovery).

No network or real database is used: DB sessions, sync entry points, and the
materialized-view refresh are replaced with lightweight fakes that record what
they were asked to do.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest

from app.services import external_compliance_pipeline as epl


# ---------------------------------------------------------------------------
# find_subcontractor_*
# ---------------------------------------------------------------------------

class _Result:
    def __init__(self, value=None):
        self._value = value

    def scalar_one_or_none(self):
        return self._value

    def mappings(self):
        return self

    def all(self):
        return []


class _FindDB:
    def __init__(self, results):
        self._results = list(results)
        self.calls = []

    async def execute(self, stmt, params=None):
        self.calls.append((str(stmt), dict(params or {})))
        return self._results.pop(0)


@pytest.mark.asyncio
async def test_find_by_ein_empty_returns_none() -> None:
    db = _FindDB([])
    assert await epl.find_subcontractor_by_ein(db, "") is None
    assert db.calls == []


@pytest.mark.asyncio
async def test_find_by_ein_normalizes_and_returns_id() -> None:
    sid = uuid.uuid4()
    db = _FindDB([_Result(sid)])
    got = await epl.find_subcontractor_by_ein(db, "  ab-12 ")
    assert got == sid
    assert db.calls[0][1]["ein"] == "AB-12"


@pytest.mark.asyncio
async def test_find_by_license_guard_and_match() -> None:
    empty_db = _FindDB([])
    assert await epl.find_subcontractor_by_license(empty_db, "", "TX") is None
    assert await epl.find_subcontractor_by_license(empty_db, "L1", "") is None
    assert empty_db.calls == []

    sid = uuid.uuid4()
    db = _FindDB([_Result(sid)])
    got = await epl.find_subcontractor_by_license(db, " l1 ", " tx ")
    assert got == sid
    assert db.calls[0][1] == {"num": "L1", "st": "TX"}


@pytest.mark.asyncio
async def test_find_by_name_short_guard() -> None:
    db = _FindDB([])
    assert await epl.find_subcontractor_by_name(db, "AB") is None
    assert db.calls == []


@pytest.mark.asyncio
async def test_find_by_name_exact_hit() -> None:
    sid = uuid.uuid4()
    db = _FindDB([_Result(sid)])
    assert await epl.find_subcontractor_by_name(db, "Acme Corp") == sid
    assert len(db.calls) == 1


@pytest.mark.asyncio
async def test_find_by_name_falls_back_to_like() -> None:
    sid = uuid.uuid4()
    db = _FindDB([_Result(None), _Result(sid)])
    assert await epl.find_subcontractor_by_name(db, "Acme") == sid
    assert len(db.calls) == 2
    assert db.calls[1][1]["pat"] == "%ACME%"


# ---------------------------------------------------------------------------
# record_pipeline_metric
# ---------------------------------------------------------------------------

class _MetricDB:
    def __init__(self, fail=False):
        self.fail = fail
        self.calls = []
        self.committed = False

    async def execute(self, stmt, params=None):
        if self.fail:
            raise RuntimeError("boom")
        self.calls.append(dict(params or {}))

    async def commit(self):
        self.committed = True


@pytest.mark.asyncio
async def test_record_pipeline_metric_success() -> None:
    db = _MetricDB()
    await epl.record_pipeline_metric(
        db, job_name="osha_daily_sync", metric_name="duration", metric_value=1.5, metric_unit="s"
    )
    assert db.committed is True
    assert db.calls[0]["service_name"] == "osha_daily_sync"
    assert db.calls[0]["metric_value"] == 1.5


@pytest.mark.asyncio
async def test_record_pipeline_metric_swallows_failure() -> None:
    db = _MetricDB(fail=True)
    # Must not raise: metrics are best-effort.
    await epl.record_pipeline_metric(
        db, job_name="j", metric_name="m", metric_value=1.0
    )
    assert db.committed is False


# ---------------------------------------------------------------------------
# _parse_dt / parse_date
# ---------------------------------------------------------------------------

def test_parse_dt_none() -> None:
    assert epl._parse_dt(None) is None


def test_parse_dt_datetime_strips_tz() -> None:
    aware = datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
    out = epl._parse_dt(aware)
    assert out == datetime(2025, 1, 15, 10, 0, 0)
    assert out.tzinfo is None


def test_parse_dt_iso_variants() -> None:
    assert epl._parse_dt("2025-01-15T10:00:00Z") == datetime(2025, 1, 15, 10, 0, 0)
    assert epl._parse_dt("2025-01-15 10:00:00") == datetime(2025, 1, 15, 10, 0, 0)
    # The first (None) format splits on "." so sub-second precision is dropped.
    assert epl._parse_dt("2025-01-15 10:00:00.123456") == datetime(2025, 1, 15, 10, 0, 0)


def test_parse_dt_invalid_returns_none() -> None:
    assert epl._parse_dt("not-a-date") is None


def test_parse_date_datetime_branch() -> None:
    # ``datetime`` is a subclass of ``date``, so the earlier isinstance check
    # returns it unchanged; a plain ``date`` passes through too.
    dt = datetime(2025, 3, 2, 8, 30)
    assert epl.parse_date(dt) is dt
    assert epl.parse_date(date(2025, 3, 2)) == date(2025, 3, 2)


# ---------------------------------------------------------------------------
# Materialized view refresh
# ---------------------------------------------------------------------------

class _RefreshDB:
    def __init__(self):
        self.executed = 0
        self.rolled_back = False

    async def execute(self, stmt):
        self.executed += 1
        if self.executed == 1:
            raise RuntimeError("no unique index for CONCURRENTLY")

    async def rollback(self):
        self.rolled_back = True


@pytest.mark.asyncio
async def test_refresh_materialized_view_falls_back_non_concurrently() -> None:
    db = _RefreshDB()
    await epl._refresh_materialized_view(db, "mv_compliance_summary")
    assert db.rolled_back is True
    assert db.executed == 2


class _DialectDB:
    def __init__(self, dialect: str):
        self.dialect = dialect
        self.executed = []
        self.committed = False

    def get_bind(self):
        return SimpleNamespace(dialect=SimpleNamespace(name=self.dialect))

    async def execute(self, stmt):
        self.executed.append(stmt)

    async def commit(self):
        self.committed = True


@pytest.mark.asyncio
async def test_refresh_analytics_views_sqlite_short_circuits() -> None:
    db = _DialectDB("sqlite")
    await epl.refresh_analytics_views(db)
    assert db.executed == []
    assert db.committed is False


@pytest.mark.asyncio
async def test_refresh_analytics_views_postgres_refreshes_all(monkeypatch) -> None:
    db = _DialectDB("postgresql")
    refreshed = []

    async def _fake_refresh(_db, view_name):
        refreshed.append(view_name)

    async def _no_sleep(_seconds):
        return None

    monkeypatch.setattr(epl, "_refresh_materialized_view", _fake_refresh)
    monkeypatch.setattr(epl.asyncio, "sleep", _no_sleep)

    await epl.refresh_analytics_views(db)
    assert refreshed == [
        "mv_compliance_summary",
        "mv_violation_trends",
        "mv_certification_status",
        "mv_project_compliance",
    ]
    assert db.committed is True


# ---------------------------------------------------------------------------
# run_full_pipeline orchestration
# ---------------------------------------------------------------------------

class _Session:
    def __init__(self):
        self.closed = False

    async def close(self):
        self.closed = True


def _fake_run(**kw):
    base = dict(
        id=uuid.uuid4(),
        status="completed",
        records_extracted=1,
        records_inserted=1,
        records_updated=0,
        records_failed=0,
        records_matched=1,
    )
    base.update(kw)
    return SimpleNamespace(**base)


@pytest.mark.asyncio
async def test_run_full_pipeline_success(monkeypatch) -> None:
    session = _Session()

    async def _osha(**kw):
        return _fake_run()

    async def _state(**kw):
        return _fake_run(status="completed", records_extracted=2)

    monkeypatch.setattr(epl, "AsyncSessionLocal", lambda: session)
    monkeypatch.setattr(epl, "run_osha_sync", _osha)
    monkeypatch.setattr(epl, "run_state_credential_sync", _state)

    results = await epl.run_full_pipeline(state_codes=["CA"], triggered_by="test")
    assert results["osha"]["status"] == "completed"
    assert results["state_credentials"][0]["state"] == "CA"
    assert results["state_credentials"][0]["extracted"] == 2
    assert "completed_at" in results
    assert session.closed is True


@pytest.mark.asyncio
async def test_run_full_pipeline_osha_failure_is_logged_not_raised(monkeypatch) -> None:
    session = _Session()
    logged = []

    async def _osha(**kw):
        raise RuntimeError("osha down")

    async def _state(**kw):
        return _fake_run()

    async def _log(db, run, triggered_by):
        logged.append(run)

    monkeypatch.setattr(epl, "AsyncSessionLocal", lambda: session)
    monkeypatch.setattr(epl, "run_osha_sync", _osha)
    monkeypatch.setattr(epl, "run_state_credential_sync", _state)
    monkeypatch.setattr(epl, "_log_run", _log)

    results = await epl.run_full_pipeline(state_codes=["CA"], triggered_by="test")
    assert results["osha"]["status"] == "failed"
    assert "osha down" in results["osha"]["error"]
    assert len(logged) == 1
    assert session.closed is True


@pytest.mark.asyncio
async def test_run_full_pipeline_state_failure_recorded(monkeypatch) -> None:
    session = _Session()

    async def _osha(**kw):
        return _fake_run()

    async def _state(**kw):
        raise RuntimeError("state api down")

    monkeypatch.setattr(epl, "AsyncSessionLocal", lambda: session)
    monkeypatch.setattr(epl, "run_osha_sync", _osha)
    monkeypatch.setattr(epl, "run_state_credential_sync", _state)

    results = await epl.run_full_pipeline(state_codes=["TX"], triggered_by="test")
    assert results["state_credentials"][0]["state"] == "TX"
    assert results["state_credentials"][0]["status"] == "failed"


@pytest.mark.asyncio
async def test_run_full_pipeline_discovers_and_dedupes_states(monkeypatch) -> None:
    session = _Session()
    seen = []

    async def _osha(**kw):
        return _fake_run()

    async def _state(**kw):
        seen.append(kw["state_code"])
        return _fake_run()

    monkeypatch.setattr(epl, "AsyncSessionLocal", lambda: session)
    monkeypatch.setattr(epl, "run_osha_sync", _osha)
    monkeypatch.setattr(epl, "run_state_credential_sync", _state)
    monkeypatch.setattr(epl, "list_supported_states", lambda: ["CA", "TX", "CA"])
    monkeypatch.setenv("STATE_API_URL_NV", "https://example.invalid")

    results = await epl.run_full_pipeline(state_codes=None, triggered_by="test")
    # CA appears once (de-duped), TX once, and NV from the env var.
    assert seen == ["CA", "TX", "NV"]
    assert len(results["state_credentials"]) == 3
