"""
OSHA API Client for the OSHA Whistleblower Enforcement API.

API:
    GET www.whistleblower.gov/api/cases
    Query params:
        page, page_size
        search (fuzzy match on company name)
        status (open|closed|pending)
        date_opened_from, date_opened_to (YYYY-MM-DD)
        state
        us state

Rate Limits:
    OSHA asks for 1 request per second for light use.
    We default to 1 req/sec via a simple asyncio semaphore.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import date, datetime
from typing import Any, Optional

import aiohttp

from app.services.resilience import AsyncCircuitBreaker, RetryableHTTPError, resilient_call

logger = logging.getLogger(__name__)

OSHA_BASE_URL = os.getenv("OSHA_API_URL", "https://www.whistleblower.gov/api/cases")
OSHA_API_KEY = os.getenv("OSHA_API_KEY", "")
OSHA_RATE_LIMIT = float(os.getenv("OSHA_RATE_LIMIT", "1.0"))  # requests per second

DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=30)


class OSHAClientError(Exception):
    pass


class OSHAClient:
    """Async client for OSHA Whistleblower API with rate limiting, retry with
    exponential backoff, and circuit-breaker protection."""

    def __init__(
        self,
        base_url: str = None,  # type: ignore[assignment]
        api_key: Optional[str] = None,
        rate_limit_hz: float = OSHA_RATE_LIMIT,
        session: Optional[aiohttp.ClientSession] = None,
    ) -> None:
        self.base_url = base_url or OSHA_BASE_URL
        self.api_key = api_key or OSHA_API_KEY
        self._session: Optional[aiohttp.ClientSession] = session
        self._limiter = asyncio.Semaphore(int(rate_limit_hz))
        self._last_request_at: float = 0.0
        self._lock = asyncio.Lock()
        self._breaker = AsyncCircuitBreaker(name="osha")

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            headers = {"Accept": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"ApiKey {self.api_key}"
            self._session = aiohttp.ClientSession(
                headers=headers,
                raise_for_status=False,
                timeout=DEFAULT_TIMEOUT,
            )
        return self._session

    async def _throttle(self) -> None:
        async with self._lock:
            import time
            elapsed = time.monotonic() - self._last_request_at
            min_interval = 1.0 / float(os.environ.get("OSHA_RATE_LIMIT", "1.0")) + 0.05
            if elapsed < min_interval:
                await asyncio.sleep(min_interval - elapsed)
            self._last_request_at = time.monotonic()

    async def search_cases(
        self,
        *,
        search: Optional[str] = None,
        state: Optional[str] = None,
        status: Optional[str] = None,
        date_opened_from: Optional[date] = None,
        date_opened_to: Optional[date] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict[str, Any]:
        "Fetches a page of OSHA cases. Returns dict with {'results': [...], ...}."
        params: dict[str, Any] = {
            "page": page,
            "page_size": min(page_size, 500),
        }
        if search:
            params["search"] = search
        if state:
            params["state"] = state
        if status:
            params["status"] = status
        if date_opened_from:
            params["date_opened_from"] = date_opened_from.isoformat()
        if date_opened_to:
            params["date_opened_to"] = date_opened_to.isoformat()

        session = await self._get_session()
        async with self._limiter:
            await self._throttle()
            logger.debug(
                "OSHA request: GET %s with params=%s", self.base_url, params
            )
            return await resilient_call(
                lambda: self._fetch_page(session, params),
                breaker=self._breaker,
            )

    async def _fetch_page(
        self,
        session: aiohttp.ClientSession,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Fetch a single page of results, classifying HTTP errors.

        Server errors (5xx) and rate limiting (429) raise
        ``RetryableHTTPError`` so the retry layer retries them; other
        client errors raise ``OSHAClientError`` and fail fast.
        """
        async with session.get(self.base_url, params=params) as resp:
            text = await resp.text()
            if resp.status == 429 or resp.status >= 500:
                logger.warning(
                    "OSHA API transient error: status=%d body=%s", resp.status, text[:500]
                )
                raise RetryableHTTPError(f"OSHA API returned HTTP {resp.status}")
            if resp.status != 200:
                logger.error(
                    "OSHA API error: status=%d body=%s", resp.status, text[:500]
                )
                raise OSHAClientError(f"OSHA API returned HTTP {resp.status}: {text[:200]}")
            data = json.loads(text)
            return data  # type: ignore[no-any-return]

    async def paginate_cases(
        self,
        *,
        search: Optional[str] = None,
        state: Optional[str] = None,
        status: Optional[str] = None,
        date_opened_from: Optional[date] = None,
        date_opened_to: Optional[date] = None,
        max_pages: Optional[int] = None,
        page_size: int = 50,
    ) -> list[dict[str, Any]]:
        """Paginate through all results, collect into a single list.
        Stops when a page returns empty results or when max_pages reached.
        """
        results: list[dict[str, Any]] = []
        page = 1
        while True:
            data = await self.search_cases(
                search=search,
                state=state,
                status=status,
                date_opened_from=date_opened_from,
                date_opened_to=date_opened_to,
                page=page,
                page_size=page_size,
            )
            page_results = data.get("results", [])
            if not page_results:
                break
            results.extend(page_results)
            page += 1
            if max_pages and page > max_pages:
                logger.info("Paginate stopping after max_pages=%d", max_pages)
                break
            # Detect total page count safely
            total_count = data.get("count", 0)
            if page * page_size >= total_count:
                break
        return results

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def __aenter__(self) -> OSHAClient:
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self.close()
