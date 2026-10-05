"""Source-DB connector with exponential-backoff retry logic.

Provides a standalone, reusable retry layer for the PostgreSQL source
connection used by the data pipeline.  All pipeline DB operations should
acquire sessions through this connector so transient failures are
retried automatically.
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Type

import asyncpg
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration (env-driven, overridable by Ops)
# ---------------------------------------------------------------------------

DB_MAX_RETRIES = int(os.getenv("DB_MAX_RETRIES", "5"))
DB_BASE_RETRY_DELAY = float(os.getenv("DB_BASE_RETRY_DELAY", "1.0"))
DB_MAX_RETRY_DELAY = float(os.getenv("DB_MAX_RETRY_DELAY", "60.0"))

# ---------------------------------------------------------------------------
# Retryable exception types
# ---------------------------------------------------------------------------

_RETRYABLE_DB_EXCEPTIONS: Tuple[Type[BaseException], ...] = (
    OperationalError,
    DBAPIError,
    asyncpg.exceptions.ConnectionDoesNotExistError,
    asyncpg.exceptions.TooManyConnectionsError,
    OSError,
)


def _is_retryable(exc: BaseException) -> bool:
    """Return True if *exc* is a transient DB error worth retrying."""
    if isinstance(exc, _RETRYABLE_DB_EXCEPTIONS):
        return True
    msg = str(exc).lower()
    return any(k in msg for k in ("connection", "timeout", "deadlock"))


# ---------------------------------------------------------------------------
# Core retry helpers
# ---------------------------------------------------------------------------

async def async_retry(
    coro_factory: Callable[[], Any],
    *,
    max_retries: int = DB_MAX_RETRIES,
    base_delay: float = DB_BASE_RETRY_DELAY,
    max_delay: float = DB_MAX_RETRY_DELAY,
    timeout_seconds: float = 30.0,
) -> Any:
    """Run an awaitable with exponential backoff + jitter on retryable DB errors.

    Args:
        coro_factory: A callable that returns the awaitable to execute.
                      Called fresh on each attempt so the coroutine is not reused.
        max_retries: Maximum number of retry attempts.
        base_delay: Initial delay in seconds.
        max_delay: Cap on delay in seconds.
        timeout_seconds: Timeout for each individual attempt.

    Returns:
        The result of *coro_factory()*.

    Raises:
        The last exception raised if retries are exhausted or the error is
        not considered retryable.
    """
    attempt = 0
    while True:
        try:
            return await asyncio.wait_for(coro_factory(), timeout=timeout_seconds)
        except asyncio.TimeoutError:
            logger.warning(
                "Source-DB connector attempt %d/%d timed out after %.1fs",
                attempt + 1,
                max_retries,
                timeout_seconds,
            )
            if not _is_retryable(TimeoutError("Operation timed out")):
                raise
            attempt += 1
            if attempt > max_retries:
                raise TimeoutError(f"Operation timed out after {max_retries} attempts")
            delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
            delay = delay * (0.5 + random.random() / 2)
            delay = min(delay, max_delay)
            logger.warning(
                "Source-DB connector retry %d/%d after %.2fs: timeout",
                attempt,
                max_retries,
                round(delay, 2),
            )
            await asyncio.sleep(delay)
        except Exception as exc:  # noqa: BLE001
            if not _is_retryable(exc):
                raise
            attempt += 1
            if attempt > max_retries:
                raise
            delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
            delay = delay * (0.5 + random.random() / 2)
            delay = min(delay, max_delay)
            logger.warning(
                "Source-DB connector retry %d/%d after %.2fs: %s",
                attempt,
                max_retries,
                round(delay, 2),
                exc,
            )
            await asyncio.sleep(delay)


def retry_async(
    *,
    max_retries: int = DB_MAX_RETRIES,
    base_delay: float = DB_BASE_RETRY_DELAY,
    max_delay: float = DB_MAX_RETRY_DELAY,
    timeout_seconds: float = 30.0,
) -> Callable:
    """Decorator factory: apply ``async_retry`` to a coroutine function."""

    def decorator(func: Callable) -> Callable:
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            attempt = 0
            while True:
                try:
                    return await asyncio.wait_for(func(*args, **kwargs), timeout=timeout_seconds)
                except asyncio.TimeoutError:
                    logger.warning(
                        "Source-DB connector attempt %d/%d timed out after %.1fs for %s",
                        attempt + 1,
                        max_retries,
                        timeout_seconds,
                        func.__name__,
                    )
                    if not _is_retryable(TimeoutError("Operation timed out")):
                        raise
                    attempt += 1
                    if attempt > max_retries:
                        raise TimeoutError(f"Operation timed out after {max_retries} attempts for {func.__name__}")
                    delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                    delay = delay * (0.5 + random.random() / 2)
                    delay = min(delay, max_delay)
                    logger.warning(
                        "Source-DB connector retry %d/%d after %.2fs for %s: timeout",
                        attempt,
                        max_retries,
                        round(delay, 2),
                        func.__name__,
                    )
                    await asyncio.sleep(delay)
                except Exception as exc:  # noqa: BLE001
                    if not _is_retryable(exc):
                        raise
                    attempt += 1
                    if attempt > max_retries:
                        raise
                    delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                    delay = delay * (0.5 + random.random() / 2)
                    delay = min(delay, max_delay)
                    logger.warning(
                        "Source-DB connector retry %d/%d after %.2fs for %s: %s",
                        attempt,
                        max_retries,
                        round(delay, 2),
                        func.__name__,
                        exc,
                    )
                    await asyncio.sleep(delay)

        # Preserve metadata for easier introspection
        wrapper.__name__ = func.__name__  # type: ignore[assignment]
        wrapper.__doc__ = func.__doc__
        return wrapper

    return decorator


# ---------------------------------------------------------------------------
# Error classification
# ---------------------------------------------------------------------------

#: PostgreSQL / socket error codes that represent transient failures and are
#: therefore safe to retry with backoff.
RETRYABLE_ERROR_CODES = frozenset(
    {
        "ECONNREFUSED",
        "ECONNRESET",
        "ECONNABORTED",
        "ETIMEDOUT",
        "ENOTFOUND",
        "EAI_AGAIN",
        "EHOSTUNREACH",
        "ENETUNREACH",
        "EPIPE",
        # PostgreSQL class 57: operator intervention / connection failures
        "57P01",  # admin_shutdown
        "57P02",  # crash_shutdown
        "57P03",  # cannot_connect_now
        # PostgreSQL class 08: connection exception
        "08000",
        "08003",
        "08006",
        "08001",
        "08004",
    }
)

#: Error codes that are deterministic and must never be retried.
NON_RETRYABLE_ERROR_CODES = frozenset(
    {
        "42601",  # syntax_error
        "42703",  # undefined_column
        "42P01",  # undefined_table
        "28P01",  # invalid_password
        "28000",  # invalid_authorization_specification
        "23505",  # unique_violation
        "23503",  # foreign_key_violation
        "22P02",  # invalid_text_representation
        "42501",  # insufficient_privilege
    }
)

_RETRYABLE_MESSAGE_KEYWORDS = (
    "connection",
    "timeout",
    "timed out",
    "deadlock",
    "temporarily unavailable",
    "too many connections",
    "server closed the connection",
    "connection reset",
    "broken pipe",
)


def _extract_error_code(exc: BaseException) -> Optional[str]:
    """Best-effort extraction of a driver error code from an exception.

    Looks at common attributes used by ``asyncpg`` (``sqlstate``),
    ``psycopg`` (``pgcode``) and Node-style/OS errors (``code``), including
    the underlying exception wrapped by SQLAlchemy (``orig``).
    """
    for attr in ("code", "sqlstate", "pgcode"):
        value = getattr(exc, attr, None)
        if value:
            return str(value)

    orig = getattr(exc, "orig", None)
    if orig is not None:
        code = _extract_error_code(orig)
        if code:
            return code

    # SQLAlchemy terminals some driver errors; fall back to the message.
    return None


def is_retryable_error(exc: BaseException) -> bool:
    """Return True when *exc* represents a transient, retryable failure."""
    code = _extract_error_code(exc)
    if code:
        if code in RETRYABLE_ERROR_CODES:
            return True
        if code in NON_RETRYABLE_ERROR_CODES:
            return False

    if isinstance(
        exc,
        (
            OperationalError,
            DBAPIError,
            OSError,
            asyncio.TimeoutError,
            TimeoutError,
            asyncpg.exceptions.ConnectionDoesNotExistError,
            asyncpg.exceptions.TooManyConnectionsError,
        ),
    ):
        return True

    # Deterministic programmer/data errors are never retryable.
    if isinstance(exc, (ValueError, TypeError, KeyError, AttributeError, ArithmeticError)):
        return False

    message = str(exc).lower()
    return any(keyword in message for keyword in _RETRYABLE_MESSAGE_KEYWORDS)


def classify_error(exc: BaseException) -> Dict[str, Any]:
    """Return a structured classification for an exception.

    Mirrors the contract consumed by the QA suite: ``retryable``,
    ``category``, ``code`` and ``recommendedAction``.
    """
    code = _extract_error_code(exc)
    retryable = is_retryable_error(exc)

    if not retryable:
        category = "PERMANENT"
    elif code and code in RETRYABLE_ERROR_CODES and code[0].isalpha():
        category = "TRANSIENT_NETWORK"
    else:
        category = "TRANSIENT_DB"

    return {
        "retryable": retryable,
        "category": category,
        "code": code,
        "recommendedAction": "RETRY_WITH_BACKOFF" if retryable else "FAIL_FAST",
    }


# ---------------------------------------------------------------------------
# Retry configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RetryConfig:
    """Immutable retry policy for the source-DB connector."""

    max_retries: int = DB_MAX_RETRIES
    base_delay: float = DB_BASE_RETRY_DELAY
    max_delay: float = DB_MAX_RETRY_DELAY
    jitter_factor: float = 0.1
    timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        if self.max_retries <= 0:
            raise ValueError("max_retries must be > 0")
        if self.base_delay <= 0:
            raise ValueError("base_delay must be > 0")
        if self.max_delay <= 0:
            raise ValueError("max_delay must be > 0")
        if self.max_delay < self.base_delay:
            raise ValueError("max_delay must be >= base_delay")
        if not 0.0 <= self.jitter_factor <= 1.0:
            raise ValueError("jitter_factor must be between 0 and 1")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_retries": self.max_retries,
            "base_delay": self.base_delay,
            "max_delay": self.max_delay,
            "jitter_factor": self.jitter_factor,
            "timeout_seconds": self.timeout_seconds,
        }


DEFAULT_RETRY_CONFIG = RetryConfig()


def calculate_backoff(attempt: int, config: RetryConfig = DEFAULT_RETRY_CONFIG) -> float:
    """Return the delay (seconds) before retry *attempt* (0-based).

    Uses exponential backoff capped at ``config.max_delay`` with symmetric
    jitter of ``+/- jitter_factor`` applied to the capped value.
    """
    attempt = max(0, int(attempt))
    raw = min(config.base_delay * (2 ** attempt), config.max_delay)
    if config.jitter_factor:
        raw = raw * (1.0 + config.jitter_factor * (random.random() * 2.0 - 1.0))
    return max(0.0, raw)


# ---------------------------------------------------------------------------
# Circuit breaker
# ---------------------------------------------------------------------------


class CircuitBreakerState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitOpenError(RuntimeError):
    """Raised when a call is rejected because the circuit breaker is open."""


class CircuitBreaker:
    """Minimal failure-count circuit breaker.

    Opens after ``failure_threshold`` consecutive failures and automatically
    transitions to ``HALF_OPEN`` once ``recovery_timeout`` seconds have
    elapsed, allowing a probe request through.
    """

    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 30.0) -> None:
        if failure_threshold <= 0:
            raise ValueError("failure_threshold must be > 0")
        if recovery_timeout < 0:
            raise ValueError("recovery_timeout must be >= 0")
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._failures = 0
        self._opened_at: Optional[float] = None
        self._state = CircuitBreakerState.CLOSED

    @property
    def state(self) -> CircuitBreakerState:
        if (
            self._state is CircuitBreakerState.OPEN
            and self._opened_at is not None
            and (time.time() - self._opened_at) >= self.recovery_timeout
        ):
            self._state = CircuitBreakerState.HALF_OPEN
        return self._state

    def is_open(self) -> bool:
        return self.state is CircuitBreakerState.OPEN

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None
        self._state = CircuitBreakerState.CLOSED

    def record_failure(self) -> None:
        self._failures += 1
        if self._state is CircuitBreakerState.HALF_OPEN or self._failures >= self.failure_threshold:
            self._state = CircuitBreakerState.OPEN
            self._opened_at = time.time()

    def reset(self) -> None:
        self._failures = 0
        self._opened_at = None
        self._state = CircuitBreakerState.CLOSED

    def snapshot(self) -> Dict[str, Any]:
        return {
            "state": self.state.value,
            "failures": self._failures,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout_seconds": self.recovery_timeout,
        }


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@dataclass
class ConnectorMetrics:
    """In-process counters describing connector health and retry behaviour."""

    attempts: int = 0
    successes: int = 0
    failures: int = 0
    retries: int = 0
    timeouts: int = 0
    circuit_open_rejections: int = 0
    total_latency_ms: float = 0.0
    last_error: Optional[str] = None

    def record_attempt(self) -> None:
        self.attempts += 1

    def record_success(self, latency_ms: float = 0.0) -> None:
        self.successes += 1
        self.total_latency_ms += latency_ms

    def record_failure(self, error: Optional[BaseException] = None) -> None:
        self.failures += 1
        if error is not None:
            self.last_error = str(error)

    def record_retry(self) -> None:
        self.retries += 1

    def record_timeout(self) -> None:
        self.timeouts += 1

    def record_rejection(self) -> None:
        self.circuit_open_rejections += 1

    def snapshot(self) -> Dict[str, Any]:
        success_rate = (self.successes / self.attempts * 100.0) if self.attempts else 0.0
        avg_latency = (self.total_latency_ms / self.successes) if self.successes else 0.0
        return {
            "attempts": self.attempts,
            "successes": self.successes,
            "failures": self.failures,
            "retries": self.retries,
            "timeouts": self.timeouts,
            "circuit_open_rejections": self.circuit_open_rejections,
            "success_rate": round(success_rate, 2),
            "avg_latency_ms": round(avg_latency, 2),
            "last_error": self.last_error,
        }

    def reset(self) -> None:
        self.attempts = 0
        self.successes = 0
        self.failures = 0
        self.retries = 0
        self.timeouts = 0
        self.circuit_open_rejections = 0
        self.total_latency_ms = 0.0
        self.last_error = None


@dataclass
class QueryResult:
    """Standardized result shape returned by the connector."""

    rows: List[Dict[str, Any]] = field(default_factory=list)
    row_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {"rows": self.rows, "row_count": self.row_count}


# ---------------------------------------------------------------------------
# Connector
# ---------------------------------------------------------------------------


class SourceDBConnector:
    """Resilient connector for the PostgreSQL source database.

    Wraps a SQLAlchemy async engine with the retry-with-backoff policy,
    circuit-breaker protection and metrics defined in this module. When no
    engine or connection string is supplied it borrows the platform's shared
    application engine so callers (e.g. API health checks) do not open a
    second connection pool.
    """

    def __init__(
        self,
        connection_string: Optional[str] = None,
        *,
        retry: Optional[RetryConfig] = None,
        circuit_breaker: Optional[CircuitBreaker] = None,
        engine: Optional[AsyncEngine] = None,
    ) -> None:
        self.connection_string = connection_string
        self._retry_config = retry or DEFAULT_RETRY_CONFIG
        self.circuit_breaker = circuit_breaker or CircuitBreaker()
        self.metrics = ConnectorMetrics()
        self._engine = engine
        self._owns_engine = False
        self._connected = False

    # -- lifecycle ---------------------------------------------------------

    @property
    def engine(self) -> AsyncEngine:
        if self._engine is None:
            if self.connection_string:
                self._engine = create_async_engine(self.connection_string, pool_pre_ping=True)
                self._owns_engine = True
            else:
                # Lazy import avoids a circular import at module load time.
                from app.database import engine as app_engine

                self._engine = app_engine
        return self._engine

    def get_retry_config(self) -> RetryConfig:
        return self._retry_config

    def update_connection_string(self, connection_string: str) -> None:
        """Point the connector at a new database (disposes any owned engine)."""
        self.connection_string = connection_string
        self._engine = None
        self._connected = False

    async def connect(self) -> bool:
        """Verify connectivity and mark the connector as connected."""
        await self._run_once(lambda: self._probe(), timeout=self._retry_config.timeout_seconds)
        self._connected = True
        return True

    async def disconnect(self) -> None:
        if self._owns_engine and self._engine is not None:
            await self._engine.dispose()
            self._engine = None
        self._connected = False

    async def is_connected(self) -> bool:
        return self._connected

    # -- execution ---------------------------------------------------------

    async def query(self, sql: str, params: Optional[Dict[str, Any]] = None) -> QueryResult:
        return await self._run_with_retry(
            lambda: self._execute(sql, params or {}, write=False)
        )

    async def execute(self, sql: str, params: Optional[Dict[str, Any]] = None) -> QueryResult:
        return await self._run_with_retry(
            lambda: self._execute(sql, params or {}, write=True)
        )

    async def test_connection(self) -> Dict[str, Any]:
        """Run a lightweight connectivity probe and return a status report."""
        cfg = self._retry_config
        started = time.perf_counter()
        connected = True
        error: Optional[str] = None
        try:
            await self._run_with_retry(lambda: self._probe())
        except Exception as exc:  # noqa: BLE001 - report, do not propagate
            connected = False
            error = str(exc)
        latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
        self._connected = connected
        return {
            "connected": connected,
            "latency_ms": latency_ms,
            "error": error,
            "retry_config": cfg.to_dict(),
            "circuit_breaker": self.circuit_breaker.snapshot(),
            "metrics": self.metrics.snapshot(),
        }

    # -- internals ---------------------------------------------------------

    async def _probe(self) -> int:
        async with self.engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            return int(result.scalar() or 1)

    async def _execute(
        self, sql: str, params: Dict[str, Any], *, write: bool
    ) -> QueryResult:
        if write:
            async with self.engine.begin() as conn:
                result = await conn.execute(text(sql), params)
                return self._materialize(result)
        async with self.engine.connect() as conn:
            result = await conn.execute(text(sql), params)
            return self._materialize(result)

    @staticmethod
    def _materialize(result: Any) -> QueryResult:
        rows: List[Dict[str, Any]] = []
        if getattr(result, "returns_rows", False):
            rows = [dict(row._mapping) for row in result.fetchall()]
        row_count = getattr(result, "rowcount", None)
        if row_count is None or row_count < 0:
            row_count = len(rows)
        return QueryResult(rows=rows, row_count=row_count)

    async def _run_once(self, coro_factory: Callable[[], Any], *, timeout: Optional[float] = None) -> Any:
        coro = coro_factory()
        if timeout and timeout > 0:
            return await asyncio.wait_for(coro, timeout=timeout)
        return await coro

    async def _run_with_retry(self, coro_factory: Callable[[], Any]) -> QueryResult:
        cfg = self._retry_config

        if self.circuit_breaker.is_open():
            self.metrics.record_rejection()
            raise CircuitOpenError("Source-DB connector circuit breaker is open")

        attempt = 0
        last_exc: Optional[BaseException] = None
        while True:
            self.metrics.record_attempt()
            started = time.perf_counter()
            try:
                result = await asyncio.wait_for(coro_factory(), timeout=cfg.timeout_seconds)
                self.metrics.record_success((time.perf_counter() - started) * 1000.0)
                self.circuit_breaker.record_success()
                return result
            except asyncio.TimeoutError as exc:
                last_exc = exc
                self.metrics.record_timeout()
                self.metrics.record_failure(exc)
                self.circuit_breaker.record_failure()
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                self.metrics.record_failure(exc)
                self.circuit_breaker.record_failure()
                if not is_retryable_error(exc):
                    raise

            if attempt >= cfg.max_retries:
                assert last_exc is not None
                raise last_exc

            delay = calculate_backoff(attempt, cfg)
            self.metrics.record_retry()
            logger.warning(
                "Source-DB connector retry %d/%d in %.2fs: %s",
                attempt + 1,
                cfg.max_retries,
                delay,
                last_exc,
            )
            attempt += 1
            await asyncio.sleep(delay)
