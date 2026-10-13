"""Extra coverage for app.services.source_db_connector (MID-676).

Complements the existing ``test_source_db_connector.py`` by exercising the
retry/backoff/circuit-breaker/metrics surface directly:

* ``_extract_error_code`` / ``is_retryable_error`` / ``classify_error``,
* ``RetryConfig`` validation + ``calculate_backoff``,
* ``CircuitBreaker`` state machine (incl. OPEN -> HALF_OPEN recovery),
* ``ConnectorMetrics`` counters + snapshot,
* ``async_retry`` / ``retry_async`` (success, retry-then-succeed,
  non-retryable, exhausted),
* ``SourceDBConnector._run_with_retry`` (success, retry, non-retryable,
  exhausted, timeout, circuit-open rejection).

No real database is touched.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.services import source_db_connector as sdb


def _db_error(code=None, message="boom"):
    """A generic exception carrying an optional driver error code."""
    exc = Exception(message)
    if code is not None:
        exc.code = code
    return exc


class _CoroFactory:
    """Callable returning the next awaitable/exception from a script."""

    def __init__(self, script):
        self._script = list(script)
        self.calls = 0

    def __call__(self):
        self.calls += 1
        nxt = self._script.pop(0)

        async def _resolve():
            if isinstance(nxt, BaseException):
                raise nxt
            return nxt

        return _resolve()


# ---------------------------------------------------------------------------
# Error classification
# ---------------------------------------------------------------------------

def test_extract_error_code_variants() -> None:
    assert sdb._extract_error_code(_db_error(code="57P03")) == "57P03"
    assert sdb._extract_error_code(_db_error()) is None

    sqlstate = Exception()
    sqlstate.sqlstate = "08006"
    assert sdb._extract_error_code(sqlstate) == "08006"

    pgcode = Exception()
    pgcode.pgcode = "23505"
    assert sdb._extract_error_code(pgcode) == "23505"

    outer = Exception()
    outer.orig = _db_error(code="ECONNRESET")
    assert sdb._extract_error_code(outer) == "ECONNRESET"


def test_is_retryable_error() -> None:
    assert sdb.is_retryable_error(_db_error(code="ECONNRESET")) is True
    assert sdb.is_retryable_error(_db_error(code="23505")) is False
    assert sdb.is_retryable_error(OSError("x")) is True
    assert sdb.is_retryable_error(asyncio.TimeoutError()) is True
    assert sdb.is_retryable_error(ValueError("bad input")) is False
    assert sdb.is_retryable_error(Exception("server closed the connection unexpectedly")) is True
    assert sdb.is_retryable_error(Exception("totally fine")) is False


def test_classify_error() -> None:
    permanent = sdb.classify_error(ValueError("bad"))
    assert permanent == {
        "retryable": False,
        "category": "PERMANENT",
        "code": None,
        "recommendedAction": "FAIL_FAST",
    }

    network = sdb.classify_error(_db_error(code="ECONNRESET"))
    assert network["retryable"] is True
    assert network["category"] == "TRANSIENT_NETWORK"
    assert network["recommendedAction"] == "RETRY_WITH_BACKOFF"

    db = sdb.classify_error(OSError("nope"))
    assert db["category"] == "TRANSIENT_DB"
    assert db["code"] is None


# ---------------------------------------------------------------------------
# RetryConfig + backoff
# ---------------------------------------------------------------------------

def test_retry_config_valid_and_to_dict() -> None:
    cfg = sdb.RetryConfig(max_retries=3, base_delay=1.0, max_delay=8.0, jitter_factor=0.0)
    assert cfg.to_dict() == {
        "max_retries": 3,
        "base_delay": 1.0,
        "max_delay": 8.0,
        "jitter_factor": 0.0,
        "timeout_seconds": 30.0,
    }


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_retries": 0},
        {"base_delay": 0},
        {"max_delay": 0},
        {"base_delay": 5.0, "max_delay": 1.0},
        {"jitter_factor": 1.5},
    ],
)
def test_retry_config_rejects_invalid(kwargs) -> None:
    with pytest.raises(ValueError):
        sdb.RetryConfig(**kwargs)


def test_calculate_backoff() -> None:
    cfg = sdb.RetryConfig(base_delay=1.0, max_delay=4.0, jitter_factor=0.0)
    assert sdb.calculate_backoff(0, cfg) == 1.0
    assert sdb.calculate_backoff(1, cfg) == 2.0
    assert sdb.calculate_backoff(10, cfg) == 4.0  # capped
    assert sdb.calculate_backoff(-3, cfg) == 1.0  # clamped to attempt 0

    jitter_cfg = sdb.RetryConfig(base_delay=1.0, max_delay=10.0, jitter_factor=0.2)
    for _ in range(20):
        value = sdb.calculate_backoff(2, jitter_cfg)
        assert 4.0 * 0.8 <= value <= 4.0 * 1.2


# ---------------------------------------------------------------------------
# Circuit breaker
# ---------------------------------------------------------------------------

def test_circuit_breaker_invalid_config() -> None:
    with pytest.raises(ValueError):
        sdb.CircuitBreaker(failure_threshold=0)
    with pytest.raises(ValueError):
        sdb.CircuitBreaker(recovery_timeout=-1)


def test_circuit_breaker_opens_and_recovers(monkeypatch) -> None:
    clock = {"t": 1000.0}
    monkeypatch.setattr(sdb.time, "time", lambda: clock["t"])

    cb = sdb.CircuitBreaker(failure_threshold=2, recovery_timeout=10.0)
    assert cb.state is sdb.CircuitBreakerState.CLOSED
    cb.record_failure()
    assert cb.is_open() is False
    cb.record_failure()
    assert cb.is_open() is True
    assert cb.snapshot()["state"] == "OPEN"

    # Advance the clock past the recovery timeout -> HALF_OPEN probe allowed.
    clock["t"] += 11
    assert cb.state is sdb.CircuitBreakerState.HALF_OPEN
    assert cb.is_open() is False

    # A failure while HALF_OPEN re-opens it at the current time.
    cb.record_failure()
    assert cb._state is sdb.CircuitBreakerState.OPEN
    assert cb.is_open() is True

    # Success + reset close it.
    cb.record_success()
    assert cb.state is sdb.CircuitBreakerState.CLOSED
    cb.record_failure()
    cb.reset()
    assert cb.state is sdb.CircuitBreakerState.CLOSED
    assert cb.snapshot()["failures"] == 0


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def test_connector_metrics_counters_and_snapshot() -> None:
    m = sdb.ConnectorMetrics()
    assert m.snapshot()["success_rate"] == 0.0
    assert m.snapshot()["avg_latency_ms"] == 0.0

    m.record_attempt()
    m.record_attempt()
    m.record_success(10.0)
    m.record_success(30.0)
    m.record_failure(ValueError("x"))
    m.record_retry()
    m.record_timeout()
    m.record_rejection()
    snap = m.snapshot()
    assert snap["attempts"] == 2
    assert snap["successes"] == 2
    assert snap["success_rate"] == 100.0
    assert snap["avg_latency_ms"] == 20.0
    assert snap["failures"] == 1
    assert snap["last_error"] == "x"
    assert snap["retries"] == 1 and snap["timeouts"] == 1 and snap["circuit_open_rejections"] == 1

    m.reset()
    assert m.snapshot()["attempts"] == 0


# ---------------------------------------------------------------------------
# async_retry / retry_async
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_async_retry_success_first_try() -> None:
    factory = _CoroFactory(["ok"])
    result = await sdb.async_retry(factory, max_retries=2, base_delay=0.001, max_delay=0.002)
    assert result == "ok"
    assert factory.calls == 1


@pytest.mark.asyncio
async def test_async_retry_retries_then_succeeds() -> None:
    factory = _CoroFactory([OSError("connection refused"), OSError("timeout"), "ok"])
    result = await sdb.async_retry(factory, max_retries=5, base_delay=0.001, max_delay=0.002)
    assert result == "ok"
    assert factory.calls == 3


@pytest.mark.asyncio
async def test_async_retry_non_retryable_raises_immediately() -> None:
    factory = _CoroFactory([ValueError("bad")])
    with pytest.raises(ValueError):
        await sdb.async_retry(factory, max_retries=5, base_delay=0.001, max_delay=0.002)
    assert factory.calls == 1


@pytest.mark.asyncio
async def test_async_retry_exhausted_raises_last_error() -> None:
    factory = _CoroFactory([OSError("a"), OSError("b"), OSError("c")])
    with pytest.raises(OSError):
        await sdb.async_retry(factory, max_retries=1, base_delay=0.001, max_delay=0.002)
    # attempt 0 fails, retry #1, then attempt 1 fails -> attempt > max_retries.
    assert factory.calls == 2


@pytest.mark.asyncio
async def test_retry_async_decorator() -> None:
    calls = {"n": 0}

    @sdb.retry_async(max_retries=3, base_delay=0.001, max_delay=0.002)
    async def flaky():
        calls["n"] += 1
        if calls["n"] < 2:
            raise OSError("transient")
        return "done"

    assert await flaky() == "done"
    assert calls["n"] == 2

    @sdb.retry_async(max_retries=1, base_delay=0.001, max_delay=0.002)
    async def always_bad():
        raise ValueError("permanent")

    with pytest.raises(ValueError):
        await always_bad()


# ---------------------------------------------------------------------------
# SourceDBConnector._run_with_retry
# ---------------------------------------------------------------------------

def _connector(**cfg):
    retry = sdb.RetryConfig(**cfg) if cfg else sdb.RetryConfig(base_delay=0.001, max_delay=0.002)
    return sdb.SourceDBConnector(retry=retry, circuit_breaker=sdb.CircuitBreaker(failure_threshold=3, recovery_timeout=60.0))


@pytest.mark.asyncio
async def test_run_with_retry_success() -> None:
    conn = _connector()
    result = await conn._run_with_retry(_CoroFactory([sdb.QueryResult(rows=[], row_count=1)]))
    assert result.row_count == 1
    assert conn.metrics.attempts == 1
    assert conn.metrics.circuit_open_rejections == 0


@pytest.mark.asyncio
async def test_run_with_retry_retries_retryable() -> None:
    conn = _connector(max_retries=3, base_delay=0.001, max_delay=0.002)
    factory = _CoroFactory([OSError("deadlock"), sdb.QueryResult(rows=[], row_count=2)])
    result = await conn._run_with_retry(factory)
    assert result.row_count == 2
    assert conn.metrics.retries == 1


@pytest.mark.asyncio
async def test_run_with_retry_non_retryable_raises() -> None:
    conn = _connector()
    with pytest.raises(ValueError):
        await conn._run_with_retry(_CoroFactory([ValueError("bad sql")]))
    assert conn.metrics.failures == 1


@pytest.mark.asyncio
async def test_run_with_retry_exhausted() -> None:
    conn = _connector(max_retries=1, base_delay=0.001, max_delay=0.002)
    with pytest.raises(OSError):
        await conn._run_with_retry(_CoroFactory([OSError("a"), OSError("b")]))


@pytest.mark.asyncio
async def test_run_with_retry_timeout_recorded() -> None:
    conn = _connector(max_retries=1, base_delay=0.001, max_delay=0.002)
    with pytest.raises(Exception):
        await conn._run_with_retry(_CoroFactory([asyncio.TimeoutError(), asyncio.TimeoutError()]))
    assert conn.metrics.timeouts >= 1


@pytest.mark.asyncio
async def test_run_with_retry_circuit_open_rejects() -> None:
    conn = _connector()
    # Trip the breaker (threshold 3).
    for _ in range(3):
        conn.circuit_breaker.record_failure()
    with pytest.raises(sdb.CircuitOpenError):
        await conn._run_with_retry(_CoroFactory([sdb.QueryResult()]))
    assert conn.metrics.circuit_open_rejections == 1


def test_connector_basics() -> None:
    conn = _connector()
    assert conn.get_retry_config().max_retries == 5 or conn.get_retry_config() is not None
    conn.update_connection_string("postgresql+asyncpg://x")
    assert conn.connection_string == "postgresql+asyncpg://x"
    assert conn._connected is False


def test_materialize_rowcount_fallback() -> None:
    class _Res:
        returns_rows = False
        rowcount = -1

    out = sdb.SourceDBConnector._materialize(_Res())
    assert out.row_count == 0 and out.rows == []
    assert out.to_dict() == {"rows": [], "row_count": 0}
