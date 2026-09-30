"""Tests for state licensing board scrapers (CA & TX).

Mocks the live HTTP layer and validates HTML parsing with real-world data shapes.
"""
from __future__ import annotations

from typing import Any, List
from unittest.mock import AsyncMock, patch

import pytest

from app.services.state_scrapers.ca_cslb import CSLBScraper
from app.services.state_scrapers.tx_tdlr import TX_TDLR_Scraper
from app.services.state_scrapers.base import ScrapedCredentialRecord


# ---------------------------------------------------------------------------
# CSLB HTML fixtures
# ---------------------------------------------------------------------------

def _cslb_multi_result_html() -> str:
    """Return a snippet of CSLB multi-result page HTML."""
    return """
    <html>
    <body>
    <table id="ContentPlaceHolder1_grdResults">
        <tr><th>License #</th><th>Business Name</th><th>Classification</th><th>Status</th></tr>
        <tr>
            <td><a href="/detail/123456">123456</a></td>
            <td>Acme Construction Inc</td>
            <td>B-General Building Contractor</td>
            <td>Active</td>
        </tr>
        <tr>
            <td><a href="/detail/789012">789012</a></td>
            <td>Wilson Electric</td>
            <td>C-10 Electrical</td>
            <td>Suspended</td>
        </tr>
    </table>
    </body>
    </html>
    """


def _cslb_detail_html() -> str:
    """Return a snippet of CSLB single detail page HTML."""
    return """
    <html>
    <body>
        <span id="ContentPlaceHolder1_lblLicenseNumber">987654</span>
        <span id="ContentPlaceHolder1_lblBusinessName">Green Valley Builders LLC</span>
        <span id="ContentPlaceHolder1_lblClassification">B-General Building Contractor</span>
        <span id="ContentPlaceHolder1_lblStatus">Active</span>
        <span id="ContentPlaceHolder1_lblIssueDate">01/15/2022</span>
        <span id="ContentPlaceHolder1_lblExpirationDate">01/15/2026</span>
        <span id="ContentPlaceHolder1_lblAddress">123 Builder Way</span>
        <span id="ContentPlaceHolder1_lblCityStateZip">Sacramento, CA 95814</span>
        <span id="ContentPlaceHolder1_lblBondInfo">$15,000 Bond</span>
        <span id="ContentPlaceHolder1_lblDisciplinaryActions">
            <ul><li>Probation – 2023</li></ul>
        </span>
    </body>
    </html>
    """


# ---------------------------------------------------------------------------
# TDLR HTML fixtures
# ---------------------------------------------------------------------------

def _tdlr_results_html() -> str:
    """Return a snippet of TDLR results page HTML."""
    return """
    <html>
    <body>
    <table class="results">
        <tr><th>License</th><th>Name</th><th>Type</th><th>Status</th></tr>
        <tr>
            <td>EC-123456</td>
            <td>Ace Electric LLC</td>
            <td>Electrical Contractor</td>
            <td>Active</td>
        </tr>
        <tr>
            <td>GC-789012</td>
            <td>Build Right Inc</td>
            <td>General Contractor</td>
            <td>Expired</td>
        </tr>
    </table>
    </body>
    </html>
    """


def _tdlr_detail_html() -> str:
    """Return a snippet of TDLR detail page HTML."""
    return """
    <html>
    <body>
        <span id="lblLicense">GC-999888</span>
        <span id="lblBusinessName">Top Notch Construction</span>
        <span id="lblType">General Contractor</span>
        <span id="lblStatus">Active</span>
        <span id="lblExpiration">12/31/2025</span>
        <span id="lblAddress">456 Main St</span>
        <span id="lblCity">Austin</span>
        <span id="lblZip">78701</span>
    </body>
    </html>
    """


# ---------------------------------------------------------------------------
# CSLB Scraper Tests
# ---------------------------------------------------------------------------

class TestCSLBScraper:
    @pytest.mark.asyncio
    async def test_search_by_license_number_multi_results(self):
        scraper = CSLBScraper()
        expected = await scraper._parse_search_results(_cslb_multi_result_html())
        with patch.object(scraper, "_fetch_search_form", new=AsyncMock(return_value={})):
            with patch.object(scraper, "_post_search", new=AsyncMock(return_value=expected)):
                records = await scraper.search_by_license_number("123456")
        assert len(records) == 2
        assert records[0].credential_number == "123456"
        assert records[0].holder_name == "Acme Construction Inc"
        assert records[0].status == "active"
        assert records[1].credential_number == "789012"
        assert records[1].status == "suspended"

    @pytest.mark.asyncio
    async def test_search_by_business_name_detail_page(self):
        scraper = CSLBScraper()
        expected = await scraper._parse_search_results(_cslb_detail_html())
        with patch.object(scraper, "_fetch_search_form", new=AsyncMock(return_value={})):
            with patch.object(scraper, "_post_search", new=AsyncMock(return_value=expected)):
                records = await scraper.search_by_business_name("Green Valley")
        assert len(records) == 1
        rec = records[0]
        assert rec.credential_number == "987654"
        assert rec.holder_name == "Green Valley Builders LLC"
        assert rec.classification == "B-General Building Contractor"
        assert rec.status == "active"
        assert rec.issue_date.year == 2022
        assert rec.expiration_date.year == 2026
        assert rec.holder_address == "123 Builder Way"
        assert rec.holder_city == "Sacramento"
        assert rec.holder_state == "CA"
        assert rec.holder_zip == "95814"
        assert rec.bond_info == "$15,000 Bond"
        assert rec.disciplinary_actions == ["Probation – 2023"]

    @pytest.mark.asyncio
    async def test_empty_results(self):
        scraper = CSLBScraper()
        expected = await scraper._parse_search_results("<html><body></body></html>")
        with patch.object(scraper, "_fetch_search_form", new=AsyncMock(return_value={})):
            with patch.object(scraper, "_post_search", new=AsyncMock(return_value=expected)):
                records = await scraper.search_by_business_name("NonExistent")
        assert records == []


# ---------------------------------------------------------------------------
# TDLR Scraper Tests
# ---------------------------------------------------------------------------

class TestTX_TDLR_Scraper:
    @pytest.mark.asyncio
    async def test_search_by_business_name_results(self):
        scraper = TX_TDLR_Scraper()
        expected = scraper._parse_results(_tdlr_results_html())
        with patch.object(scraper, "_post_search", new=AsyncMock(return_value=_tdlr_results_html())):
            records = await scraper.search_by_business_name("Ace")
        # The search_by_business_name calls _parse_results on the returned html
        # So we need to mock _post_search to return the html string
        assert len(records) == 2
        assert records[0].credential_number == "EC-123456"
        assert records[0].holder_name == "Ace Electric LLC"
        assert records[0].status == "active"
        assert records[1].credential_number == "GC-789012"
        assert records[1].status == "expired"

    @pytest.mark.asyncio
    async def test_search_by_license_number_detail(self):
        scraper = TX_TDLR_Scraper()
        expected = scraper._parse_results(_tdlr_detail_html())
        with patch.object(scraper, "_post_search", new=AsyncMock(return_value=_tdlr_detail_html())):
            records = await scraper.search_by_license_number("GC-999888取景")
        assert len(records) == 1
        rec = records[0]
        assert rec.credential_number == "GC-999888"
        assert rec.holder_name == "Top Notch Construction"
        assert rec.status == "active"
        assert rec.expiration_date.year == 2025
        assert rec.holder_address == "456 Main St"
        assert rec.holder_city == "Austin"
        assert rec.holder_zip == "78701"

    @pytest.mark.asyncio
    async def test_empty_results(self):
        scraper = TX_TDLR_Scraper()
        with patch.object(scraper, "_post_search", new=AsyncMock(return_value="<html><body></body></html>")):
            records = await scraper.search_by_business_name("NoMatch")
        assert records == []

