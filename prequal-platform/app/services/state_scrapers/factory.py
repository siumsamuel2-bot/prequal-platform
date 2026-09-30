"""Scraper factory — dispatches to the correct state scraper.

Owner: Data Engineer
"""
from __future__ import annotations

from typing import Dict, Optional, Type

from .base import StateScraper
from .ca_cslb import CSLBScraper
from .tx_tdlr import TX_TDLR_Scraper

# Registry of scrapers by state code
_SCRAPER_REGISTRY: Dict[str, Type[StateScraper]] = {
    "CA": CSLBScraper,
    "TX": TX_TDLR_Scraper,
}


def get_scraper(state_code: str) -> Optional[StateScraper]:
    """Return a scraper instance for the given state code, or None."""
    scraper_cls = _SCRAPER_REGISTRY.get(state_code.upper())
    if scraper_cls:
        return scraper_cls()
    return None


def list_supported_states() -> list[str]:
    """Return a list of state codes with scraper support."""
    return list(_SCRAPER_REGISTRY.keys())


def register_scraper(state_code: str, scraper_cls: Type[StateScraper]) -> None:
    """Register a new scraper for a state code."""
    _SCRAPER_REGISTRY[state_code.upper()] = scraper_cls
