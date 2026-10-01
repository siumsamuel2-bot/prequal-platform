"""Tests for the source-DB connector retry logic."""

from unittest.mock import AsyncMock, patch

import pytest

from app.services.source_db_connector import async_retry, retry_async


class FakeConnectionError(ConnectionError):
    pass


@pytest.mark.asyncio
async def test_async_retry_succeeds_on_first_try():
    coro = AsyncMock(return_value=42)
    result = await async_retry(coro)
    assert result == 42
    coro.assert_awaited_once()


@pytest.mark.asyncio
async def test_async_retry_retries_then_succeeds():
    coro = AsyncMock(side_effect=[FakeConnectionError("boom"), 99])
    with patch("app.services.source_db_connector.asyncio.sleep", new_callable=AsyncMock):
        result = await async_retry(coro, max_retries=3, base_delay=0.1, max_delay=1.0)
    assert result == 99
    assert coro.await_count == 2


@pytest.mark.asyncio
async def test_async_retry_exhausts_retries():
    coro = AsyncMock(side_effect=FakeConnectionError("boom"))
    with patch("app.services.source_db_connector.asyncio.sleep", new_callable=AsyncMock):
        with pytest.raises(FakeConnectionError):
            await async_retry(coro, max_retries=2, base_delay=0.1, max_delay=1.0)
    assert coro.await_count == 3  # initial + 2 retries


@pytest.mark.asyncio
async def test_retry_async_decorator():
    @retry_async(max_retries=2, base_delay=0.01, max_delay=0.1)
    async def flaky():
        if flaky.calls == 0:
            flaky.calls += 1
            raise FakeConnectionError("fail")
        return "ok"

    flaky.calls = 0
    with patch("app.services.source_db_connector.asyncio.sleep", new_callable=AsyncMock):
        result = await flaky()
    assert result == "ok"
    assert flaky.calls == 1


@pytest.mark.asyncio
async def test_non_retryable_error_raises_immediately():
    coro = AsyncMock(side_effect=ValueError("bad data"))
    with pytest.raises(ValueError):
        await async_retry(coro, max_retries=2)
    coro.assert_awaited_once()
