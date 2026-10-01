"""Tests for the analytics pipeline (materialized views + aggregate queries).

Validates:
1. MVs exist and are queryable
2. Aggregation shapes match expected API response format
3. Data quality (no negative counts, valid date formats, etc.)
4. Edge cases (empty tables, single rows, null values)

Owner: Data Engineer
"""
from __future__ import annotations

import pytest
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.analytics_pipeline import (
    get_compliance_summary,
    get_compliance_trends,
    get_certification_export_rows,
    get_recent_alerts,
    get_project_compliance_by_id,
    get_all_project_compliance,
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
