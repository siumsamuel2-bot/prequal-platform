"""Tests for compliance data deduplication and matching validation.

Covers:
- Fuzzy string matching (Jaro-Winkler)
- Duplicate detection across OSHA and state credential records
- Matching accuracy validation against real data shapes
- Normalization edge cases

Owner: Data Engineer
"""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.compliance_matching import (
    jaro_winkler,
    normalize_text,
    normalize_ein,
    normalize_license,
    is_potential_duplicate,
    find_duplicates,
    parse_iso_date,
    DuplicateCheckResult,
)

# ---------------------------------------------------------------------------
# 1. String normalization tests
# ---------------------------------------------------------------------------


class TestNormalizeText:
    def test_basic(self):
        assert normalize_text("  Acme Construction  ") == "ACME CONSTRUCTION"

    def test_multiple_spaces(self):
        assert normalize_text("Acme   Construction") == "ACME CONSTRUCTION"

    def test_empty(self):
        assert normalize_text("") == ""
        assert normalize_text(None) == ""  # type: ignore[arg-type]


class TestNormalizeEIN:
    def test_standard_format(self):
        assert normalize_ein("12-3456789") == "12-3456789"

    def test_no_dash(self):
        assert normalize_ein("123456789") == "12-3456789"

    def test_with_spaces(self):
        assert normalize_ein(" 12-3456789 ") == "12-3456789"

    def test_invalid(self):
        assert normalize_ein("not-an-ein") == "NOT-AN-EIN"
        assert normalize_ein("12345") == "12345"

    def test_empty(self):
        assert normalize_ein("") == ""
        assert normalize_ein(None) == ""  # type: ignore[arg-type]


class TestNormalizeLicense:
    def test_basic(self):
        assert normalize_license(" abc-123 ") == "ABC-123"

    def test_empty(self):
        assert normalize_license("") == ""


# ---------------------------------------------------------------------------
# 2. Jaro-Winkler similarity tests
# ---------------------------------------------------------------------------


class TestJaroWinkler:
    def test_identical_strings(self):
        assert jaro_winkler("ACME", "ACME") == 1.0

    def test_completely_different(self):
        assert jaro_winkler("ACME", "XYZW") < 0.5

    def test_typo(self):
        sim = jaro_winkler("ACME CONSTRUCTION", "ACEM CONSTRUCTION")
        assert sim > 0.8  # Should be high for transposition

    def test_empty(self):
        assert jaro_winkler("", "") == 0.0
        assert jaro_winkler("", "ACME") == 0.0

    def test_common_prefix_boost(self):
        # Jaro-Winkler gives extra score for common prefix
        sim1 = jaro_winkler("ACME BUILDERS", "ACME CONSTRUCTION")
        sim2 = jaro_winkler("BUILDERS ACME", "ACME CONSTRUCTION")
        assert sim1 > sim2  # Common prefix should help


# ---------------------------------------------------------------------------
# 3. Duplicate detection tests
# ---------------------------------------------------------------------------


class TestIsPotentialDuplicate:
    def test_exact_osha_id(self):
        rec1 = {"id": "a", "osha_violation_id": "V12345"}
        rec2 = {"id": "b", "osha_violation_id": "V12345"}
        result = is_potential_duplicate(rec1, rec2)
        assert result.is_duplicate is True
        assert "OSHA violation ID" in result.reason

    def test_different_osha_ids(self):
        rec1 = {"id": "a", "osha_violation_id": "V12345"}
        rec2 = {"id": "b", "osha_violation_id": "V67890"}
        result = is_potential_duplicate(rec1, rec2)
        assert result.is_duplicate is False

    def test_same_credential(self):
        rec1 = {"id": "a", "credential_number": "TX-EC-123", "state_code": "TX"}
        rec2 = {"id": "b", "credential_number": "TX-EC-123", "state_code": "TX"}
        result = is_potential_duplicate(rec1, rec2)
        assert result.is_duplicate is True
        assert "credential number" in result.reason

    def test_same_ein_and_date(self):
        rec1 = {"id": "a", "ein": "12-3456789", "issued_date": "2024-01-15"}
        rec2 = {"id": "b", "ein": "12-3456789", "issued_date": "2024-01-15"}
        result = is_potential_duplicate(rec1, rec2)
        assert result.is_duplicate is True
        assert "EIN" in result.reason

    def test_fuzzy_name_and_date(self):
        rec1 = {"id": "a", "company_name": "Acme Construction LLC", "issued_date": "2024-01-15"}
        rec2 = {"id": "b", "company_name": "Acme Construction LLC", "issued_date": "2024-01-15"}
        result = is_potential_duplicate(rec1, rec2)
        assert result.is_duplicate is True

    def test_no_match(self):
        rec1 = {"id": "a", "company_name": "Acme Construction", "issued_date": "2024-01-15"}
        rec2 = {"id": "b", "company_name": "XYZ Builders", "issued_date": "2024-03-20"}
        result = is_potential_duplicate(rec1, rec2)
        assert result.is_duplicate is False

    def test_missing_dates(self):
        rec1 = {"id": "a", "company_name": "Acme Construction", "issued_date": None}
        rec2 = {"id": "b", "company_name": "Acme Construction", "issued_date": None}
        result = is_potential_duplicate(rec1, rec2)
        # Without dates, fuzzy name only is not enough
        assert result.is_duplicate is False


class TestFindDuplicates:
    def test_finds_duplicates(self):
        records = [
            {"id": "1", "osha_violation_id": "V12345"},
            {"id": "2", "osha_violation_id": "V12345"},  # duplicate
            {"id": "3", "osha_violation_id": "V67890"},
        ]
        unique, duplicates = find_duplicates(records)
        assert len(unique) == 2
        assert len(duplicates) == 1
        assert duplicates[0]["id"] == "2"

    def test_all_unique(self):
        records = [
            {"id": "1", "osha_violation_id": "V11111"},
            {"id": "2", "osha_violation_id": "V22222"},
            {"id": "3", "osha_violation_id": "V33333"},
        ]
        unique, duplicates = find_duplicates(records)
        assert len(unique) == 3
        assert len(duplicates) == 0

    def test_empty_list(self):
        unique, duplicates = find_duplicates([])
        assert len(unique) == 0
        assert len(duplicates) == 0


# ---------------------------------------------------------------------------
# 4. Date parsing tests
# ---------------------------------------------------------------------------


class TestParseISODate:
    def test_iso_string(self):
        assert parse_iso_date("2024-03-15") == date(2024, 3, 15)

    def test_datetime_object(self):
        from datetime import datetime
        d = datetime(2024, 3, 15, 10, 30, 0)
        assert parse_iso_date(d) == date(2024, 3, 15)

    def test_date_object(self):
        d = date(2024, 3, 15)
        assert parse_iso_date(d) == date(2024, 3, 15)

    def test_none(self):
        assert parse_iso_date(None) is None

    def test_invalid(self):
        assert parse_iso_date("not-a-date") is None
        assert parse_iso_date("13/45/2024") is None


# ---------------------------------------------------------------------------
# 5. Real data shape tests
# ---------------------------------------------------------------------------


class TestRealDataShapes:
    """Test with real-world OSHA / state credential record shapes."""

    def test_osha_record_with_all_fields(self):
        rec = {
            "id": "abc-123",
            "osha_violation_id": "V-2024-001",
            "company_name": "Acme Construction, Inc.",
            "ein": "12-3456789",
            "issued_date": "2024-01-15",
            "penalty_amount": "12500.00",
        }
        assert normalize_ein(rec["ein"]) == "12-3456789"
        assert parse_iso_date(rec["issued_date"]) == date(2024, 1, 15)

    def test_state_credential_with_fuzzy_name(self):
        rec1 = {
            "id": "a",
            "credential_number": "TX-EC-12345678",
            "holder_name": "Acme Electric LLC",
            "state_code": "TX",
            "issued_date": "2023-06-01",
        }
        rec2 = {
            "id": "b",
            "credential_number": "TX-EC-12345678",
            "holder_name": "Acme Electric Limited Liability Co",
            "state_code": "TX",
            "issued_date": "2023-06-01",
        }
        result = is_potential_duplicate(rec1, rec2)
        assert result.is_duplicate is True  # Same credential number

    def test_different_companies_same_date(self):
        rec1 = {"id": "a", "company_name": "Acme Construction", "issued_date": "2024-01-15"}
        rec2 = {"id": "b", "company_name": "XYZ Builders", "issued_date": "2024-01-15"}
        result = is_potential_duplicate(rec1, rec2)
        assert result.is_duplicate is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
