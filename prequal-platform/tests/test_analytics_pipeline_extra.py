"""Extra coverage for app.services.analytics_pipeline (MID-676).

Covers the previously-uncovered surface:

* dialect helpers ``_team_filter_value`` / ``_days_ago_expr`` (SQLite vs
  PostgreSQL vs dialect-detection failure),
* ``_to_iso`` / ``_safe_rate`` pure helpers,
* ``refresh_all_analytics_views`` / ``_refresh_view`` (concurrent + non),
* the pagination ``*_count`` wrappers,
* ``get_project_compliance_by_id``, ``get_feature_adoption_summary`` and
  ``get_system_health_summary`` row mapping.

A lightweight fake session records the SQL/binds it is handed so the dialect
branching and filter construction are asserted directly - no real DB needed.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from types import SimpleNamespace

import pytest

from app.services import analytics_pipeline as ap


class _Res:
    def __init__(self, scalar=None, rows=None):
        self._scalar = scalar
        self._rows = list(rows or [])

    def scalar(self):
        return self._scalar

    def mappings(self):
        return self

    def first(self):
        return self._rows[0] if self._rows else None

    def all(self):
        return self._rows


class _DB:
    def __init__(self, res=None, dialect="sqlite"):
        self._res = res if res is not None else _Res()
        self.dialect = dialect
        self.calls = []

    def get_bind(self):
        return SimpleNamespace(dialect=SimpleNamespace(name=self.dialect))

    async def execute(self, stmt, params=None):
        self.calls.append((str(stmt), dict(params or {})))
        return self._res


class _RaisingBind:
    def get_bind(self):
        raise RuntimeError("no bind")

    async def execute(self, stmt, params=None):
        raise AssertionError("should not execute")


# ---------------------------------------------------------------------------
# _to_iso / _safe_rate
# ---------------------------------------------------------------------------

def test_to_iso_variants() -> None:
    assert ap._to_iso(None) is None
    assert ap._to_iso("already-iso") == "already-iso"
    assert ap._to_iso(datetime(2025, 1, 2, 3, 4, 5)) == "2025-01-02T03:04:05"
    assert ap._to_iso(object()) .startswith("<object object at")


def test_safe_rate() -> None:
    assert ap._safe_rate(5, 10) == 50.0
    assert ap._safe_rate(1, 0) == 0.0
    assert ap._safe_rate(0, 0) == 0.0
    assert ap._safe_rate(1, 3) == 33.33


# ---------------------------------------------------------------------------
# Dialect helpers
# ---------------------------------------------------------------------------

def test_team_filter_value_sqlite_returns_hex() -> None:
    db = _DB(dialect="sqlite")
    got = ap._team_filter_value(db, "11111111-1111-1111-1111-111111111111")
    assert got == "11111111111111111111111111111111"


def test_team_filter_value_postgres_returns_uuid() -> None:
    db = _DB(dialect="postgresql")
    uid = uuid.UUID("11111111-1111-1111-1111-111111111111")
    assert ap._team_filter_value(db, uid) == uid
    assert isinstance(ap._team_filter_value(db, str(uid)), uuid.UUID)


def test_team_filter_value_bind_failure_defaults_to_uuid() -> None:
    got = ap._team_filter_value(_RaisingBind(), "11111111-1111-1111-1111-111111111111")
    assert isinstance(got, uuid.UUID)


def test_days_ago_expr_dialects() -> None:
    assert ap._days_ago_expr(_DB(dialect="sqlite")) == "date('now', '-' || :days || ' days')"
    assert ap._days_ago_expr(_DB(dialect="postgresql")) == "(CURRENT_DATE - CAST(:days AS integer))"
    # Dialect detection failure falls through to the PostgreSQL expression.
    assert "CURRENT_DATE" in ap._days_ago_expr(_RaisingBind())


# ---------------------------------------------------------------------------
# Materialized view refresh
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_refresh_all_views_concurrently() -> None:
    db = _DB()
    await ap.refresh_all_analytics_views(db, concurrently=True)
    assert len(db.calls) == 5
    assert all("CONCURRENTLY" in stmt for stmt, _ in db.calls)


@pytest.mark.asyncio
async def test_refresh_all_views_non_concurrently() -> None:
    db = _DB()
    await ap.refresh_all_analytics_views(db, concurrently=False)
    assert len(db.calls) == 5
    assert all(
        "REFRESH MATERIALIZED VIEW" in stmt and "CONCURRENTLY" not in stmt
        for stmt, _ in db.calls
    )


@pytest.mark.asyncio
async def test_refresh_view_single() -> None:
    db = _DB()
    await ap._refresh_view(db, "mv_recent_alerts", concurrently=True)
    assert len(db.calls) == 1
    assert "mv_recent_alerts" in db.calls[0][0]


# ---------------------------------------------------------------------------
# Count wrappers
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_certification_export_count_filters_and_binds() -> None:
    db = _DB(_Res(scalar=7), dialect="sqlite")
    got = await ap.get_certification_export_count(
        db,
        expiration_bucket="30d",
        subcontractor_id="abc",
        team_id="11111111-1111-1111-1111-111111111111",
    )
    assert got == 7
    stmt, params = db.calls[0]
    assert "expiration_bucket = :bucket" in stmt
    assert "subcontractor_id = :sub_id" in stmt
    assert "team_id = :team_id" in stmt
    assert params["bucket"] == "30d"
    assert params["sub_id"] == "abc"
    assert params["team_id"] == "11111111111111111111111111111111"


@pytest.mark.asyncio
async def test_certification_export_count_defaults_to_zero() -> None:
    db = _DB(_Res(scalar=None))
    assert await ap.get_certification_export_count(db) == 0


@pytest.mark.asyncio
async def test_recent_alerts_count_with_and_without_status() -> None:
    with_status = _DB(_Res(scalar=3))
    assert await ap.get_recent_alerts_count(with_status, status="pending") == 3
    assert with_status.calls[0][1]["status"] == "pending"

    without = _DB(_Res(scalar=None))
    assert await ap.get_recent_alerts_count(without) == 0
    assert "status = :status" not in without.calls[0][0]


@pytest.mark.asyncio
async def test_feature_adoption_count_uses_dialect_expr() -> None:
    db = _DB(_Res(scalar=11), dialect="sqlite")
    got = await ap.get_feature_adoption_summary_count(db, feature_name="reports", days=30)
    assert got == 11
    stmt, params = db.calls[0]
    assert "date('now'" in stmt
    assert params["feature_name"] == "reports"
    assert params["days"] == 30


# ---------------------------------------------------------------------------
# Row mapping
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_project_compliance_by_id_maps_row() -> None:
    pid = uuid.uuid4()
    row = {
        "project_id": pid,
        "project_name": "Tower A",
        "project_number": "P-1",
        "project_status": "active",
        "start_date": datetime(2025, 1, 1),
        "estimated_end_date": None,
        "total_subcontractors": 4,
        "active_subcontractors": 4,
        "suspended_subcontractors": 0,
        "compliant_subcontractors": 2,
        "open_violations": 1,
        "open_osha_violations": 0,
        "total_open_penalties": 1500,
        "expiring_soon_subcontractors": 1,
        "computed_at": datetime(2025, 2, 1, 9, 0),
    }
    db = _DB(_Res(rows=[row]))
    out = await ap.get_project_compliance_by_id(db, str(pid))
    assert out is not None
    assert out["project_id"] == str(pid)
    assert out["compliance_rate"] == 50.0
    assert out["total_open_penalties"] == 1500.0
    assert out["computed_at"] == "2025-02-01T09:00:00"
    assert out["start_date"] == "2025-01-01T00:00:00"
    assert db.calls[0][1]["project_id"] == str(pid)


@pytest.mark.asyncio
async def test_project_compliance_by_id_missing_returns_none() -> None:
    db = _DB(_Res(rows=[]))
    assert await ap.get_project_compliance_by_id(db, str(uuid.uuid4())) is None


@pytest.mark.asyncio
async def test_feature_adoption_summary_maps_rows() -> None:
    row = {
        "feature_name": "reports",
        "event_date": datetime(2025, 3, 1),
        "total_events": 10,
        "unique_users": 4,
        "view_count": 6,
        "action_count": 3,
        "export_count": 1,
        "computed_at": None,
    }
    db = _DB(_Res(rows=[row]))
    out = await ap.get_feature_adoption_summary(db, feature_name="reports", days=7)
    assert out[0]["feature_name"] == "reports"
    assert out[0]["event_date"] == "2025-03-01T00:00:00"
    assert out[0]["computed_at"] is None
    assert db.calls[0][1]["feature_name"] == "reports"


@pytest.mark.asyncio
async def test_system_health_summary_maps_rows() -> None:
    row = {
        "service_name": "prequal-api",
        "metric_name": "latency",
        "metric_unit": "ms",
        "avg_value": 12.34567,
        "min_value": None,
        "max_value": 20,
        "p95_value": 18.4,
        "total_count": 100,
        "computed_at": datetime(2025, 4, 1),
    }
    db = _DB(_Res(rows=[row]))
    out = await ap.get_system_health_summary(db, service_name="prequal-api", metric_name="latency")
    assert out[0]["avg_value"] == 12.3457
    assert out[0]["min_value"] == 0.0
    assert out[0]["max_value"] == 20.0
    assert out[0]["computed_at"] == "2025-04-01T00:00:00"
    assert db.calls[0][1] == {"service_name": "prequal-api", "metric_name": "latency"}
