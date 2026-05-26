"""Integration tests for the analytics router (analytics materialized view endpoints).

Validates that the analytics endpoints defined in analytics.py:
- Return the expected response shapes
- Handle edge cases gracefully (empty DB, navigation, etc.)
- Validate query parameters

Owner: Data Engineer
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.compliance import TokenData
from app.routers.auth import get_current_user
from app.services.analytics_pipeline import (
    get_compliance_summary,
    get_compliance_trends,
    get_recent_alerts,
)

# Import the FastAPI app instance to override auth dependency
from api.main import app as fastapi_app


def _mock_current_user():
    return TokenData(sub="test@example.com", user_id="test-user-id", role="admin")


@pytest_asyncio.fixture(autouse=True)
async def override_auth():
    fastapi_app.dependency_overrides[get_current_user] = _mock_current_user
    yield
    fastapi_app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
class TestAnalyticsRouter:
    """Test analytics router endpoints via async HTTP client."""

    async def test_compliance_summary_endpoint_shape(self, async_client: AsyncClient) -> None:
        """GET /api/analytics/compliance/summary should return the expected keys."""
        response = await async_client.get("/api/analytics/compliance/summary")
        assert response.status_code == 200
        data = response.json()
        required_keys = [
            "total_subcontractors",
            "active_subcontractors",
            "compliant_subcontractors",
            "compliance_rate",
            "expiring_soon_30d",
            "open_violations",
            "valid_certifications",
            "expired_certifications",
            "pending_verification_certs",
            "computed_at",
        ]
        for key in required_keys:
            assert key in data, f"Missing key: {key}"

    async def test_compliance_summary_counts_non_negative(self, async_client: AsyncClient) -> None:
        response = await async_client.get("/api/analytics/compliance/summary")
        assert response.status_code == 200
        data = response.json()
        count_keys = [
            "total_subcontractors",
            "active_subcontractors",
            "suspended_subcontractors",
            "blacklisted_subcontractors",
            "compliant_subcontractors",
            "expiring_soon_30d",
            "expiring_soon_60d",
            "open_violations",
            "open_osha_violations",
            "valid_certifications",
            "expired_certifications",
            "pending_verification_certs",
        ]
        for key in count_keys:
            assert data[key] >= 0, f"{key} must be >= 0, got {data[key]}"

    async def test_compliance_rate_range(self, async_client: AsyncClient) -> None:
        response = await async_client.get("/api/analytics/compliance/summary")
        assert response.status_code == 200
        data = response.json()
        rate = data.get("compliance_rate")
        assert 0.0 <= rate <= 100.0, f"compliance_rate out of range: {rate}"

    async def test_trends_endpoint_default_days(self, async_client: AsyncClient) -> None:
        """GET /api/analytics/compliance/trends returns list, default 30 days."""
        response = await async_client.get("/api/analytics/compliance/trends")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    async def test_trends_endpoint_90_days(self, async_client: AsyncClient) -> None:
        response = await async_client.get("/api/analytics/compliance/trends?days=90")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    async def test_trends_endpoint_invalid_days_negative(self, async_client: AsyncClient) -> None:
        response = await async_client.get("/api/analytics/compliance/trends?days=-1")
        assert response.status_code == 422

    async def test_trends_endpoint_invalid_days_zero(self, async_client: AsyncClient) -> None:
        response = await async_client.get("/api/analytics/compliance/trends?days=0")
        assert response.status_code == 422

    async def test_trends_returns_iso_dates(self, async_client: AsyncClient) -> None:
        response = await async_client.get("/api/analytics/compliance/trends?days=30")
        assert response.status_code == 200
        data = response.json()
        if data:
            assert "date" in data[0]
            assert "compliance_percentage" in data[0]
            assert "computed_at" in data[0]

    async def test_alerts_recent_returns_list(self, async_client: AsyncClient) -> None:
        """GET /api/analytics/alerts/recent returns a list."""
        response = await async_client.get("/api/analytics/alerts/recent")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    async def test_alerts_recent_with_status_filter(self, async_client: AsyncClient) -> None:
        for status_val in ["pending", "sent", "failed"]:
            response = await async_client.get(f"/api/analytics/alerts/recent?status={status_val}")
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)

    async def test_projects_endpoint_returns_list(self, async_client: AsyncClient) -> None:
        """GET /api/analytics/projects returns a list of project compliance summaries."""
        response = await async_client.get("/api/analytics/projects")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    async def test_projects_endpoint_pagination(self, async_client: AsyncClient) -> None:
        response = await async_client.get("/api/analytics/projects?limit=1&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) <= 1

    async def test_projects_compliance_rate_range(self, async_client: AsyncClient) -> None:
        response = await async_client.get("/api/analytics/projects")
        assert response.status_code == 200
        data = response.json()
        for project in data:
            rate = project.get("compliance_rate")
            assert 0.0 <= rate <= 100.0, f"compliance_rate out of range: {rate}"

    async def test_export_csv_format(self, async_client: AsyncClient) -> None:
        """GET /api/analytics/compliance/export?format=csv returns a CSV stream."""
        response = await async_client.get("/api/analytics/compliance/export?format=csv")
        assert response.status_code == 200
        # FastAPI StreamingResponse may not include charset in content-type header
        assert response.headers["content-type"].startswith("text/csv")
        content = response.text
        assert "subcontractor_id" in content

    async def test_export_json_format(self, async_client: AsyncClient) -> None:
        """GET /api/analytics/compliance/export?format=json returns a JSON list."""
        response = await async_client.get("/api/analytics/compliance/export?format=json")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        data = response.json()
        assert isinstance(data, list)

    async def test_export_invalid_format(self, async_client: AsyncClient) -> None:
        response = await async_client.get("/api/analytics/compliance/export?format=xml")
        assert response.status_code == 422