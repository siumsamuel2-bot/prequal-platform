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
from typing import Any, Callable, Tuple, Type

import asyncpg
from sqlalchemy.exc import DBAPIError, OperationalError

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
