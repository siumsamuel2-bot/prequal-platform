"""Async HTTP client for state credential database lookups.

Supports two data paths:
  1. REST API (legacy path via STATE_API_URL_* env vars)
  2. Web scrapers (primary path for states without public APIs)

Each state exposes its own contractor licensing board interface. This client
provides a normalized interface for fetching and caching credential records.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import aiohttp

from app.services.resilience import (
    AsyncCircuitBreaker,
    RetryableHTTPError,
    async_retry_call,
    resilient_call,
)
from app.services.state_scrapers.factory import get_scraper
from app.services.state_scrapers.base import ScrapedCredentialRecord

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=30)


class StateCredentialClientError(Exception):
    """Raised when the state credential API returns a non-retryable error."""


class StateCredentialClient:
    """Generic async credential client for state licensing boards.

    Supports both API and scraper-based data sources.  The scraper path is
    preferred when no public API is available (most US states).  HTTP calls
    are retried with exponential backoff and guarded by a circuit breaker so
    transient upstream failures do not surface as silent errors.
    """

    def __init__(
        self,
        state_code: str,
        *,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: Optional[aiohttp.ClientTimeout] = None,
    ) -> None:
        self.state_code = state_code.upper()
        self.base_url = base_url or os.getenv(f"STATE_API_URL_{self.state_code}", "")
        self.api_key = api_key or os.getenv(f"STATE_API_KEY_{self.state_code}")
        self._timeout = timeout or DEFAULT_TIMEOUT
        self._session: Optional[aiohttp.ClientSession] = None
        self._scraper = get_scraper(self.state_code)
        self._breaker = AsyncCircuitBreaker(name=f"state-creds-{self.state_code}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def fetch_credentials(
        self,
        *,
        query: Optional[str] = None,
        credential_type: Optional[str] = None,
        active_only: bool = True,
        page: int = 1,
        page_size: int = 50,
    ) -> dict[str, Any]:
        """Search the state for credential records matching *query*.

        Attempts the API path first (if configured), then falls back to the
        scraper path.
        """
        # Prefer scraper when no API is configured (most states)
        if not self.base_url and self._scraper is not None:
            logger.debug("Using scraper for state %s", self.state_code)
            records = await async_retry_call(
                lambda: self._scraper.search_by_business_name(query or "")
            )
            if active_only:
                records = [r for r in records if r.status == "active"]
            return {"results": [r.__dict__ for r in records], "count": len(records)}

        # Legacy API path
        if not self.base_url:
            logger.warning("No base URL or scraper configured for state %s; returning empty.", self.state_code)
            return {"results": [], "count": 0}

        params: dict[str, Any] = {"page": page, "page_size": page_size}
        if query:
            params["q"] = query
        if credential_type:
            params["type"] = credential_type
        if active_only:
            params["status"] = "active"

        session = await self._get_session()
        url = urljoin(self.base_url.rstrip("/") + "/", "credentials/search")
        logger.debug("Fetching state credentials from %s", url)
        return await resilient_call(
            lambda: self._fetch_api_page(session, url, params),
            breaker=self._breaker,
        )

    async def _fetch_api_page(
        self,
        session: aiohttp.ClientSession,
        url: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Fetch a single page from the state API, classifying HTTP errors.

        Server errors (5xx) and rate limiting (429) raise
        ``RetryableHTTPError`` so the retry layer retries them; other
        client errors raise ``StateCredentialClientError`` and fail fast.
        """
        async with session.get(url, params=params) as resp:
            if resp.status == 200:
                data = await resp.json()
                return {"results": data.get("results", []), "count": data.get("count", 0)}
            body = await resp.text()
            if resp.status == 429 or resp.status >= 500:
                logger.warning("State API transient error %s: %s", resp.status, body[:200])
                raise RetryableHTTPError(f"State API returned HTTP {resp.status}")
            logger.error("State API error %s: %s", resp.status, body)
            raise StateCredentialClientError(f"State API returned HTTP {resp.status}: {body[:200]}")

    async def paginate_credentials(
        self,
        *,
        query: Optional[str] = None,
        credential_type: Optional[str] = None,
        active_only: bool = True,
        page_size: int = 50,
        max_pages: Optional[int] = None,
    ) -> List[dict[str, Any]]:
        """Fetch all pages of results from the state."""
        all_results: List[dict[str, Any]] = []
        page = 1
        while True:
            batch = await self.fetch_credentials(
                query=query,
                credential_type=credential_type,
                active_only=active_only,
                page=page,
                page_size=page_size,
            )
            results = batch.get("results", [])
            all_results.extend(results)
            page += 1
            if not results or (max_pages is not None and page > max_pages):
                break
        return all_results

    async def lookup_by_license_number(self, license_number: str) -> List[ScrapedCredentialRecord]:
        """Look up a credential by license number (scraper path)."""
        if self._scraper is None:
            raise RuntimeError(f"No scraper available for state {self.state_code}")
        return await self._scraper.search_by_license_number(license_number)

    async def lookup_by_business_name(self, business_name: str) -> List[ScrapedCredentialRecord]:
        """Look up credentials by business name (scraper path)."""
        if self._scraper is None:
            raise RuntimeError(f"No scraper available for state {self.state_code}")
        return await self._scraper.search_by_business_name(business_name)

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            headers = {"Accept": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            self._session = aiohttp.ClientSession(
                headers=headers,
                timeout=self._timeout,
                raise_for_status=False,
            )
        return self._session

    async def close(self) -> None:
        if self._scraper is not None:
            await self._scraper.close()
        if self._session and not self._session.closed:
            await self._session.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()
