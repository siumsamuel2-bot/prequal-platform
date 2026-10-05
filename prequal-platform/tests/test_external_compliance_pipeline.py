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

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.external_compliance_pipeline import (
    MatchResult,
    OSHARecordValidationError,
    check_batch_health,
    get_pipeline_health_summary,
    match_subcontractor,
    normalize_company_name,
    parse_date,
    parse_decimal,
    map_status,
    validate_osha_case_record,
    PipelineRun,
    run_state_credential_sync,
    cleanup_stale_runs,
    validate_pipeline_health,
    STALE_RUN_TIMEOUT_HOURS,
    BATCH_LATENCY_MAX_MS,
)
from app.services.state_scrapers.base import ScrapedCredentialRecord

# ---------------------------------------------------------------------------
# 1. Utility function tests (data shapes, edge cases)
# ---------------------------------------------------------------------------


class TestNormalizeCompanyName:
    def test_strips_common_suffixes(self):
        assert normalize_company_name("Acme Construction LLC") == "ACME CONSTRUCTION"
        assert normalize_company_name("Acme Construction, Inc.") == "ACME CONSTRUCTION"
        assert normalize_company_name("Acme Construction Corp") == "ACME CONSTRUCTION"

    def test_handles_no_suffix(self):
        assert normalize_company_name("Acme Construction") == "ACME CONSTRUCTION"

    def test_handles_ampersand(self):
        # "CO" is a recognized suffix and is stripped by normalize_company_name
        assert normalize_company_name("Smith & Jones Co.") == "SMITH AND JONES"

    def test_empty_string(self):
        assert normalize_company_name("") == ""


class TestParseDate:
    def test_iso_format(self):
        assert parse_date("2024-03-15") == date(2024, 3, 15)

    def test_datetime_object(self):
        d = datetime(2024, 3, 15, 10, 30, 0)
        assert parse_date(d) == d

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
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = uuid.uuid4()
        mock_db.execute.return_value = mock_result

        match = await match_subcontractor(
            mock_db, license_number="ABC123", license_state="TX"
        )
        assert match.subcontractor_id is not None
        assert match.match_method == "license"
        assert match.match_score == 0.95

    @pytest.mark.asyncio
    async def test_match_by_name(self):
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = uuid.uuid4()
        mock_db.execute.return_value = mock_result

        match = await match_subcontractor(mock_db, name="Acme Construction")
        assert match.subcontractor_id is not None
        assert match.match_method == "name"
        assert match.match_score == 0.80

    @pytest.mark.asyncio
    async def test_no_match(self):
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.side_effect = [mock_result] * 3

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
        assert "ACME AND SONS" in result


# ---------------------------------------------------------------------------
# 6. State-credential sync tests (safe pipeline behaviour)
# ---------------------------------------------------------------------------

class TestRunStateCredentialSync:
    @pytest.mark.asyncio
    async def test_search_query_path(self):
        """When search_query is provided, scraper.search_by_business_name is used."""
        mock_db = AsyncMock()
        mock_scraper = AsyncMock()
        mock_scraper.search_by_business_name = AsyncMock(
            return_value=[
                ScrapedCredentialRecord(
                    state_code="CA",
                    credential_number="123456",
                    credential_type="B-General Building Contractor",
                    issuing_state="California",
                    holder_name="Acme Construction Inc",
                    status="active",
                )
            ]
        )
        with patch(
            "app.services.external_compliance_pipeline.get_scraper",
            return_value=mock_scraper,
        ):
            run = await run_state_credential_sync(
                db=mock_db, state_code="CA", search_query="Acme"
            )
        assert run.status == "completed"
        assert run.records_extracted == 1
        mock_scraper.search_by_business_name.assert_awaited_once_with("Acme")

    @pytest.mark.asyncio
    async def test_db_driven_sync_path(self):
        """When search_query is empty, pipeline looks up active subcontractors."""
        mock_db = AsyncMock()
        # Return two active subcontractors for CA
        mock_result = MagicMock()
        mock_result.all.return_value = [
            ("Acme Construction Inc", "123456"),
            ("Top Notch Builders", None),
        ]
        mock_db.execute.return_value = mock_result

        mock_scraper = AsyncMock()
        mock_scraper.search_by_license_number = AsyncMock(return_value=[])
        mock_scraper.search_by_business_name = AsyncMock(return_value=[])

        with patch(
            "app.services.external_compliance_pipeline.get_scraper",
            return_value=mock_scraper,
        ):
            run = await run_state_credential_sync(
                db=mock_db, state_code="CA", max_results=10
            )
        assert run.status == "completed"
        mock_scraper.search_by_license_number.assert_awaited_once_with("123456")
        mock_scraper.search_by_business_name.assert_awaited_once_with(
            "Top Notch Builders"
        )

    @pytest.mark.asyncio
    async def test_skip_when_no_source(self):
        """When neither scraper nor API is configured, sync is skipped."""
        mock_db = AsyncMock()
        with patch(
            "app.services.external_compliance_pipeline.get_scraper",
            return_value=None,
        ):
            with patch.dict("os.environ", {}, clear=True):
                run = await run_state_credential_sync(
                    db=mock_db, state_code="FL"
                )
        assert run.status == "skipped"


# ---------------------------------------------------------------------------
# 7. Stale run cleanup and health validation tests
# ---------------------------------------------------------------------------


class TestCleanupStaleRuns:
    @pytest.mark.asyncio
    async def test_cleanup_marks_stale_runs_as_failed(self):
        """Runs that have been running longer than STALE_RUN_TIMEOUT_HOURS should be marked failed."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            (uuid.uuid4(), "osha_daily_sync", datetime(2026, 6, 20, 0, 0, 0)),
            (uuid.uuid4(), "state_creds_CA", datetime(2026, 6, 20, 0, 0, 0)),
        ]
        mock_db.execute.return_value = mock_result

        cleaned = await cleanup_stale_runs(mock_db)

        assert cleaned == 2
        mock_db.execute.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_returns_zero_when_no_stale_runs(self):
        """When there are no stale runs, cleanup should return 0."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result

        cleaned = await cleanup_stale_runs(mock_db)

        assert cleaned == 0
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_pipeline_health_includes_stale_runs_cleaned(self):
        """validate_pipeline_health should call cleanup_stale_runs and include the count."""
        mock_db = AsyncMock()

        mock_result_count = MagicMock()
        mock_result_count.scalar.return_value = 5

        stale_result = MagicMock()
        stale_result.fetchall.return_value = [(uuid.uuid4(), "test_job", datetime.now())]

        mock_db.execute.side_effect = [stale_result, mock_result_count, mock_result_count, mock_result_count, mock_result_count]

        checks = await validate_pipeline_health(mock_db)

        assert "stale_runs_cleaned" in checks
        assert "unmatched_osha_violations" in checks
        assert "unmatched_state_credentials" in checks
        assert "stale_running_jobs" in checks
        assert "failed_jobs_last_7d" in checks


class TestSTALE_RUN_TIMEOUT_HOURS:
    def test_stale_timeout_config_default(self):
        """STALE_RUN_TIMEOUT_HOURS should default to 2 hours for faster failure detection."""
        assert STALE_RUN_TIMEOUT_HOURS == 2


# ---------------------------------------------------------------------------
# 8. OSHA record validation gate (MID-613)
# ---------------------------------------------------------------------------


class TestValidateOSHARecord:
    VALID = {
        "id": "12345678-abcd-1234-efgh-123456789012",
        "company_name": "Acme Construction, Inc.",
        "date_opened": "2024-01-15",
        "penalty_amount": "12500.00",
        "gravity_score": "10",
    }

    def test_valid_record_returns_canonical_id(self):
        assert validate_osha_case_record(self.VALID) == self.VALID["id"]

    def test_accepts_violation_id_fallback(self):
        rec = {**self.VALID, "id": None, "violation_id": "VIOL-1"}
        assert validate_osha_case_record(rec) == "VIOL-1"

    def test_missing_id_rejected(self):
        with pytest.raises(OSHARecordValidationError):
            validate_osha_case_record({"company_name": "Acme"})

    def test_oversized_id_rejected(self):
        with pytest.raises(OSHARecordValidationError):
            validate_osha_case_record({**self.VALID, "id": "x" * 65})

    def test_no_identity_signal_rejected(self):
        rec = {**self.VALID}
        rec.pop("company_name")
        with pytest.raises(OSHARecordValidationError):
            validate_osha_case_record(rec)

    def test_ein_counts_as_identity(self):
        rec = {**self.VALID}
        rec.pop("company_name")
        rec["ein"] = "12-3456789"
        assert validate_osha_case_record(rec) == self.VALID["id"]

    def test_unparseable_date_rejected(self):
        with pytest.raises(OSHARecordValidationError):
            validate_osha_case_record({**self.VALID, "date_opened": "13/45/2024"})

    def test_slash_format_date_accepted(self):
        assert validate_osha_case_record({**self.VALID, "date_opened": "01/15/2024"})

    def test_negative_penalty_rejected(self):
        with pytest.raises(OSHARecordValidationError):
            validate_osha_case_record({**self.VALID, "penalty_amount": "-5"})

    def test_non_numeric_gravity_rejected(self):
        with pytest.raises(OSHARecordValidationError):
            validate_osha_case_record({**self.VALID, "gravity_score": "high"})

    def test_missing_optional_fields_accepted(self):
        rec = {"id": "12345678", "company_name": "Acme"}
        assert validate_osha_case_record(rec) == "12345678"


# ---------------------------------------------------------------------------
# 9. Match threshold enforcement (MID-613)
# ---------------------------------------------------------------------------


class TestMatchThreshold:
    def test_ein_match_meets_threshold(self):
        m = MatchResult(subcontractor_id=uuid.uuid4(), match_score=1.0, match_method="ein")
        assert m.meets_threshold() is True

    def test_no_match_fails_threshold(self):
        m = MatchResult(match_score=0.0, match_method="none")
        assert m.meets_threshold() is False

    def test_low_score_fails_threshold(self):
        m = MatchResult(subcontractor_id=uuid.uuid4(), match_score=0.5, match_method="name")
        assert m.meets_threshold() is False

    def test_custom_threshold(self):
        m = MatchResult(subcontractor_id=uuid.uuid4(), match_score=0.8, match_method="name")
        assert m.meets_threshold(0.8) is True
        assert m.meets_threshold(0.95) is False


# ---------------------------------------------------------------------------
# 10. Batch health and pipeline summary (MID-613)
# ---------------------------------------------------------------------------


def _batch_mock_db(runs):
    """Build a mock AsyncSession returning the given sync_run_logs rows."""
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.mappings.return_value = MagicMock()
    mock_result.mappings.return_value.all.return_value = runs
    mock_db.execute.return_value = mock_result
    return mock_db


class TestCheckBatchHealth:
    @pytest.mark.asyncio
    async def test_computes_metrics_from_rows(self):
        now = datetime.now()
        runs = [
            {
                "job_name": "osha_daily_sync",
                "records_processed": 1000,
                "started_at": now,
                "completed_at": now,  # zero duration -> excluded from throughput avg
            },
            {
                "job_name": "osha_daily_sync",
                "records_processed": 1000,
                "started_at": now,
                "completed_at": now.replace(microsecond=0) if False else now,  # keep simple
            },
        ]
        # Give one run a real 10-second duration
        from datetime import timedelta as _td
        runs[0]["completed_at"] = now + _td(seconds=10)

        summary = await check_batch_health(_batch_mock_db(runs), days=7)
        metrics = summary["metrics"]["osha_daily_sync"]
        assert metrics["runs"] == 2
        assert metrics["total_records"] == 2000
        assert metrics["avg_throughput_rps"] == 100.0
        assert metrics["avg_duration_sec"] == 10.0

    @pytest.mark.asyncio
    async def test_latency_alert_fires(self):
        now = datetime.now()
        from datetime import timedelta as _td
        slow_duration = BATCH_LATENCY_MAX_MS / 1000 + 10.0
        runs = [
            {
                "job_name": "state_creds_CA",
                "records_processed": 100_000,  # high throughput, no throughput alert
                "started_at": now,
                "completed_at": now + _td(seconds=slow_duration),
            },
        ]
        summary = await check_batch_health(_batch_mock_db(runs), days=7)
        latency_alerts = [a for a in summary["alerts"] if a["alert_type"] == "batch_latency_high"]
        assert len(latency_alerts) == 1
        assert latency_alerts[0]["job_name"] == "state_creds_CA"
        assert latency_alerts[0]["severity"] == "error"

    @pytest.mark.asyncio
    async def test_throughput_alert_fires(self):
        now = datetime.now()
        from datetime import timedelta as _td
        runs = [
            {
                "job_name": "osha_daily_sync",
                "records_processed": 5,
                "started_at": now,
                "completed_at": now + _td(seconds=10),  # 0.5 rec/sec << threshold
            },
        ]
        summary = await check_batch_health(_batch_mock_db(runs), days=7)
        tput = [a for a in summary["alerts"] if a["alert_type"] == "batch_throughput_low"]
        assert len(tput) == 1

    @pytest.mark.asyncio
    async def test_empty_period_no_alerts(self):
        summary = await check_batch_health(_batch_mock_db([]), days=7)
        assert summary["metrics"] == {}
        assert summary["alerts"] == []


class TestGetPipelineHealthSummary:
    @pytest.mark.asyncio
    async def test_uses_parameterised_interval(self):
        """Regression: interval must be parameter-bound, not a quoted literal."""
        mock_db = AsyncMock()

        ok_result = MagicMock()
        ok_result.mappings.return_value = MagicMock()
        ok_result.mappings.return_value.all.return_value = [
            {
                "job_name": "osha_daily_sync",
                "total_runs": 10,
                "successful_runs": 10,
                "avg_records": 500.0,
                "max_records": 900,
                "avg_duration_sec": 12.5,
            }
        ]
        trend_result = MagicMock()
        trend_result.fetchone.return_value = (5000, 4000)
        mock_db.execute.side_effect = [ok_result, trend_result]

        summary = await get_pipeline_health_summary(mock_db, days=7)

        sql_used = str(mock_db.execute.call_args_list[0].args[0].text)
        assert "make_interval(days => :days)" in sql_used
        assert "INTERVAL ':days days'" not in sql_used
        job = summary["jobs"][0]
        assert job["job_name"] == "osha_daily_sync"
        assert job["success_rate"] == 100.0
        assert job["alert"] == "ok"
        assert summary["throughput_trend"]["last_24h"] == 5000
        assert summary["throughput_trend"]["change_pct"] == 25.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
