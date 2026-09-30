"""California Contractor State License Board (CSLB) web scraper.

Scrapes the CSLB public license lookup at:
    https://www.cslb.ca.gov/OnlineServices/CheckLicenseII/CheckLicense.aspx

Returns normalized ScrapedCredentialRecord objects for ingestion into the
Prequal compliance platform.

Owner: Data Engineer
"""
from __future__ import annotations

import asyncio
import logging
import re
import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional

import aiohttp
from bs4 import BeautifulSoup

from .base import StateScraper, ScrapedCredentialRecord

logger = logging.getLogger(__name__)

CSLB_BASE_URL = "https://www.cslb.ca.gov/OnlineServices/CheckLicenseII"
CSLB_SEARCH_URL = f"{CSLB_BASE_URL}/CheckLicense.aspx"
CSLB_DETAIL_URL = f"{CSLB_BASE_URL}/LicenseDetail.aspx"

# ASP.NET form field names (may shift; keep an eye on site structure)
FORM_VIEWSTATE = "__VIEWSTATE"
FORM_EVENTVALIDATION = "__EVENTVALIDATION"
FORM_EVENTTARGET = "__EVENTTARGET"
FORM_EVENTARGUMENT = "__EVENTARGUMENT"

# Search mode button IDs observed on the CSLB site
SEARCH_BY_LICENSE = "ctl00$ContentPlaceHolder1$btnLicNum"
SEARCH_BY_BUSINESS = "ctl00$ContentPlaceHolder1$btnBusName"
SEARCH_BY_CONTRACTOR = "ctl00$ContentPlaceHolder1$btnContractorName"
SEARCH_BY_HIS = "ctl00$ContentPlaceHolder1$btnHISNum"

DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=30)


class CSLBScraper(StateScraper):
    """Scraper for the California CSLB license lookup."""

    def __init__(self, timeout: Optional[aiohttp.ClientTimeout] = None) -> None:
        self._session: Optional[aiohttp.ClientSession] = None
        self._timeout = timeout or DEFAULT_TIMEOUT
        self._headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;"  
                "q=0.9,image/webp,*/*;q=0.8"
            ),
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

    # ------------------------------------------------------------------
    # StateScraper interface
    # ------------------------------------------------------------------

    @property
    def state_code(self) -> str:
        return "CA"

    @property
    def state_name(self) -> str:
        return "California"

    async def search_by_license_number(self, license_number: str) -> List[ScrapedCredentialRecord]:
        """Search CSLB by license number (most reliable)."""
        session = await self._get_session()
        form_data = await self._fetch_search_form(session)
        form_data[SEARCH_BY_LICENSE] = "Search"
        form_data["ctl00$ContentPlaceHolder1$txtLicNum"] = license_number.strip()

        records = await self._post_search(session, form_data)
        return records

    async def search_by_business_name(self, business_name: str) -> List[ScrapedCredentialRecord]:
        """Search CSLB by business name."""
        session = await self._get_session()
        form_data = await self._fetch_search_form(session)
        form_data[SEARCH_BY_BUSINESS] = "Search"
        form_data["ctl00$ContentPlaceHolder1$txtBusName"] = business_name.strip()

        records = await self._post_search(session, form_data)
        return records

    async def search_by_contractor_name(
        self, last_name: str, first_name: Optional[str] = None
    ) -> List[ScrapedCredentialRecord]:
        """Search CSLB by contractor name."""
        session = await self._get_session()
        form_data = await self._fetch_search_form(session)
        form_data[SEARCH_BY_CONTRACTOR] = "Search"
        form_data["ctl00$ContentPlaceHolder1$txtContractorLastName"] = last_name.strip()
        if first_name:
            form_data["ctl00$ContentPlaceHolder1$txtContractorFirstName"] = first_name.strip()

        records = await self._post_search(session, form_data)
        return records

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers=self._headers,
                timeout=self._timeout,
                raise_for_status=False,
            )
        return self._session

    async def _fetch_search_form(self, session: aiohttp.ClientSession) -> Dict[str, str]:
        """GET the search page and extract ASP.NET viewstate / eventvalidation."""
        logger.debug("Fetching CSLB search form …")
        async with session.get(CSLB_SEARCH_URL) as resp:
            if resp.status != 200:
                body = await resp.text()
                raise CSLBScrapeError(f"Search form returned HTTP {resp.status}: {body[:200]}")

            html = await resp.text()
            soup = BeautifulSoup(html, "html.parser")

        data: Dict[str, str] = {}
        for name in (FORM_VIEWSTATE, FORM_EVENTVALIDATION, FORM_EVENTTARGET, FORM_EVENTARGUMENT):
            tag = soup.find("input", {"name": name})
            if tag and tag.get("value"):
                data[name] = tag["value"]
        return data

    async def _post_search(
        self, session: aiohttp.ClientSession, form_data: Dict[str, str]
    ) -> List[ScrapedCredentialRecord]:
        """POST the search form and parse results."""
        logger.debug("POSTing CSLB search form …")

        # aiohttp accepts plain dict for data=; no need for FormData here.
        async with session.post(CSLB_SEARCH_URL, data=form_data) as resp:
            if resp.status not in (200,):
                body = await resp.text()
                raise CSLBScrapeError(f"Search POST returned HTTP {resp.status}: {body[:200]}")

            html = await resp.text()
            return await self._parse_search_results(html)

    # ------------------------------------------------------------------
    # HTML Parsing
    # ------------------------------------------------------------------

    async def _parse_search_results(self, html: str) -> List[ScrapedCredentialRecord]:
        """Parse the CSLB search results page."""
        soup = BeautifulSoup(html, "html.parser")

        # Detect multiple results (table of links) vs single result (detail page)
        results_table = soup.find("table", {"id": "ContentPlaceHolder1_grdResults"})
        if results_table:
            return await self._parse_multi_results(soup)

        # Single detail page fallback
        detail = self._extract_detail_from_soup(soup)
        if detail:
            return [detail]

        logger.warning("No results found on CSLB search page.")
        return []

    async def _parse_multi_results(self, soup: BeautifulSoup) -> List[ScrapedCredentialRecord]:
        """Parse a results table with multiple rows."""
        records: List[ScrapedCredentialRecord] = []
        table = soup.find("table", {"id": "ContentPlaceHolder1_grdResults"})
        if not table:
            return records

        for row in table.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 3:
                continue

            # Try to extract a license number and a detail URL
            link = row.find("a", href=True)
            detail_url = None
            license_number = None
            if link:
                detail_url = link["href"]
                license_number = link.get_text(strip=True)

            # Fall back to plain text in first cell for license number
            if not license_number:
                license_number = cells[0].get_text(strip=True)

            business_name = cells[1].get_text(strip=True) if len(cells) > 1 else None
            classification = cells[2].get_text(strip=True) if len(cells) > 2 else None
            status_text = cells[3].get_text(strip=True) if len(cells) > 3 else None

            records.append(
                ScrapedCredentialRecord(
                    state_code=self.state_code,
                    credential_number=license_number or "",
                    credential_type=classification or "General Contractor",
                    issuing_state=self.state_name,
                    holder_name=business_name,
                    status=self._map_status(status_text),
                    external_source_url=detail_url,
                )
            )

        logger.info("Parsed %d results from CSLB multi-result page", len(records))
        return records

    def _extract_detail_from_soup(self, soup: BeautifulSoup) -> Optional[ScrapedCredentialRecord]:
        """Extract a single ScrapedCredentialRecord from a CSLB detail page."""
        # License number
        lic_tag = soup.find("span", {"id": "ContentPlaceHolder1_lblLicenseNumber"})
        license_number = lic_tag.get_text(strip=True) if lic_tag else None

        if not license_number:
            # Try alternative identifiers
            lic_tag = soup.find("span", string=re.compile(r"License\s*#?"))
            if lic_tag:
                license_number = lic_tag.get_text(strip=True)

        if not license_number:
            return None

        # Business name
        biz_tag = soup.find("span", {"id": "ContentPlaceHolder1_lblBusinessName"})
        business_name = biz_tag.get_text(strip=True) if biz_tag else None

        # Classification
        cls_tag = soup.find("span", {"id": "ContentPlaceHolder1_lblClassification"})
        classification = cls_tag.get_text(strip=True) if cls_tag else None

        # Status
        status_tag = soup.find("span", {"id": "ContentPlaceHolder1_lblStatus"})
        status_text = status_tag.get_text(strip=True) if status_tag else None

        # Issue date
        issue_tag = soup.find("span", {"id": "ContentPlaceHolder1_lblIssueDate"})
        issue_date = self._parse_date(issue_tag.get_text(strip=True)) if issue_tag else None

        # Expiration date
        exp_tag = soup.find("span", {"id": "ContentPlaceHolder1_lblExpirationDate"})
        expiration_date = self._parse_date(exp_tag.get_text(strip=True)) if exp_tag else None

        # Address
        addr_tag = soup.find("span", {"id": "ContentPlaceHolder1_lblAddress"})
        address = addr_tag.get_text(strip=True) if addr_tag else None

        # City / State / Zip
        city_tag = soup.find("span", {"id": "ContentPlaceHolder1_lblCityStateZip"})
        city, state, zip_code = self._parse_city_state_zip(city_tag.get_text(strip=True) if city_tag else "")

        # Bond info
        bond_tag = soup.find("span", {"id": "ContentPlaceHolder1_lblBondInfo"})
        bond_info = bond_tag.get_text(strip=True) if bond_tag else None

        # Disciplinary actions
        disc_tag = soup.find("span", {"id": "ContentPlaceHolder1_lblDisciplinaryActions"})
        disciplinary_actions: List[str] = []
        if disc_tag:
            for li in disc_tag.find_all("li"):
                txt = li.get_text(strip=True)
                if txt:
                    disciplinary_actions.append(txt)

        return ScrapedCredentialRecord(
            state_code=self.state_code,
            credential_number=license_number,
            credential_type=classification or "General Contractor",
            issuing_state=self.state_name,
            holder_name=business_name,
            holder_address=address,
            holder_city=city,
            holder_state=state,
            holder_zip=zip_code,
            issue_date=issue_date,
            expiration_date=expiration_date,
            status=self._map_status(status_text),
            bond_info=bond_info,
            classification=classification,
            disciplinary_actions=disciplinary_actions,
            raw_data={"source": "CSLB", "page_title": soup.title.get_text(strip=True) if soup.title else None},
        )

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

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
            "delinquent": "suspended",
        }
        return mapping.get(s, "active")

    @staticmethod
    def _parse_date(value: str) -> Optional[date]:
        if not value:
            return None
        for fmt in ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d", "%B %d, %Y"):
            try:
                return datetime.strptime(value.strip(), fmt).date()
            except ValueError:
                continue
        return None

    @staticmethod
    def _parse_city_state_zip(value: str) -> tuple:
        """Parse a string like 'Sacramento, CA 95814' into (city, state, zip)."""
        if not value:
            return None, None, None
        # Pattern: City, ST ZIP
        match = re.match(r"^(.*?),\s*([A-Z]{2})\s*(\d{5}(-\d{4})?)$", value.strip())
        if match:
            return match.group(1).strip(), match.group(2), match.group(3)
        # Fallback: just return the whole string as city
        return value.strip(), None, None

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()


class CSLBScrapeError(Exception):
    """Raised when the CSLB scraper encounters an unrecoverable error."""
    pass
