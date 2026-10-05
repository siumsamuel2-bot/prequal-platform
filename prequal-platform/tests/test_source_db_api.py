"""Tests for the source-DB connector backend API and resilience primitives.

Covers:
- Retry policy validation and backoff calculation
- Error classification (retryable vs permanent)
- Circuit breaker transitions
- SourceDBConnector query/execute/test-connection behaviour
- The FastAPI router endpoints exposed under ``/api/source-db``
"""

from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.services.source_db_connector import (
    CircuitBreaker,
    CircuitBreakerState,
    CircuitOpenError,
    ConnectorMetrics,
    RetryConfig,
    SourceDBConnector,
    calculate_backoff,
    classify_error,
    is_retryable_error,
)

from app.schemas.compliance import TokenData
from app.routers.auth import get_current_user, require_admin
from api.main import app as fastapi_app


def _mock_admin():
    return TokenData(sub="admin@example.com", user_id="admin-id", role="admin")


@pytest_asyncio.fixture(autouse=True)
async def override_auth():
    fastapi_app.dependency_overrides[get_current_user] = _mock_admin
    fastapi_app.dependency_overrides[require_admin] = _mock_admin
    yield
    fastapi_app.dependency_overrides.pop(get_current_user, None)
    fastapi_app.dependency_overrides.pop(require_admin, None)


def _coded(code: str) -> Exception:
    exc = Exception(f"driver error {code}")
    exc.code = code  # type: ignore[attr-defined]
    return exc


# ---------------------------------------------------------------------------
# Retry configuration & backoff
# ---------------------------------------------------------------------------


class TestRetryConfig:
    def test_defaults_are_valid(self) -> None:
        config = RetryConfig()
        assert config.max_retries > 0
        assert config.base_delay > 0
        assert config.max_delay >= config.base_delay

    def test_rejects_non_positive_max_retries(self) -> None:
        with pytest.raises(ValueError):
            RetryConfig(max_retries=0)

    def test_rejects_non_positive_base_delay(self) -> None:
        with pytest.raises(ValueError):
            RetryConfig(base_delay=0)

    def test_rejects_max_delay_below_base_delay(self) -> None:
        with pytest.raises(ValueError):
            RetryConfig(base_delay=10.0, max_delay=1.0)

    def test_to_dict_round_trips(self) -> None:
        config = RetryConfig(max_retries=4, base_delay=0.5)
        data = config.to_dict()
        assert data["max_retries"] == 4
        assert data["base_delay"] == 0.5


class TestCalculateBackoff:
    def test_first_retry_is_near_base_delay(self) -> None:
        config = RetryConfig(base_delay=1.0, max_delay=30.0, jitter_factor=0.1)
        for _ in range(20):
            delay = calculate_backoff(0, config)
            assert 0.9 <= delay <= 1.1

    def test_exponential_growth(self) -> None:
        config = RetryConfig(base_delay=1.0, max_delay=30.0, jitter_factor=0.1)
        second = calculate_backoff(1, config)
        assert 1.8 <= second <= 2.2

    def test_caps_at_max_delay(self) -> None:
        config = RetryConfig(base_delay=1.0, max_delay=5.0, jitter_factor=0.1)
        for _ in range(20):
            assert calculate_backoff(10, config) <= 5.5

    def test_zero_jitter_is_deterministic(self) -> None:
        config = RetryConfig(base_delay=2.0, max_delay=30.0, jitter_factor=0.0)
        assert calculate_backoff(2, config) == 8.0


# ---------------------------------------------------------------------------
# Error classification
# ---------------------------------------------------------------------------


class TestErrorClassification:
    @pytest.mark.parametrize(
        "code",
        ["ECONNREFUSED", "ETIMEDOUT", "ENOTFOUND", "57P01", "57P02", "57P03"],
    )
    def test_retryable_codes(self, code: str) -> None:
        assert is_retryable_error(_coded(code)) is True

    @pytest.mark.parametrize("code", ["42601", "28P01", "23505"])
    def test_non_retryable_codes(self, code: str) -> None:
        assert is_retryable_error(_coded(code)) is False

    def test_unknown_error_is_not_retryable(self) -> None:
        assert is_retryable_error(ValueError("bad data")) is False

    def test_classify_network_error(self) -> None:
        classification = classify_error(_coded("ECONNREFUSED"))
        assert classification == {
            "retryable": True,
            "category": "TRANSIENT_NETWORK",
            "code": "ECONNREFUSED",
            "recommendedAction": "RETRY_WITH_BACKOFF",
        }

    def test_classify_permanent_error(self) -> None:
        classification = classify_error(_coded("42601"))
        assert classification["retryable"] is False
        assert classification["recommendedAction"] == "FAIL_FAST"


# ---------------------------------------------------------------------------
# Circuit breaker & metrics
# ---------------------------------------------------------------------------


class TestCircuitBreaker:
    def test_opens_after_threshold(self) -> None:
        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=60.0)
        breaker.record_failure()
        assert breaker.is_open() is False
        breaker.record_failure()
        assert breaker.is_open() is True
        assert breaker.state is CircuitBreakerState.OPEN

    def test_success_closes_breaker(self) -> None:
        breaker = CircuitBreaker(failure_threshold=1)
        breaker.record_failure()
        assert breaker.is_open() is True
        breaker.record_success()
        assert breaker.is_open() is False

    def test_transitions_to_half_open_after_timeout(self) -> None:
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=0.0)
        breaker.record_failure()
        assert breaker.state is CircuitBreakerState.HALF_OPEN


class TestConnectorMetrics:
    def test_snapshot_reports_success_rate(self) -> None:
        metrics = ConnectorMetrics()
        metrics.record_attempt()
        metrics.record_success(10.0)
        metrics.record_attempt()
        metrics.record_failure(RuntimeError("boom"))
        snapshot = metrics.snapshot()
        assert snapshot["attempts"] == 2
        assert snapshot["successes"] == 1
        assert snapshot["failures"] == 1
        assert snapshot["success_rate"] == 50.0
        assert snapshot["avg_latency_ms"] == 10.0

    def test_reset_clears_counters(self) -> None:
        metrics = ConnectorMetrics()
        metrics.record_attempt()
        metrics.reset()
        assert metrics.snapshot()["attempts"] == 0


# ---------------------------------------------------------------------------
# Connector behaviour
# ---------------------------------------------------------------------------


class TestSourceDBConnector:
    @pytest.mark.asyncio
    async def test_query_and_execute(self, db_engine) -> None:
        connector = SourceDBConnector(
            engine=db_engine,
            retry=RetryConfig(max_retries=1, base_delay=0.01, max_delay=0.02),
        )
        result = await connector.query("SELECT 1 AS value")
        assert result.row_count == 1
        assert result.rows[0]["value"] == 1

        await connector.execute("CREATE TABLE IF NOT EXISTS sdb_probe (id INTEGER)")
        await connector.execute("INSERT INTO sdb_probe (id) VALUES (:id)", {"id": 7})
        rows = await connector.query("SELECT id FROM sdb_probe")
        assert any(row["id"] == 7 for row in rows.rows)

    @pytest.mark.asyncio
    async def test_connect_and_disconnect(self, db_engine) -> None:
        connector = SourceDBConnector(
            engine=db_engine,
            retry=RetryConfig(max_retries=1, base_delay=0.01, max_delay=0.02),
        )
        assert await connector.is_connected() is False
        assert await connector.connect() is True
        assert await connector.is_connected() is True
        await connector.disconnect()
        assert await connector.is_connected() is False

    @pytest.mark.asyncio
    async def test_test_connection_reports_healthy(self, db_engine) -> None:
        connector = SourceDBConnector(
            engine=db_engine,
            retry=RetryConfig(max_retries=1, base_delay=0.01, max_delay=0.02),
        )
        report = await connector.test_connection()
        assert report["connected"] is True
        assert report["latency_ms"] >= 0
        assert report["circuit_breaker"]["state"] == "CLOSED"

    @pytest.mark.asyncio
    async def test_retries_transient_failure(self, db_engine) -> None:
        connector = SourceDBConnector(
            engine=db_engine,
            retry=RetryConfig(max_retries=2, base_delay=0.01, max_delay=0.02),
        )
        calls = {"n": 0}

        async def flaky():
            calls["n"] += 1
            if calls["n"] == 1:
                raise _coded("ECONNREFUSED")
            return connector._materialize(_FakeResult())

        with patch("app.services.source_db_connector.asyncio.sleep", new_callable=AsyncMock):
            result = await connector._run_with_retry(flaky)
        assert result.row_count == 1
        assert connector.metrics.retries == 1

    @pytest.mark.asyncio
    async def test_open_circuit_rejects_call(self, db_engine) -> None:
        breaker = CircuitBreaker(failure_threshold=1)
        breaker.record_failure()
        connector = SourceDBConnector(engine=db_engine, circuit_breaker=breaker)
        with pytest.raises(CircuitOpenError):
            await connector.query("SELECT 1")


class _FakeResult:
    returns_rows = True
    rowcount = 1

    def fetchall(self):
        class _Row:
            _mapping = {"value": 1}

        return [_Row()]


# ---------------------------------------------------------------------------
# Router endpoints
# ---------------------------------------------------------------------------


class TestSourceDBRouter:
    @pytest.mark.asyncio
    async def test_health_endpoint(self, async_client: AsyncClient) -> None:
        response = await async_client.get("/api/source-db/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ("healthy", "unhealthy")
        assert data["component"] == "source-db-connector"
        assert "retry_config" in data

    @pytest.mark.asyncio
    async def test_retry_config_endpoint(self, async_client: AsyncClient) -> None:
        response = await async_client.get("/api/source-db/retry-config")
        assert response.status_code == 200
        data = response.json()
        assert data["max_retries"] >= 1
        assert "ECONNREFUSED" in data["retryable_error_codes"]
        assert "42601" in data["non_retryable_error_codes"]

    @pytest.mark.asyncio
    async def test_metrics_endpoint(self, async_client: AsyncClient) -> None:
        response = await async_client.get("/api/source-db/metrics")
        assert response.status_code == 200
        assert "success_rate" in response.json()

    @pytest.mark.asyncio
    async def test_circuit_breaker_endpoint(self, async_client: AsyncClient) -> None:
        response = await async_client.get("/api/source-db/circuit-breaker")
        assert response.status_code == 200
        assert response.json()["state"] in ("CLOSED", "OPEN", "HALF_OPEN")

    @pytest.mark.asyncio
    async def test_test_connection_endpoint(self, async_client: AsyncClient) -> None:
        response = await async_client.post("/api/source-db/test-connection")
        assert response.status_code == 200
        assert "connected" in response.json()

    @pytest.mark.asyncio
    async def test_query_endpoint_select(self, async_client: AsyncClient) -> None:
        response = await async_client.post(
            "/api/source-db/query", json={"sql": "SELECT 1 AS value"}
        )
        assert response.status_code == 200
        assert response.json()["row_count"] == 1

    @pytest.mark.asyncio
    async def test_query_endpoint_rejects_writes(self, async_client: AsyncClient) -> None:
        response = await async_client.post(
            "/api/source-db/query", json={"sql": "DELETE FROM subcontractors"}
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_query_endpoint_rejects_stacked_statements(
        self, async_client: AsyncClient
    ) -> None:
        response = await async_client.post(
            "/api/source-db/query", json={"sql": "SELECT 1; DROP TABLE subcontractors"}
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_query_endpoint_requires_sql(self, async_client: AsyncClient) -> None:
        response = await async_client.post("/api/source-db/query", json={})
        assert response.status_code == 422
