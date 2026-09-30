"""Tests for the resilience layer (retry-with-backoff + circuit breaker)
and its integration with the critical API clients."""

import asyncio
import sys
import os
import time
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.osha_client import OSHAClient, OSHAClientError
from app.services.resilience import (
    AsyncCircuitBreaker,
    CircuitOpenError,
    CircuitState,
    RetryableHTTPError,
    async_retry_call,
    resilient_call,
    retry_with_backoff,
)
from app.services.state_credential_client import StateCredentialClient, StateCredentialClientError


class TransientError(ConnectionError):
    pass


def make_half_open(breaker: AsyncCircuitBreaker) -> None:
    """Force a breaker into HALF_OPEN by backdating its last failure."""
    breaker._state = CircuitState.OPEN
    breaker._last_failure_time = time.monotonic() - breaker.recovery_timeout - 1.0


def make_sequential_session(responses):
    """Fake aiohttp session whose GET returns each response in order."""

    class FakeCtx:
        def __init__(self, response):
            self.response = response

        async def __aenter__(self):
            return self.response

        async def __aexit__(self, exc_type, exc, tb):
            return None

    class FakeSession:
        def __init__(self):
            self.responses = list(responses)
            self.calls = 0
            self.closed = False

        def get(self, *args, **kwargs):
            idx = min(self.calls, len(self.responses) - 1)
            self.calls += 1
            return FakeCtx(self.responses[idx])

        async def close(self):
            self.closed = True

    return FakeSession()


def make_response(status, body='{"results": [], "count": 0}', parsed=None):
    response = AsyncMock()
    response.status = status
    response.text.return_value = body
    response.json.return_value = parsed if parsed is not None else {"results": [], "count": 0}
    return response


# ---------------------------------------------------------------------------
# AsyncCircuitBreaker
# ---------------------------------------------------------------------------


class TestAsyncCircuitBreaker:
    def test_breaker_starts_closed(self):
        breaker = AsyncCircuitBreaker(name="test")
        assert breaker.state == CircuitState.CLOSED

    def test_breaker_invalid_threshold(self):
        with pytest.raises(ValueError):
            AsyncCircuitBreaker(failure_threshold=0)

    @pytest.mark.asyncio
    async def test_breaker_opens_after_threshold(self):
        breaker = AsyncCircuitBreaker(failure_threshold=3, name="test")
        for _ in range(3):
            await breaker.record_failure()
        assert breaker.state == CircuitState.OPEN
        with pytest.raises(CircuitOpenError):
            await breaker.allow_call()

    @pytest.mark.asyncio
    async def test_breaker_success_resets_count(self):
        breaker = AsyncCircuitBreaker(failure_threshold=3, name="test")
        await breaker.record_failure()
        await breaker.record_failure()
        await breaker.record_success()
        await breaker.record_failure()
        await breaker.record_failure()
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_breaker_half_open_after_cooldown(self):
        breaker = AsyncCircuitBreaker(failure_threshold=1, recovery_timeout=30.0, name="test")
        await breaker.record_failure()
        assert breaker.state == CircuitState.OPEN
        make_half_open(breaker)
        assert breaker.state == CircuitState.HALF_OPEN
        await breaker.allow_call()
        assert breaker.state == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_breaker_trial_success_closes(self):
        breaker = AsyncCircuitBreaker(failure_threshold=1, recovery_timeout=30.0, name="test")
        await breaker.record_failure()
        make_half_open(breaker)
        await breaker.record_success()
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_breaker_trial_failure_reopens(self):
        breaker = AsyncCircuitBreaker(failure_threshold=1, recovery_timeout=30.0, name="test")
        await breaker.record_failure()
        make_half_open(breaker)
        assert breaker.state == CircuitState.HALF_OPEN
        await breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_breaker_call_executes_and_records(self):
        breaker = AsyncCircuitBreaker(name="test")
        coro = AsyncMock(return_value=7)
        result = await breaker.call(coro)
        assert result == 7
        coro.assert_awaited_once()
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_breaker_call_records_failure(self):
        breaker = AsyncCircuitBreaker(failure_threshold=1, name="test")
        coro = AsyncMock(side_effect=TransientError("boom"))
        with pytest.raises(TransientError):
            await breaker.call(coro)
        assert breaker.state == CircuitState.OPEN


# ---------------------------------------------------------------------------
# async_retry_call / retry_with_backoff / resilient_call
# ---------------------------------------------------------------------------


class TestAsyncRetryCall:
    @pytest.mark.asyncio
    async def test_succeeds_first_try(self):
        coro = AsyncMock(return_value=42)
        result = await async_retry_call(coro)
        assert result == 42
        coro.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_retries_then_succeeds(self):
        coro = AsyncMock(side_effect=[TransientError("boom"), 99])
        with patch("app.services.resilience.asyncio.sleep", new_callable=AsyncMock):
            result = await async_retry_call(coro, max_retries=3, base_delay=0.01, max_delay=0.1)
        assert result == 99
        assert coro.await_count == 2

    @pytest.mark.asyncio
    async def test_exhausts_retries(self):
        coro = AsyncMock(side_effect=TransientError("boom"))
        with patch("app.services.resilience.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(TransientError):
                await async_retry_call(coro, max_retries=2, base_delay=0.01, max_delay=0.1)
        assert coro.await_count == 3  # initial + 2 retries

    @pytest.mark.asyncio
    async def test_non_retryable_raises_immediately(self):
        coro = AsyncMock(side_effect=ValueError("bad data"))
        with pytest.raises(ValueError):
            await async_retry_call(coro, max_retries=3)
        coro.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_negative_max_retries_rejected(self):
        with pytest.raises(ValueError):
            await async_retry_call(AsyncMock(), max_retries=-1)

    def test_backoff_delay_bounds(self):
        from app.services.resilience import _backoff_delay

        for attempt in range(6):
            delay = _backoff_delay(
                attempt, base_delay=0.5, max_delay=8.0, jitter=True
            )
            expected_cap = min(8.0, 0.5 * (2**attempt))
            assert expected_cap / 2 <= delay <= expected_cap

    def test_backoff_delay_no_jitter(self):
        from app.services.resilience import _backoff_delay

        assert _backoff_delay(0, base_delay=0.5, max_delay=8.0, jitter=False) == 0.5
        assert _backoff_delay(3, base_delay=0.5, max_delay=8.0, jitter=False) == 4.0
        assert _backoff_delay(10, base_delay=0.5, max_delay=8.0, jitter=False) == 8.0


class TestRetryWithBackoffDecorator:
    @pytest.mark.asyncio
    async def test_decorator_retries(self):
        calls = {"count": 0}

        @retry_with_backoff(max_retries=2, base_delay=0.01, max_delay=0.1)
        async def flaky():
            if calls["count"] == 0:
                calls["count"] += 1
                raise TransientError("fail")
            return "ok"

        with patch("app.services.resilience.asyncio.sleep", new_callable=AsyncMock):
            result = await flaky()
        assert result == "ok"
        assert calls["count"] == 1

    @pytest.mark.asyncio
    async def test_decorator_preserves_name(self):
        @retry_with_backoff(max_retries=1)
        async def my_fetch():
            return None

        assert my_fetch.__name__ == "my_fetch"


class TestResilientCall:
    @pytest.mark.asyncio
    async def test_success_records_success(self):
        breaker = AsyncCircuitBreaker(name="test")
        coro = AsyncMock(return_value="ok")
        result = await resilient_call(coro, breaker=breaker)
        assert result == "ok"
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_failure_records_failure(self):
        breaker = AsyncCircuitBreaker(failure_threshold=1, name="test")
        coro = AsyncMock(side_effect=ValueError("nope"))
        with pytest.raises(ValueError):
            await resilient_call(coro, breaker=breaker)
        assert breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_no_breaker_still_retries(self):
        coro = AsyncMock(side_effect=[TransientError("boom"), "ok"])
        with patch("app.services.resilience.asyncio.sleep", new_callable=AsyncMock):
            result = await resilient_call(coro, max_retries=1, base_delay=0.01)
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_retry_exhaustion_counts_single_failure(self):
        breaker = AsyncCircuitBreaker(failure_threshold=2, name="test")
        coro = AsyncMock(side_effect=TransientError("boom"))
        with patch("app.services.resilience.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(TransientError):
                await resilient_call(coro, breaker=breaker, max_retries=2, base_delay=0.01)
        assert coro.await_count == 3
        assert breaker.state == CircuitState.CLOSED  # 1 failure < threshold 2

    @pytest.mark.asyncio
    async def test_open_circuit_fails_fast_without_calls(self):
        breaker = AsyncCircuitBreaker(failure_threshold=1, recovery_timeout=60.0, name="test")
        await breaker.record_failure()
        coro = AsyncMock()
        with pytest.raises(CircuitOpenError):
            await resilient_call(coro, breaker=breaker)
        coro.assert_not_awaited()


# ---------------------------------------------------------------------------
# Client integration
# ---------------------------------------------------------------------------


class TestOSHAClientResilience:
    @pytest.mark.asyncio
    async def test_retries_on_500_then_succeeds(self):
        client = OSHAClient()
        client._session = make_sequential_session(
            [make_response(500, "server error"), make_response(200)]
        )
        with patch("app.services.resilience.asyncio.sleep", new_callable=AsyncMock):
            data = await client.search_cases(search="acme")
        assert isinstance(data, dict)
        assert client._session.calls == 2
        assert client._breaker.state == CircuitState.CLOSED
        await client.close()

    @pytest.mark.asyncio
    async def test_retries_on_429_then_succeeds(self):
        client = OSHAClient()
        client._session = make_sequential_session(
            [make_response(429, "rate limited"), make_response(200)]
        )
        with patch("app.services.resilience.asyncio.sleep", new_callable=AsyncMock):
            data = await client.search_cases()
        assert isinstance(data, dict)
        assert client._session.calls == 2
        await client.close()

    @pytest.mark.asyncio
    async def test_client_error_no_retry(self):
        client = OSHAClient()
        client._session = make_sequential_session([make_response(404, "not found")])
        with pytest.raises(OSHAClientError):
            await client.search_cases()
        assert client._session.calls == 1  # no retry on 4xx
        await client.close()

    @pytest.mark.asyncio
    async def test_circuit_opens_after_persistent_failures(self):
        client = OSHAClient()
        client._breaker = AsyncCircuitBreaker(failure_threshold=2, recovery_timeout=60.0, name="osha-test")
        client._session = make_sequential_session([make_response(500, "server error")])
        with patch("app.services.resilience.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(RetryableHTTPError):
                await client.search_cases()
            with pytest.raises(RetryableHTTPError):
                await client.search_cases()
            # Circuit should now be open; next call fails fast
            assert client._breaker.state == CircuitState.OPEN
            with pytest.raises(CircuitOpenError):
                await client.search_cases()
        # Only 8 HTTP attempts total (4 per failed call, none for the open circuit)
        assert client._session.calls == 8
        await client.close()


class TestStateCredentialClientResilience:
    @pytest.mark.asyncio
    async def test_retries_on_503_then_succeeds(self):
        client = StateCredentialClient(state_code="ZZ", base_url="https://api.example.com")
        client._session = make_sequential_session(
            [
                make_response(503, "unavailable"),
                make_response(200, '{"results": [{"id": 1}], "count": 1}', parsed={"results": [{"id": 1}], "count": 1}),
            ]
        )
        with patch("app.services.resilience.asyncio.sleep", new_callable=AsyncMock):
            result = await client.fetch_credentials(query="electrician")
        assert result["count"] == 1
        assert client._session.calls == 2
        assert client._breaker.state == CircuitState.CLOSED
        await client.close()

    @pytest.mark.asyncio
    async def test_non_retryable_404_no_retry(self):
        client = StateCredentialClient(state_code="ZZ", base_url="https://api.example.com")
        client._session = make_sequential_session([make_response(404, "not found")])
        with pytest.raises(StateCredentialClientError):
            await client.fetch_credentials(query="builder")
        assert client._session.calls == 1
        await client.close()

    @pytest.mark.asyncio
    async def test_circuit_opens_after_persistent_failures(self):
        client = StateCredentialClient(state_code="ZZ", base_url="https://api.example.com")
        client._breaker = AsyncCircuitBreaker(failure_threshold=2, recovery_timeout=60.0, name="state-test")
        client._session = make_sequential_session([make_response(500, "server error")])
        with patch("app.services.resilience.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(RetryableHTTPError):
                await client.fetch_credentials(query="a")
            with pytest.raises(RetryableHTTPError):
                await client.fetch_credentials(query="b")
            assert client._breaker.state == CircuitState.OPEN
            with pytest.raises(CircuitOpenError):
                await client.fetch_credentials(query="c")
        assert client._session.calls == 8
        await client.close()
