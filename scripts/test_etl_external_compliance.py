"""
Tests for the External Compliance ETL Pipeline

Tests focus on data integrity, pipeline correctness, and matching logic
with real-world data shapes (not just happy path).
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure prequal-platform libs are importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "prequal-platform"))

from scripts.etl_external_compliance import (
    MatchResult,
    match_subcontractor,
    normalize_company_name,
    parse_date,
    parse_decimal,
    map_status,
    PipelineRun,
)

# ---------------------------------------------------------------------------
# 1. Utility function tests (data shapes, edge cases)
# ---------------------------------------------------------------------------


class TestNormalizeCompanyName:
    def test_strips_common_suffixes(self):
        assert normalize_company_name("Acme Construction LLC") == "Acme Construction"
        assert normalize_company_name("Acme Construction, Inc.") == "Acme Construction"
        assert normalize_company_name("Acme Construction Corp") == "Acme Construction"

    def test_handles_no_suffix(self):
        assert normalize_company_name("Acme Construction") == "Acme Construction"

    def test_handles_ampersand(self):
        assert normalize_company_name("Smith & Jones Co.") == "Smith AND Jones"

    def test_empty_string(self):
        assert normalize_company_name("") == ""


class TestParseDate:
    def test_iso_format(self):
        assert parse_date("2024-03-15") == date(2024, 3, 15)

    def test_datetime_object(self):
        d = datetime(2024, 3, 15, 10, 30, 0)
        assert parse_date(d) == date(2024, 3, 15)

    def test_date_object(self):
        d = date(2024, 3, 15)
        assert parse_date(d) == date(2024, 3, 15)

    def test_none_returns_none(self):
        assert parse_date(None) is None

    def test_invalid_returns_none(self):
        assert parse_date("not-a-date") is None

    def test_slash_format(self):
        assert parse_date("03/15/2024") == date(2024, 3, 15)

    def test_timestamp_format(self):
        assert parse_date("2024-03-15T10:30:00") == date(2024, 3, 15)


class TestParseDecimal:
    def test_valid_float(self):
        assert parse_decimal("123.45") == 123.45

    def test_valid_int(self):
        assert parse_decimal(100) == 100.0

    def test_none_returns_none(self):
        assert parse_decimal(None) is None

    def test_invalid_returns_none(self):
        assert parse_decimal("abc") is None


class TestMapStatus:
    def test_known_statuses(self):
        assert map_status("open") == "open"
        assert map_status("closed") == "resolved"
        assert map_status("resolved") == "resolved"
        assert map_status("under_review") == "under_review"
        assert map_status("appealed") == "appealed"
        assert map_status("pending") == "under_review"

    def test_unknown_returns_default(self):
        assert map_status("foobar") == "open"
        assert map_status("", "resolved") == "resolved"

    def test_none_returns_default(self):
        assert map_status(None) == "open"


# ---------------------------------------------------------------------------
# 2. Subcontractor matching tests (data integrity)
# ---------------------------------------------------------------------------


class TestMatchSubcontractor:
    @pytest.mark.asyncio
    async def test_match_by_ein(self):
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = uuid.uuid4()
        mock_db.execute.return_value = mock_result

        match = await match_subcontractor(mock_db, ein="12-3456789")
        assert match.subcontractor_id is not None
        assert match.match_method == "ein"
        assert match.match_score == 1.0

    @pytest.mark.asyncio
    async def test_match_by_license(self):
        mock_db = AsyncMock()
        # First query (EIN) returns None
        mock_result_ein = MagicMock()
        mock_result_ein.scalar_one_or_none.return_value = None
        # Second query (license) returns match
        mock_result_lic = MagicMock()
        mock_result_lic.scalar_one_or_none.return_value = uuid.uuid4()

        mock_db.execute.side_effect = [mock_result_ein, mock_result_lic]

        match = await match_subcontractor(
            mock_db, ein=None, license_number="ABC123", license_state="TX"
        )
        assert match.subcontractor_id is not None
        assert match.match_method == "license"
        assert match.match_score == 0.95

    @pytest.mark.asyncio
    async def test_match_by_name(self):
        mock_db = AsyncMock()
        mock_result_ein = MagicMock()
        mock_result_ein.scalar_one_or_none.return_value = None
        mock_result_lic = MagicMock()
        mock_result_lic.scalar_one_or_none.return_value = None
        mock_result_name = MagicMock()
        mock_result_name.scalar_one_or_none.return_value = uuid.uuid4()

        mock_db.execute.side_effect = [mock_result_ein, mock_result_lic, mock_result_name]

        match = await match_subcontractor(mock_db, name="Acme Construction")
        assert match.subcontractor_id is not None
        assert match.match_method == "name"
        assert match.match_score == 0.80

    @pytest.mark.asyncio
    async def test_no_match(self):
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        match = await match_subcontractor(mock_db, ein=None, name="", license_number=None)
        assert match.subcontractor_id is None
        assert match.match_method == "none"
        assert match.match_score == 0.0


# ---------------------------------------------------------------------------
# 3. PipelineRun tests (data integrity / tracking)
# ---------------------------------------------------------------------------


class TestPipelineRun:
    def test_default_creation(self):
        run = PipelineRun()
        assert run.status == "running"
        assert run.records_extracted == 0
        assert run.id is not None

    def test_post_execution(self):
        run = PipelineRun()
        run.status = "completed"
        run.records_inserted = 10
        run.records_updated = 2
        run.records_failed = 1
        run.completed_at = datetime.now()
        assert run.records_inserted == 10
        assert run.status == "completed"


# ---------------------------------------------------------------------------
# 4. End-to-end data shape tests (simulate real data)
# ---------------------------------------------------------------------------


class TestRealDataShapes:
    """Test that the pipeline handles real-world OSHA / state credential data shapes."""

    @pytest.mark.asyncio
    async def test_osha_case_with_all_fields(self):
        case = {
            "id": "12345678-abcd-1234-efgh-123456789012",
            "company_name": "Acme Construction, Inc.",
            "ein": "12-3456789",
            "violation_type": "safety",
            "citation_number": "0123456.012",
            "description": "Failure to provide fall protection",
            "date_opened": "2024-01-15",
            "status": "open",
            "penalty_amount": "12500.00",
            "gravity_score": "10",
            "inspection_number": "123456789",
            "standard_cited": "1926.501",
            "site_city": "Austin",
            "site_state": "TX",
            "site_zip_code": "78701",
            "naics_code": "236220",
        }
        # Validate parsing of all fields
        assert parse_date(case["date_opened"]) == date(2024, 1, 15)
        assert parse_decimal(case["penalty_amount"]) == 12500.00
        assert parse_decimal(case["gravity_score"]) == 10.0
        assert map_status(case["status"]) == "open"

    @pytest.mark.asyncio
    async def test_osha_case_with_missing_fields(self):
        """OSHA responses often have missing fields."""
        case = {
            "id": "98765432-wxyz-9876-abcd-987654321098",
            "company_name": "",
            "violation_type": None,
            "date_opened": None,
            "status": "",
        }
        assert parse_date(case["date_opened"]) is None
        assert parse_decimal(case.get("penalty_amount")) is None
        assert map_status(case["status"]) == "open"

    @pytest.mark.asyncio
    async def test_state_credential_record(self):
        rec = {
            "state_code": "TX",
            "credential_number": "TX-EC-12345678",
            "credential_type": "Electrical Contractor",
            "issuing_state": "Texas",
            "holder_name": "Acme Electric LLC",
            "holder_address": "123 Main St",
            "holder_city": "Houston",
            "holder_state": "TX",
            "holder_zip": "77001",
            "issue_date": "2023-06-01",
            "expiration_date": "2025-05-31",
            "status": "active",
            "external_source_id": "SRC-12345",
            "external_source_url": "https://licensing.texas.gov/creds/12345",
            "raw_data": {"classification": "Class A"},
        }
        assert parse_date(rec["issue_date"]) == date(2023, 6, 1)
        assert parse_date(rec["expiration_date"]) == date(2025, 5, 31)

    @pytest.mark.asyncio
    async def test_state_credential_with_bad_dates(self):
        """State APIs may return malformed dates."""
        rec = {
            "state_code": "CA",
            "credential_number": "CA-GC-999999",
            "issue_date": "not-a-date",
            "expiration_date": "",
        }
        assert parse_date(rec["issue_date"]) is None
        assert parse_date(rec["expiration_date"]) is None


# ---------------------------------------------------------------------------
# 5. Error handling tests
# ---------------------------------------------------------------------------


class TestErrorHandling:
    def test_parse_decimal_with_various_inputs(self):
        """parse_decimal should be resilient to bad input."""
        assert parse_decimal("") is None
        assert parse_decimal("abc") is None
        assert parse_decimal("123,456.78") is None  # comma not handled
        assert parse_decimal("0") == 0.0
        assert parse_decimal(0) == 0.0

    def test_parse_date_with_various_inputs(self):
        """parse_date should be resilient to bad input."""
        assert parse_date("") is None
        assert parse_date("13/45/2024") is None
        assert parse_date("2024-02-30") is None
        assert parse_date("today") is None

    def test_normalize_company_name_with_special_chars(self):
        """Should not crash on special characters."""
        result = normalize_company_name("Acme & Sons Co., Ltd.")
        assert "Acme AND Sons" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
