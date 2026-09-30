"""Texas Department of Licensing and Regulation (TDLR) web scraper.

Scrapes the TDLR public license verification at:
    https://www.tdlr.texas.gov

Owner: Data Engineer
"""
from __future__ import annotations

import logging
import re
from datetime import date
from typing import Any, Dict, List, Optional

import aiohttp
from bs4 import BeautifulSoup

from .base import StateScraper, ScrapedCredentialRecord

logger = logging.getLogger(__name__)

TDLR_VERIFY_URL = "https://www.tdlr.texas.gov/tools_search/"
TDLR_SEARCH_URL = "https://www.tdlr.texas.gov/tools_search/mver_Search.asp"

DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=30)


class TX_TDLR_Scraper(StateScraper):
    """Scraper for the Texas TDLR license lookup."""

    def __init__(self, timeout: Optional[aiohttp.ClientTimeout] = None) -> None:
        self._session: Optional[aiohttp.ClientSession] = None
        self._timeout = timeout or DEFAULT_TIMEOUT
        self._headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        }

    @property
    def state_code(self) -> str:
        return "TX"

    @property
    def state_name(self) -> str:
        return "Texas"

    async def search_by_license_number(self, license_number: str) -> List[ScrapedCredentialRecord]:
        session = await self._get_session()
        form_data = {
            "searchtype": "license",
            "searchstring": license_number.strip(),
            "submit": "Search",
        }
        html = await self._post_search(session, form_data)
        return self._parse_results(html)

    async def search_by_business_name(self, business_name: str) -> List[ScrapedCredentialRecord]:
        session = await self._get_session()
        form_data = {
            "searchtype": "name",
            "searchstring": business_name.strip(),
            "submit": "Search",
        }
        html = await self._post_search(session, form_data)
        return self._parse_results(html)

    async def search_by_contractor_name(self, last_name: str, first_name: Optional[str] = None) -> List[ScrapedCredentialRecord]:
        session = await self._get_session()
        search_name = f"{first_name or ''} {last_name}".strip()
        form_data = {
            "searchtype": "name",
            "searchstring": search_name,
            "submit": "Search",
        }
        html = await self._post_search(session, form_data)
        return self._parse_results(html)

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers=self._headers,
                timeout=self._timeout,
                raise_for_status=False,
            )
        return self._session

    async def _post_search(self, session: aiohttp.ClientSession, form_data: Dict[str, str]) -> str:
        logger.debug("POSTing TDLR search form")   
        async with session.post(TDLR_SEARCH_URL, data=form_data) as resp:
            if resp.status not in (200,):
                body = await resp.text()
                raise TX_TDLR_ScrapeError(f"Search POST returned HTTP {resp.status}: {body[:200]}")
            return await resp.text()

    def _parse_results(self, html: str) -> List[ScrapedCredentialRecord]:
        soup = BeautifulSoup(html, "html.parser")
        records: List[ScrapedCredentialRecord] = []

        results_table = soup.find("table", class_=re.compile(r"results|data|grid", re.I))
        if not results_table:
            detail = self._extract_detail_from_soup(soup)
            if detail:
                return [detail]
            return []

        for row in results_table.find_all("tr")[1:]:
            cells = row.find_all("td")
            if len(cells) < 4:
                continue

            license_number = cells[0].get_text(strip=True)
            business_name = cells[1].get_text(strip=True)
            license_type = cells[2].get_text(strip=True)
            status_text = cells[3].get_text(strip=True)

            records.append(
                ScrapedCredentialRecord(
                    state_code=self.state_code,
                    credential_number=license_number,
                    credential_type=license_type or "Contractor",
                    issuing_state=self.state_name,
                    holder_name=business_name,
                    status=self._map_status(status_text),
                )
            )

        logger.info("Parsed %d results from TDLR search page", len(records))
        return records

    def _extract_detail_from_soup(self, soup: BeautifulSoup) -> Optional[ScrapedCredentialRecord]:
        lic_patterns = [
            ("span", {"id": re.compile(r"lblLic.*", re.I)}),
            ("span", {"class": re.compile(r"lic.*num", re.I)}),
        ]
        license_number = None
        for tag_name, attrs in lic_patterns:
            tag = soup.find(tag_name, attrs)
            if tag:
                license_number = tag.get_text(strip=True)
                break

        if not license_number:
            return None

        biz_tag = soup.find("span", {"id": re.compile(r"lblBus.*", re.I)}) or soup.find("span", {"class": re.compile(r"business.*name", re.I)})
        business_name = biz_tag.get_text(strip=True) if biz_tag else None

        cls_tag = soup.find("span", {"id": re.compile(r"lblType|lblClass", re.I)})
        classification = cls_tag.get_text(strip=True) if cls_tag else None

        status_tag = soup.find("span", {"id": re.compile(r"lblStatus", re.I)})
        status_text = status_tag.get_text(strip=True) if status_tag else None

        exp_tag = soup.find("span", {"id": re.compile(r"lblExp|lblExpiration", re.I)})
        expiration_date = self._parse_date(exp_tag.get_text(strip=True)) if exp_tag else None

        addr_tag = soup.find("span", {"id": re.compile(r"lblAddress", re.I)})
        address = addr_tag.get_text(strip=True) if addr_tag else None

        city_tag = soup.find("span", {"id": re.compile(r"lblCity", re.I)})
        city = city_tag.get_text(strip=True) if city_tag else None

        zip_tag = soup.find("span", {"id": re.compile(r"lblZip", re.I)})
        zip_code = zip_tag.get_text(strip=True) if zip_tag else None

        return ScrapedCredentialRecord(
            state_code=self.state_code,
            credential_number=license_number,
            credential_type=classification or "Contractor",
            issuing_state=self.state_name,
            holder_name=business_name,
            holder_address=address,
            holder_city=city,
            holder_state="TX",
            holder_zip=zip_code,
            expiration_date=expiration_date,
            status=self._map_status(status_text),
            raw_data={"source": "TDLR"},
        )

    @staticmethod
    def _map_status(status_text: Optional[str]) -> str:
        if not status_text:
            return "active"
        s = status_text.lower().strip()
        mapping = {
            "active": "active",
            "inactive": "expired",
            "expired": "expired",
            "suspended": "suspended",
            "revoked": "revoked",
            "cancelled": "revoked",
        }
        return mapping.get(s, "active")

    @staticmethod
    def _parse_date(value: str) -> Optional[date]:
        if not value:
            return None
        from datetime import datetime
        for fmt in ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d", "%B %d, %Y"):
            try:
                return datetime.strptime(value.strip(), fmt).date()
            except ValueError:
                continue
        return None

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()


class TX_TDLR_ScrapeError(Exception):
    """Raised when the TDLR scraper encounters an unrecoverable error."""
    pass
