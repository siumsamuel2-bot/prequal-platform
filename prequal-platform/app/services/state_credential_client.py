"""Async HTTP client for state credential database lookups.

Each state exposes its own contractor licensing board API. This client
provides a normalized interface for fetching and caching credential records.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import date, datetime
from typing import Any, Optional, Dict, List
from urllib.parse import urljoin

import aiohttp

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=30)


class StateCredentialClient:
    """Generic async credential client for state licensing boards APIs.

    Configuration is read from environment variables keyed by state code:
      STATE_API_URL_{CODE}   - base URL for the state API
      STATE_API_KEY_{CODE}   - API key (optional)
    """

    def __init__(self, state_code: str, base_url: Optional[str] = None, api_key: Optional[str] = None) -> None:
        self.state_code = state_code.upper()
        self.base_url = base_url or os.getenv(f"STATE_API_URL_{self.state_code}", "")
        self.api_key = api_key or os.getenv(f"STATE_API_KEY_{self.state_code}")
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            headers = {"Accept": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            self._session = aiohttp.ClientSession(
                headers=headers,
                timeout=DEFAULT_TIMEOUT,
                raise_for_status=False,
            )
        return self._session

    async def fetch_credentials(
        self,
        *,
        query: Optional[str] = None,
        credential_type: Optional[str] = None,
        active_only: bool = True,
        page: int = 1,
        page_size: int = 50,
    ) -> dict[str, Any]:
        """Search the state API for credential records matching *query*."""
        if not self.base_url:
            logger.warning("No base URL configured for state %s; returning empty.", self.state_code)
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
        async with session.get(url, params=params) as resp:
            if resp.status == 200:
                data = await resp.json()
                return {"results": data.get("results", []), "count": data.get("count", 0)}
            else:
                body = await resp.text()
                logger.error("State API error %s: %s", resp.status, body)
                resp.raise_for_status()
                return {"results": [], "count": 0}

    async def paginate_credentials(
        self,
        *,
        query: Optional[str] = None,
        credential_type: Optional[str] = None,
        active_only: bool = True,
        page_size: int = 50,
        max_pages: Optional[int] = None,
    ) -> List[dict[str, Any]]:
        """Fetch all pages of results from the state API."""
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

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()
