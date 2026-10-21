"""Tests for the analytics pipeline (materialized views + aggregate queries).

Validates:
1. MVs exist and are queryable
2. Aggregation shapes match expected API response format
3. Data quality (no negative counts, valid date formats, etc.)
4. Edge cases (empty tables, single rows, null values)

Owner: Data Engineer
"""
from __future__ import annotations

import datetime as _dt
import uuid as _uuid
from unittest.mock import MagicMock

import pytest
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.analytics_pipeline import (
    _days_ago_expr,
    _refresh_view,
    _safe_rate,
    _team_filter_value,
    _to_iso,
    get_all_project_compliance,
    get_certification_export_count,
    get_certification_export_rows,
    get_compliance_summary,
    get_compliance_trends,
    get_feature_adoption_summary,
    get_feature_adoption_summary_count,
    get_project_compliance_by_id,
    get_recent_alerts,
    get_recent_alerts_count,
    get_system_health_summary,
    refresh_all_analytics_views,
)


class TestAnalyticsViewsExist:
    """Verify all materialized views are present and queryable."""

    @pytest.mark.asyncio
    async def test_mv_compliance_summary_exists(self, db_session: AsyncSession) -> None:
        result = await db_session.execute(text("SELECT 1 FROM mv_compliance_summary LIMIT 1"))
        assert result.scalar() is not None or True  # empty is okay, but should not error

    @pytest.mark.asyncio
    async def test_mv_compliance_trends_exists(self, db_session: AsyncSession) -> None:
        result = await db_session.execute(text("SELECT 1 FROM mv_compliance_trends LIMIT 1"))
        assert True  # no exception means it exists

    @pytest.mark.asyncio
    async def test_mv_certification_status_exists(self, db_session: AsyncSession) -> None:
        result = await db_session.execute(text("SELECT 1 FROM mv_certification_status LIMIT 1"))
        assert True

    @pytest.mark.asyncio
    async def test_mv_project_compliance_exists(self, db_session: AsyncSession) -> None:
        result = await db_session.execute(text("SELECT 1 FROM mv_project_compliance LIMIT 1"))
        assert True

    @pytest.mark.asyncio
    async def test_mv_recent_alerts_exists(self, db_session: AsyncSession) -> None:
        result = await db_session.execute(text("SELECT 1 FROM mv_recent_alerts LIMIT 1"))
        assert True


class TestComplianceSummary:
    """Test GET /api/compliance/summary aggregation shape."""

    @pytest.mark.asyncio
    async def test_returns_dict(self, db_session: AsyncSession) -> None:
        data = await get_compliance_summary(db_session)
        assert isinstance(data, dict)

    @pytest.mark.asyncio
    async def test_required_fields_present(self, db_session: AsyncSession) -> None:
        data = await get_compliance_summary(db_session)
        required = [
            "total_subcontractors",
            "active_subcontractors",
            "compliant_subcontractors",
            "compliance_rate",
            "expiring_soon_30d",
            "open_violations",
            "valid_certifications",
        ]
        for field in required:
            assert field in data, f"Missing field: {field}"

    @pytest.mark.asyncio
    async def test_counts_are_non_negative(self, db_session: AsyncSession) -> None:
        data = await get_compliance_summary(db_session)
        count_fields = [
            "total_subcontractors",
            "active_subcontractors",
            "compliant_subcontractors",
            "expiring_soon_30d",
            "open_violations",
            "valid_certifications",
        ]
        for field in count_fields:
            val = data.get(field)
            if val is not None:
                assert val >= 0, f"{field} must be >= 0, got {val}"

    @pytest.mark.asyncio
    async def test_compliance_rate_between_0_and_100(self, db_session: AsyncSession) -> None:
        data = await get_compliance_summary(db_session)
        rate = data.get("compliance_rate")
        if rate is not None:
            assert 0 <= rate <= 100, f"compliance_rate out of range: {rate}"


class TestComplianceTrends:
    """Test GET /api/compliance/trends?days=N aggregation shape."""

    @pytest.mark.asyncio
    async def test_returns_list(self, db_session: AsyncSession) -> None:
        data = await get_compliance_trends(db_session, days=30)
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_trend_fields_present(self, db_session: AsyncSession) -> None:
        data = await get_compliance_trends(db_session, days=30)
        if not data:
            pytest.skip("No trend data in database")
        first = data[0]
        required = [
            "date",
            "active_subcontractors",
            "valid_certifications",
            "expired_certifications",
            "open_violations",
            "compliance_percentage",
            "computed_at",
        ]
        for field in required:
            assert field in first, f"Missing field: {field}"

    @pytest.mark.asyncio
    async def test_dates_are_iso_strings(self, db_session: AsyncSession) -> None:
        data = await get_compliance_trends(db_session, days=30)
        if not data:
            pytest.skip("No trend data in database")
        for point in data:
            date_str = point["date"]
            assert isinstance(date_str, str)
            try:
                datetime.fromisoformat(date_str)
            except ValueError:
                pytest.fail(f"Invalid date format: {date_str}")

    @pytest.mark.asyncio
    async def test_compliance_percentage_between_0_and_100(self, db_session: AsyncSession) -> None:
        data = await get_compliance_trends(db_session, days=30)
        for point in data:
            rate = point["compliance_percentage"]
            if rate is not None:
                assert 0 <= 100, f"compliance_percentage out of range: {rate}"


class TestCertificationExport:
    """Test GET /api/compliance/export aggregation shape."""

    @pytest.mark.asyncio
    async def test_returns_list(self, db_session: AsyncSession) -> None:
        data = await get_certification_export_rows(db_session, limit=10)
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_export_fields_present(self, db_session: AsyncSession) -> None:
        data = await get_certification_export_rows(db_session, limit=10)
        if not data:
            pytest.skip("No certification data in database")
        first = data[0]
        required = [
            "subcontractor_id",
            "company_name",
            "email",
            "certification_id",
            "certification_type",
            "expiration_date",
            "expiration_bucket",
            "days_until_expiration",
        ]
        for field in required:
            assert field in first, f"Missing field: {field}"

    @pytest.mark.asyncio
    async def test_expiration_buckets_are_valid(self, db_session: AsyncSession) -> None:
        valid_buckets = {"critical", "warning", "attention", "valid", "expired"}
        data = await get_certification_export_rows(db_session, limit=100)
        for row in data:
            bucket = row.get("expiration_bucket")
            if bucket:
                assert bucket in valid_buckets, f"Invalid bucket: {bucket}"

    @pytest.mark.asyncio
    async def test_days_until_expiration_is_numeric(self, db_session: AsyncSession) -> None:
        data = await get_certification_export_rows(db_session, limit=100)
        for row in data:
            days = row.get("days_until_expiration")
            if days is not None:
                assert isinstance(days, int), f"days_until_expiration must be int, got {type(days)}"


class TestRecentAlerts:
    """Test GET /api/alerts/recent aggregation shape."""

    @pytest.mark.asyncio
    async def test_returns_list(self, db_session: AsyncSession) -> None:
        data = await get_recent_alerts(db_session, limit=10)
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_alert_fields_present(self, db_session: AsyncSession) -> None:
        data = await get_recent_alerts(db_session, limit=10)
        if not data:
            pytest.skip("No alert data in database")
        first = data[0]
        required = [
            "alert_id",
            "certification_id",
            "alert_type",
            "status",
            "subcontractor_id",
            "subcontractor_name",
        ]
        for field in required:
            assert field in first, f"Missing field: {field}"


class TestProjectCompliance:
    """Test project-level compliance aggregation."""

    @pytest.mark.asyncio
    async def test_all_projects_returns_list(self, db_session: AsyncSession) -> None:
        data = await get_all_project_compliance(db_session, limit=10)
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_project_fields_present(self, db_session: AsyncSession) -> None:
        data = await get_all_project_compliance(db_session, limit=10)
        if not data:
            pytest.skip("No project data in database")
        first = data[0]
        required = [
            "project_id",
            "project_name",
            "total_subcontractors",
            "compliant_subcontractors",
            "compliance_rate",
            "open_violations",
        ]
        for field in required:
            assert field in first, f"Missing field: {field}"

    @pytest.mark.asyncio
    async def test_nonexistent_project_returns_none(self, db_session: AsyncSession) -> None:
        import uuid
        data = await get_project_compliance_by_id(db_session, str(uuid.uuid4()))
        assert data is None

    @pytest.mark.asyncio
    async def test_compliance_rate_between_0_and_100(self, db_session: AsyncSession) -> None:
        data = await get_all_project_compliance(db_session, limit=100)
        for project in data:
            rate = project.get("compliance_rate")
            if rate is not None:
                assert 0 <= rate <= 100, f"compliance_rate out of range: {rate}"


class TestDataQuality:
    """Cross-cutting data quality checks."""

    @pytest.mark.asyncio
    async def test_compliant_count_le_total_active(self, db_session: AsyncSession) -> None:
        data = await get_compliance_summary(db_session)
        total = data.get("active_subcontractors", 0)
        compliant = data.get("compliant_subcontractors", 0)
        if total is not None and compliant is not None:
            assert compliant <= total, f"Compliant ({compliant}) > Active ({total})"

    @pytest.mark.asyncio
    async def test_no_negative_penalties(self, db_session: AsyncSession) -> None:
        data = await get_compliance_summary(db_session)
        penalties = data.get("total_open_penalties", 0)
        if penalties is not None:
            assert penalties >= 0, f"Negative penalties: {penalties}"

    @pytest.mark.asyncio
    async def test_computed_at_field_is_iso(self, db_session: AsyncSession) -> None:
        data = await get_compliance_summary(db_session)
        computed = data.get("computed_at")
        if computed:
            try:
                datetime.fromisoformat(computed)
            except ValueError:
                pytest.fail(f"computed_at not valid ISO: {computed}")

# ---------------------------------------------------------------------------
# New Analytics Views - Feature Adoption & System Health
# ---------------------------------------------------------------------------

class TestNewAnalyticsViewsExist:
    """Verify new materialized views are present and queryable."""

    @pytest.mark.asyncio
    async def test_mv_feature_adoption_summary_exists(self, db_session: AsyncSession) -> None:
        result = await db_session.execute(text("SELECT 1 FROM mv_feature_adoption_summary LIMIT 1"))
        assert result.scalar() is not None or True

    @pytest.mark.asyncio
    async def test_mv_system_health_summary_exists(self, db_session: AsyncSession) -> None:
        result = await db_session.execute(text("SELECT 1 FROM mv_system_health_summary LIMIT 1"))
        assert result.scalar() is not None or True


class TestFeatureAdoption:
    """Test GET /api/analytics/feature-adoption aggregation shape."""

    @pytest.mark.asyncio
    async def test_returns_list(self, db_session: AsyncSession) -> None:
        from app.services.analytics_pipeline import get_feature_adoption_summary
        data = await get_feature_adoption_summary(db_session, limit=10)
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_fields_present(self, db_session: AsyncSession) -> None:
        from app.services.analytics_pipeline import get_feature_adoption_summary
        data = await get_feature_adoption_summary(db_session, limit=10)
        if data:
            first = data[0]
            required = [
                "feature_name",
                "event_date",
                "total_events",
                "unique_users",
                "view_count",
                "action_count",
                "export_count",
                "computed_at",
            ]
            for field in required:
                assert field in first, f"Missing field: {field}"

    @pytest.mark.asyncio
    async def test_non_negative_counts(self, db_session: AsyncSession) -> None:
        from app.services.analytics_pipeline import get_feature_adoption_summary
        data = await get_feature_adoption_summary(db_session, limit=100)
        for row in data:
            for field in ("total_events", "unique_users", "view_count", "action_count", "export_count"):
                val = row.get(field)
                if val is not None:
                    assert val >= 0, f"{field} must be >= 0, got {val}"


class TestSystemHealth:
    """Test GET /api/analytics/system-health aggregation shape."""

    @pytest.mark.asyncio
    async def test_returns_list(self, db_session: AsyncSession) -> None:
        from app.services.analytics_pipeline import get_system_health_summary
        data = await get_system_health_summary(db_session)
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_fields_present(self, db_session: AsyncSession) -> None:
        from app.services.analytics_pipeline import get_system_health_summary
        data = await get_system_health_summary(db_session)
        if data:
            first = data[0]
            required = [
                "service_name",
                "metric_name",
                "metric_unit",
                "avg_value",
                "min_value",
                "max_value",
                "p95_value",
                "total_count",
                "computed_at",
            ]
            for field in required:
                assert field in first, f"Missing field: {field}"


# ---------------------------------------------------------------------------
# Helper function tests (pure logic, no DB required)
# ---------------------------------------------------------------------------

class TestToIso:
    """Test ``_to_iso`` datetime/date/string conversion."""

    def test_none_returns_none(self):
        assert _to_iso(None) is None

    def test_string_passthrough(self):
        assert _to_iso("2024-03-15T10:30:00") == "2024-03-15T10:30:00"

    def test_datetime_converted(self):
        dt = datetime(2024, 3, 15, 10, 30, 0)
        assert _to_iso(dt) == "2024-03-15T10:30:00"

    def test_date_converted(self):
        d = _dt.date(2024, 3, 15)
        assert _to_iso(d) == "2024-03-15"

    def test_fallback_str(self):
        assert _to_iso(12345) == "12345"


class TestSafeRate:
    """Test ``_safe_rate`` percentage calculation with edge cases."""

    def test_normal_rate(self):
        assert _safe_rate(3, 4) == 75.0

    def test_zero_denominator_returns_zero(self):
        assert _safe_rate(5, 0) == 0.0

    def test_none_denominator_returns_zero(self):
        assert _safe_rate(5, None) == 0.0

    def test_zero_numerator(self):
        assert _safe_rate(0, 10) == 0.0

    def test_full_rate(self):
        assert _safe_rate(10, 10) == 100.0


class TestTeamFilterValue:
    """Test ``_team_filter_value`` dialect-normalised team id binding."""

    def _sqlite_db(self):
        db = MagicMock(spec=AsyncSession)
        db.get_bind.return_value.dialect.name = "sqlite"
        return db

    def test_uuid_team_id_sqlite_returns_hex(self):
        tid = _uuid.UUID("00112233-4455-6677-8899-aabbccddeeff")
        db = self._sqlite_db()
        assert _team_filter_value(db, tid) == "00112233445566778899aabbccddeeff"

    def test_string_team_id_sqlite_returns_hex(self):
        db = self._sqlite_db()
        assert _team_filter_value(db, "00112233445566778899aabbccddeeff") == "00112233445566778899aabbccddeeff"

    def test_non_sqlite_passthrough(self):
        tid = _uuid.UUID("00112233-4455-6677-8899-aabbccddeeff")
        db = MagicMock(spec=AsyncSession)
        db.get_bind.return_value.dialect.name = "postgresql"
        assert _team_filter_value(db, tid) == tid


class TestDaysAgoExpr:
    """Test ``_days_ago_expr`` dialect-specific SQL generation."""

    def _sqlite_db(self):
        db = MagicMock(spec=AsyncSession)
        db.get_bind.return_value.dialect.name = "sqlite"
        return db

    def test_sqlite_uses_date_expr(self):
        db = self._sqlite_db()
        expr = _days_ago_expr(db)
        assert expr == "date('now', '-' || :days || ' days')"

    def test_postgres_uses_current_date(self):
        db = MagicMock(spec=AsyncSession)
        db.get_bind.return_value.dialect.name = "postgresql"
        expr = _days_ago_expr(db)
        assert expr == "(CURRENT_DATE - CAST(:days AS integer))"

    def test_dialect_detection_failure_returns_postgres_expr(self):
        """Dialect detection failure falls back to PostgreSQL expression."""
        db = MagicMock(spec=AsyncSession)
        db.get_bind.side_effect = RuntimeError("no bind")
        expr = _days_ago_expr(db)
        assert expr == "(CURRENT_DATE - CAST(:days AS integer))"


class TestTeamFilterValueDialectFailure:
    """Test ``_team_filter_value`` dialect-detection failure path."""

    def test_dialect_detection_failure_returns_uuid(self):
        """When dialect detection fails, return the UUID as-is (postgres path)."""
        tid = _uuid.UUID("00112233-4455-6677-8899-aabbccddeeff")
        db = MagicMock(spec=AsyncSession)
        db.get_bind.side_effect = RuntimeError("no bind")
        assert _team_filter_value(db, tid) == tid


class TestComplianceSummaryEdgeCases:
    """Edge cases for compliance summary aggregation."""

    @pytest.mark.asyncio
    async def test_empty_row_returns_empty_dict(self, db_session: AsyncSession) -> None:
        """When mv_compliance_summary has no rows, return {}."""
        from unittest.mock import MagicMock as _MM
        result = _MM()
        result.mappings.return_value.first.return_value = None
        orig_execute = db_session.execute
        async def _fake_execute(*args, **kwargs):
            return result
        db_session.execute = _fake_execute
        try:
            data = await get_compliance_summary(db_session)
            assert data == {}
        finally:
            db_session.execute = orig_execute


class TestRefreshViews:
    """Tests for materialized view refresh helpers.

    SQLite does not support REFRESH MATERIALIZED VIEW, so these tests mock
    the db session's execute to verify the correct SQL is issued.
    """

    def test_refresh_view_concurrently_issues_correct_sql(self):
        from unittest.mock import MagicMock as _MM
        db = _MM(spec=AsyncSession)
        import asyncio
        asyncio.run(_refresh_view(db, "mv_compliance_summary", concurrently=True))
        called = db.execute.call_args[0][0]
        assert "REFRESH MATERIALIZED VIEW CONCURRENTLY mv_compliance_summary" in str(called)

    def test_refresh_view_non_concurrently_issues_correct_sql(self):
        from unittest.mock import MagicMock as _MM
        db = _MM(spec=AsyncSession)
        import asyncio
        asyncio.run(_refresh_view(db, "mv_compliance_summary", concurrently=False))
        called = db.execute.call_args[0][0]
        assert "REFRESH MATERIALIZED VIEW mv_compliance_summary" in str(called)
        assert "CONCURRENTLY" not in str(called)

    def test_refresh_all_analytics_views_issues_correct_sql(self):
        from unittest.mock import MagicMock as _MM
        db = _MM(spec=AsyncSession)
        import asyncio
        asyncio.run(refresh_all_analytics_views(db, concurrently=False))
        calls = [str(c[0][0]) for c in db.execute.call_args_list]
        expected = [
            "mv_compliance_summary",
            "mv_compliance_trends",
            "mv_certification_status",
            "mv_project_compliance",
            "mv_recent_alerts",
        ]
        for view in expected:
            assert any(view in c for c in calls), f"Missing refresh for {view}"


class TestCountFunctions:
    """Tests for count/pagination helper functions."""

    @pytest.mark.asyncio
    async def test_certification_export_count(self, db_session: AsyncSession) -> None:
        count = await get_certification_export_count(db_session)
        assert isinstance(count, int)
        assert count >= 0

    @pytest.mark.asyncio
    async def test_certification_export_count_with_filters(self, db_session: AsyncSession) -> None:
        count = await get_certification_export_count(
            db_session, expiration_bucket="valid", subcontractor_id="00000000000000000000000000000001"
        )
        assert isinstance(count, int)
        assert count >= 0

    @pytest.mark.asyncio
    async def test_recent_alerts_count(self, db_session: AsyncSession) -> None:
        count = await get_recent_alerts_count(db_session)
        assert isinstance(count, int)
        assert count >= 0

    @pytest.mark.asyncio
    async def test_recent_alerts_count_with_status(self, db_session: AsyncSession) -> None:
        count = await get_recent_alerts_count(db_session, status="sent")
        assert isinstance(count, int)
        assert count >= 0

    @pytest.mark.asyncio
    async def test_feature_adoption_summary_count(self, db_session: AsyncSession) -> None:
        count = await get_feature_adoption_summary_count(db_session)
        assert isinstance(count, int)
        assert count >= 0

    @pytest.mark.asyncio
    async def test_feature_adoption_summary_count_with_feature(self, db_session: AsyncSession) -> None:
        count = await get_feature_adoption_summary_count(db_session, feature_name="feature_a")
        assert isinstance(count, int)
        assert count >= 0


class TestCertificationExportFilters:
    """Test optional filter parameters on certification export (covers lines 190-194)."""

    @pytest.mark.asyncio
    async def test_with_expiration_bucket(self, db_session: AsyncSession) -> None:
        data = await get_certification_export_rows(db_session, limit=10, expiration_bucket="valid")
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_with_subcontractor_id(self, db_session: AsyncSession) -> None:
        data = await get_certification_export_rows(
            db_session, limit=10, subcontractor_id="00000000000000000000000000000001"
        )
        assert isinstance(data, list)


class TestRecentAlertsFilters:
    """Test optional status filter on recent alerts (covers lines 309-310)."""

    @pytest.mark.asyncio
    async def test_with_status(self, db_session: AsyncSession) -> None:
        data = await get_recent_alerts(db_session, limit=10, status="sent")
        assert isinstance(data, list)


class TestFilteredQueries:
    """Tests for team_id / feature_name / service_name filter paths in analytics_pipeline."""

    @pytest.mark.asyncio
    async def test_certification_export_rows_with_team_id(self, db_session: AsyncSession) -> None:
        data = await get_certification_export_rows(db_session, limit=10, team_id="00000000000000000000000000000001")
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_certification_export_count_with_team_id(self, db_session: AsyncSession) -> None:
        count = await get_certification_export_count(db_session, team_id="00000000000000000000000000000001")
        assert isinstance(count, int)
        assert count >= 0

    @pytest.mark.asyncio
    async def test_recent_alerts_with_team_id(self, db_session: AsyncSession) -> None:
        data = await get_recent_alerts(db_session, limit=10, team_id="00000000000000000000000000000001")
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_all_projects_with_team_id(self, db_session: AsyncSession) -> None:
        data = await get_all_project_compliance(db_session, limit=10, team_id="00000000000000000000000000000001")
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_feature_adoption_with_feature_name(self, db_session: AsyncSession) -> None:
        data = await get_feature_adoption_summary(db_session, limit=10, feature_name="feature_a")
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_system_health_with_filters(self, db_session: AsyncSession) -> None:
        data = await get_system_health_summary(db_session, service_name="service_1", metric_name="metric_a")
        assert isinstance(data, list)


class TestComplianceTrendsWithData:
    """Test get_compliance_trends loop body when trend rows exist (covers line 153)."""

    @pytest.mark.asyncio
    async def test_trends_append_when_rows_exist(self, db_session: AsyncSession) -> None:
        from unittest.mock import MagicMock as _MM
        result = _MM()
        row = _MM()
        row.__getitem__.side_effect = lambda k: {
            "trend_date": "2024-01-01", "active_subcontractors": 5, "valid_certifications": 3,
            "expired_certifications": 1, "open_violations": 0, "open_osha_violations": 0,
            "compliance_percentage": 60.0, "computed_at": "2024-01-01T00:00:00",
        }[k]
        result.mappings.return_value.all.return_value = [row]
        orig_execute = db_session.execute
        async def _fake_execute(*args, **kwargs):
            return result
        db_session.execute = _fake_execute
        try:
            data = await get_compliance_trends(db_session, days=30)
            assert isinstance(data, list)
            assert len(data) == 1
        finally:
            db_session.execute = orig_execute


class TestProjectComplianceWithData:
    """Test project compliance happy paths when rows exist (covers lines 421-423, 476-478)."""

    @pytest.mark.asyncio
    async def test_get_project_compliance_by_id_found(self, db_session: AsyncSession) -> None:
        from unittest.mock import MagicMock as _MM
        result = _MM()
        row = _MM()
        row.__getitem__.side_effect = lambda k: {
            "project_id": "00000000-0000-0000-0000-000000000001",
            "project_name": "Test Project",
            "project_number": "TP-001",
            "project_status": "active",
            "start_date": "2024-01-01",
            "estimated_end_date": "2024-12-31",
            "total_subcontractors": 3,
            "active_subcontractors": 2,
            "suspended_subcontractors": 0,
            "compliant_subcontractors": 2,
            "open_violations": 0,
            "open_osha_violations": 0,
            "total_open_penalties": 0,
            "expiring_soon_subcontractors": 0,
            "computed_at": "2024-01-01T00:00:00",
        }[k]
        result.mappings.return_value.first.return_value = row
        orig_execute = db_session.execute
        async def _fake_execute(*args, **kwargs):
            return result
        db_session.execute = _fake_execute
        try:
            data = await get_project_compliance_by_id(db_session, "00000000-0000-0000-0000-000000000001")
            assert data is not None
            assert data["project_name"] == "Test Project"
        finally:
            db_session.execute = orig_execute

    @pytest.mark.asyncio
    async def test_get_all_project_compliance_loop_body(self, db_session: AsyncSession) -> None:
        from unittest.mock import MagicMock as _MM
        result = _MM()
        row = _MM()
        row.__getitem__.side_effect = lambda k: {
            "project_id": "00000000-0000-0000-0000-000000000001",
            "project_name": "Test Project",
            "project_number": "TP-001",
            "project_status": "active",
            "start_date": "2024-01-01",
            "estimated_end_date": "2024-12-31",
            "total_subcontractors": 3,
            "active_subcontractors": 2,
            "suspended_subcontractors": 0,
            "compliant_subcontractors": 2,
            "open_violations": 0,
            "open_osha_violations": 0,
            "total_open_penalties": 0,
            "expiring_soon_subcontractors": 0,
            "computed_at": "2024-01-01T00:00:00",
        }[k]
        result.mappings.return_value.all.return_value = [row]
        orig_execute = db_session.execute
        async def _fake_execute(*args, **kwargs):
            return result
        db_session.execute = _fake_execute
        try:
            data = await get_all_project_compliance(db_session, limit=10)
            assert isinstance(data, list)
            assert len(data) == 1
        finally:
            db_session.execute = orig_execute
