"""Tests for state-level credential data validation.

Ensures that the validation logic in state_credential_validation.py
correctly rejects invalid records, normalizes good ones, and handles
edge cases (nulls, empty strings, bad dates).

Owner: Data Engineer
"""
from __future__ import annotations

import pytest
from datetime import date

from app.services.state_credential_validation import (
    validate_state_credential_record,
    StateCredentialValidationError,
)


class TestValidateStateCredentialRecord:
    def test_valid_record_passes(self):
        rec = {
            "state_code": "TX",
            "credential_number": "TX-EC-12345678",
            "credential_type": "Electrical Contractor",
            "status": "active",
            "issue_date": "2023-06-01",
            "expiration_date": "2025-05-31",
        }
        result = validate_state_credential_record(rec)
        assert result["state_code"] == "TX"
        assert result["credential_number"] == "TX-EC-12345678"
        assert result["credential_type"] == "Electrical Contractor"
        assert result["status"] == "active"
        assert result["issue_date"] == date(2023, 6, 1)
        assert result["expiration_date"] == date(2025, 5, 31)

    def test_missing_state_code_raises(self):
        rec = {
            "credential_number": "X123",
            "credential_type": "GC",
        }
        with pytest.raises(StateCredentialValidationError, match="state_code"):
            validate_state_credential_record(rec)

    def test_invalid_state_code_raises(self):
        rec = {"state_code": "TEX", "credential_number": "X", "credential_type": "Y"}
        with pytest.raises(StateCredentialValidationError, match="state_code"):
            validate_state_credential_record(rec)

    def test_missing_credential_number_raises(self):
        rec = {"state_code": "CA", "credential_type": "Y"}
        with pytest.raises(StateCredentialValidationError, match="credential_number"):
            validate_state_credential_record(rec)

    def test_missing_credential_type_raises(self):
        rec = {"state_code": "CA", "credential_number": "X"}
        with pytest.raises(StateCredentialValidationError, match="credential_type"):
            validate_state_credential_record(rec)

    def test_invalid_status_raises(self):
        rec = {
            "state_code": "CA",
            "credential_number": "X123",
            "credential_type": "GC",
            "status": "bogus",
        }
        with pytest.raises(StateCredentialValidationError, match="Invalid status"):
            validate_state_credential_record(rec)

    def test_expiration_before_issue_raises(self):
        rec = {
            "state_code": "NY",
            "credential_number": "NY-123",
            "credential_type": "Plumber",
            "issue_date": "2025-01-01",
            "expiration_date": "2024-01-01",
        }
        with pytest.raises(StateCredentialValidationError, match="expiration_date"):
            validate_state_credential_record(rec)

    def test_case_insensitive_state_code(self):
        rec = {
            "state_code": "ca",
            "credential_number": "CA-123",
            "credential_type": "General Contractor",
        }
        result = validate_state_credential_record(rec)
        assert result["state_code"] == "CA"

    def test_whitespace_trimmed(self):
        rec = {
            "state_code": "  FL  ",
            "credential_number": "  FL-123  ",
            "credential_type": "  Roofing  ",
        }
        result = validate_state_credential_record(rec)
        assert result["state_code"] == "FL"
        assert result["credential_number"] == "FL-123"
        assert result["credential_type"] == "Roofing"

    def test_none_status_defaults_to_active(self):
        rec = {
            "state_code": "IL",
            "credential_number": "IL-999",
            "credential_type": "HVAC",
        }
        result = validate_state_credential_record(rec)
        assert result["status"] == "active"

    def test_allows_none_dates(self):
        rec = {
            "state_code": "WA",
            "credential_number": "WA-001",
            "credential_type": "Painter",
            "issue_date": None,
            "expiration_date": None,
        }
        result = validate_state_credential_record(rec)
        assert result["issue_date"] is None
        assert result["expiration_date"] is None

    def test_rejects_bad_date_string(self):
        rec = {
            "state_code": "NV",
            "credential_number": "NV-001",
            "credential_type": "Electrician",
            "issue_date": "not-a-date",
        }
        with pytest.raises(StateCredentialValidationError, match="Invalid date"):
            validate_state_credential_record(rec)

    def test_accepts_date_objects(self):
        rec = {
            "state_code": "CO",
            "credential_number": "CO-001",
            "credential_type": "Mason",
            "issue_date": date(2022, 1, 15),
            "expiration_date": date(2024, 1, 15),
        }
        result = validate_state_credential_record(rec)
        assert result["issue_date"] == date(2022, 1, 15)
        assert result["expiration_date"] == date(2024, 1, 15)
