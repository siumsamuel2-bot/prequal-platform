"""Resilience utilities for critical API integrations.

Extends the source-DB connector pattern (``app.services.source_db_connector``)
to outbound HTTP dependencies.  The connector pattern provides env-driven
configuration, exponential backoff with jitter, and a standalone reusable
retry layer; this module adds:

- ``AsyncCircuitBreaker`` — asyncio-friendly circuit breaker that fails fast
  once a dependency is persistently failing and allows trial calls after a
  cooldown.
- ``async_retry_call`` / ``retry_with_backoff`` — retry any awaitable with
  exponential backoff and jitter on configurable retryable exceptions.
- ``resilient_call`` — combine circuit breaker + retry for critical calls.
- ``RetryableHTTPError`` — marker exception for 5xx/429 HTTP responses so
  callers can distinguish transient upstream failures from client errors.

All critical API clients (OSHA, state credential databases) should route
their HTTP operations through these helpers so transient failures are
retried automatically and persistently failing upstreams fail fast instead
of causing silent timeouts.
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import time
from enum import Enum
from functools import wraps
from typing import Any, Awaitable, Callable, Optional, Tuple, Type

import aiohttp

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration (env-driven, overridable by Ops)
# ---------------------------------------------------------------------------

API_MAX_RETRIES = int(os.getenv("API_MAX_RETRIES", "3"))
API_BASE_RETRY_DELAY = float(os.getenv("API_BASE_RETRY_DELAY", "0.5"))
API_MAX_RETRY_DELAY = float(os.getenv("API_MAX_RETRY_DELAY", "8.0"))

CIRCUIT_FAILURE_THRESHOLD = int(os.getenv("CIRCUIT_FAILURE_THRESHOLD", "5"))
CIRCUIT_RECOVERY_TIMEOUT = float(os.getenv("CIRCUIT_RECOVERY_TIMEOUT", "30.0"))

# ---------------------------------------------------------------------------
# Exception types
# ---------------------------------------------------------------------------


class CircuitOpenError(Exception):
    """Raised when a call is blocked because the circuit breaker is open."""


class RetryableHTTPError(Exception):
    """Raised for HTTP responses that are transient and worth retrying
    (server errors and rate limiting: 5xx, 429)."""


_RETRYABLE_API_EXCEPTIONS: Tuple[Type[BaseException], ...] = (
    RetryableHTTPError,
    aiohttp.ClientError,
    asyncio.TimeoutError,
    ConnectionError,
    OSError,
)


def is_retryable(exc: BaseException) -> bool:
    """Return True if *exc* is a transient API error worth retrying."""
    return isinstance(exc, _RETRYABLE_API_EXCEPTIONS)


# ---------------------------------------------------------------------------
# Circuit breaker
# ---------------------------------------------------------------------------


class CircuitState(Enum):
    """States of a circuit breaker."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class AsyncCircuitBreaker:
    """Asyncio-friendly circuit breaker.

    The breaker stays CLOSED while calls succeed. After
    ``failure_threshold`` consecutive failures it opens and immediately
    rejects calls with ``CircuitOpenError``. After ``recovery_timeout``
    seconds it transitions to HALF_OPEN and allows trial calls; if a trial
    succeeds the breaker closes, otherwise it opens again.
    """

    def __init__(
        self,
        failure_threshold: int = CIRCUIT_FAILURE_THRESHOLD,
        recovery_timeout: float = CIRCUIT_RECOVERY_TIMEOUT,
        name: str = "circuit",
    ) -> None:
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be >= 1")
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.name = name
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = 0.0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        """Current state, promoting OPEN -> HALF_OPEN after the cooldown."""
        return self._current_state()

    def _current_state(self) -> CircuitState:
        if (
            self._state == CircuitState.OPEN
            and time.monotonic() - self._last_failure_time >= self.recovery_timeout
        ):
            return CircuitState.HALF_OPEN
        return self._state

    async def allow_call(self) -> None:
        """Raise ``CircuitOpenError`` if calls are currently blocked."""
        async with self._lock:
            if self._current_state() == CircuitState.OPEN:
                raise CircuitOpenError(
                    f"circuit '{self.name}' is open; "
                    f"retry after {self.recovery_timeout:.0f}s cooldown"
                )
            if self._state == CircuitState.OPEN:
                self._state = CircuitState.HALF_OPEN
                logger.info("Circuit '%s' half-open; allowing trial call", self.name)

    async def record_success(self) -> None:
        """Record a successful call; resets the breaker to CLOSED."""
        async with self._lock:
            self._failure_count = 0
            self._state = CircuitState.CLOSED

    async def record_failure(self) -> None:
        """Record a failed call; opens the breaker once the threshold is hit."""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                logger.warning("Circuit '%s' re-opened after failed trial call", self.name)
            elif self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                logger.warning(
                    "Circuit '%s' opened after %d consecutive failures",
                    self.name,
                    self._failure_count,
                )

    async def call(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Execute ``func`` guarded by the breaker."""
        await self.allow_call()
        try:
            result = await func(*args, **kwargs)
        except Exception:
            await self.record_failure()
            raise
        await self.record_success()
        return result


# ---------------------------------------------------------------------------
# Core retry helpers
# ---------------------------------------------------------------------------


def _backoff_delay(attempt: int, *, base_delay: float, max_delay: float, jitter: bool) -> float:
    """Compute the delay before retry *attempt* (0-indexed).

    ``min(max_delay, base_delay * 2 ** attempt)``, optionally scaled by a
    random jitter factor in [0.5, 1.0) to avoid thundering herds.
    """
    delay = min(max_delay, base_delay * (2**attempt))
    if jitter:
        delay *= random.uniform(0.5, 1.0)
    return delay


async def async_retry_call(
    coro_factory: Callable[[], Awaitable[Any]],
    *,
    max_retries: int = API_MAX_RETRIES,
    base_delay: float = API_BASE_RETRY_DELAY,
    max_delay: float = API_MAX_RETRY_DELAY,
    retryable_exceptions: Tuple[Type[BaseException], ...] = _RETRYABLE_API_EXCEPTIONS,
    jitter: bool = True,
) -> Any:
    """Run an awaitable with exponential backoff + jitter on retryable errors.

    Args:
        coro_factory: A callable that returns the awaitable to execute.
                      Called fresh on each attempt so the coroutine is not
                      reused.
        max_retries: Maximum number of retry attempts after the initial call.
        base_delay: Initial delay in seconds.
        max_delay: Cap on delay in seconds.
        retryable_exceptions: Exception types worth retrying; anything else
                              propagates immediately.
        jitter: Scale delays by a random factor in [0.5, 1.0).

    Returns:
        The result of *coro_factory()*.

    Raises:
        The last exception raised if retries are exhausted or the error is
        not considered retryable.
    """
    if max_retries < 0:
        raise ValueError("max_retries must be >= 0")

    attempt = 0
    while True:
        try:
            return await coro_factory()
        except retryable_exceptions as exc:
            if attempt >= max_retries:
                raise
            delay = _backoff_delay(attempt, base_delay=base_delay, max_delay=max_delay, jitter=jitter)
            logger.warning(
                "API retry %d/%d after %.2fs: %s",
                attempt + 1,
                max_retries,
                round(delay, 2),
                exc,
            )
            attempt += 1
            await asyncio.sleep(delay)


def retry_with_backoff(
    *,
    max_retries: int = API_MAX_RETRIES,
    base_delay: float = API_BASE_RETRY_DELAY,
    max_delay: float = API_MAX_RETRY_DELAY,
    retryable_exceptions: Tuple[Type[BaseException], ...] = _RETRYABLE_API_EXCEPTIONS,
    jitter: bool = True,
) -> Callable:
    """Decorator factory: apply ``async_retry_call`` to a coroutine function."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            return await async_retry_call(
                lambda: func(*args, **kwargs),
                max_retries=max_retries,
                base_delay=base_delay,
                max_delay=max_delay,
                retryable_exceptions=retryable_exceptions,
                jitter=jitter,
            )

        return wrapper

    return decorator


async def resilient_call(
    coro_factory: Callable[[], Awaitable[Any]],
    *,
    breaker: Optional[AsyncCircuitBreaker] = None,
    **retry_kwargs: Any,
) -> Any:
    """Run an awaitable guarded by an optional circuit breaker with retry.

    Combines :class:`AsyncCircuitBreaker` and :func:`async_retry_call`: the
    breaker fails fast when the dependency is persistently failing, while
    the retry layer absorbs transient errors with exponential backoff.
    A failure of the whole call (including exhausted retries) counts as one
    breaker failure.
    """
    if breaker is not None:
        await breaker.allow_call()
    try:
        result = await async_retry_call(coro_factory, **retry_kwargs)
    except Exception:
        if breaker is not None:
            await breaker.record_failure()
        raise
    if breaker is not None:
        await breaker.record_success()
    return result
