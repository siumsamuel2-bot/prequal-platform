"""Base class for state licensing board scrapers.

Defines the common interface that all state scrapers must implement.
Owner: Data Engineer
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional


@dataclass
class ScrapedCredentialRecord:
    """Normalized credential record returned by any state scraper."""

    state_code: str
    credential_number: str
    credential_type: str
    issuing_state: str
    holder_name: Optional[str] = None
    holder_address: Optional[str] = None
    holder_city: Optional[str] = None
    holder_state: Optional[str] = None
    holder_zip: Optional[str] = None
    issue_date: Optional[date] = None
    expiration_date: Optional[date] = None
    status: str = "active"
    external_source_id: Optional[str] = None
    external_source_url: Optional[str] = None
    disciplinary_actions: List[str] = field(default_factory=list)
    bond_info: Optional[str] = None
    classification: Optional[str] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)


class StateScraper(abc.ABC):
    """Abstract base class for state licensing board scrapers."""

    @property
    @abc.abstractmethod
    def state_code(self) -> str:
        """Two-letter state code (e.g. 'CA', 'TX')."""
        ...

    @property
    @abc.abstractmethod
    def state_name(self) -> str:
        """Full state name."""
        ...

    @abc.abstractmethod
    async def search_by_license_number(self, license_number: str) -> List[ScrapedCredentialRecord]:
        """Search by license number."""
        ...

    @abc.abstractmethod
    async def search_by_business_name(self, business_name: str) -> List[ScrapedCredentialRecord]:
        """Search by business name."""
        ...

    @abc.abstractmethod
    async def search_by_contractor_name(self, last_name: str, first_name: Optional[str] = None) -> List[ScrapedCredentialRecord]:
        """Search by contractor name."""
        ...

    @abc.abstractmethod
    async def close(self) -> None:
        """Release any network resources held by the scraper."""
        ...

    def _to_dict(self, record: ScrapedCredentialRecord) -> Dict[str, Any]:
        """Convert a ScrapedCredentialRecord to a plain dict for serialization."""
        return {
            "state_code": record.state_code,
            "credential_number": record.credential_number,
            "credential_type": record.credential_type,
            "issuing_state": record.issuing_state,
            "holder_name": record.holder_name,
            "holder_address": record.holder_address,
            "holder_city": record.holder_city,
            "holder_state": record.holder_state,
            "holder_zip": record.holder_zip,
            "issue_date": record.issue_date.isoformat() if record.issue_date else None,
            "expiration_date": record.expiration_date.isoformat() if record.expiration_date else None,
            "status": record.status,
            "external_source_id": record.external_source_id,
            "external_source_url": record.external_source_url,
            "disciplinary_actions": record.disciplinary_actions,
            "bond_info": record.bond_info,
            "classification": record.classification,
            "raw_data": record.raw_data,
        }
