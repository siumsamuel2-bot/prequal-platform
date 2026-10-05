"""ETL Pipeline for External Compliance Data Integration

Integrates OSHA violation data and state credential databases into the
Prequal compliance platform. Handles extraction, transformation, deduplication,
subcontractor matching, error handling, rate limiting, and audit logging.

Usage:
    python -m app.services.external_compliance_pipeline --job osha --state CA
    python -m app.services.external_compliance_pipeline --job state-creds --state TX
    python -m app.services.external_compliance_pipeline --job full-pipeline

Environment:
    DATABASE_URL        PostgreSQL connection string
    OSHA_MAX_PAGES      Max pagination pages for OSHA (default 10)
    STATE_MAX_PAGES     Max pagination pages for state APIs (default 5)
    LOG_LEVEL           Logging level (default INFO)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

import asyncpg
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Ensure the prequal-platform app is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

from app.database import AsyncSessionLocal
from app.services.osha_client import OSHAClient
from app.services.state_credential_client import StateCredentialClient
from app.services.state_credential_validation import (
    validate_state_credential_record,
    StateCredentialValidationError,
)
from app.services.state_scrapers.factory import get_scraper, list_supported_states
from app.services.state_scrapers.base import ScrapedCredentialRecord
from app.services.source_db_connector import async_retry, retry_async

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_DB_URL = os.getenv(
    "DATABASE_URL", "postgresql+asyncpg://postgres@localhost:5432/compliance"
)
OSHA_MAX_PAGES = int(os.getenv("OSHA_MAX_PAGES", "20"))
OSHA_RATE_LIMIT = float(os.getenv("OSHA_RATE_LIMIT", "1.0"))
STATE_MAX_PAGES = int(os.getenv("STATE_MAX_PAGES", "10"))
SCRAPER_TIMEOUT_SECONDS = float(os.getenv("SCRAPER_TIMEOUT_SECONDS", "30.0"))
MAX_CONSECUTIVE_SCRAPER_FAILURES = int(os.getenv("MAX_CONSECUTIVE_SCRAPER_FAILURES", "10"))
MATCH_THRESHOLD = float(os.getenv("MATCH_THRESHOLD", "0.75"))

# Pipeline batch sizes (tuned for throughput)
# Unified batch size env var; per-source env vars below for fine-tuning.
DEFAULT_BATCH_SIZE = int(os.getenv("PIPELINE_BATCH_SIZE", "500"))
OSHA_PAGE_SIZE = int(os.getenv("OSHA_PAGE_SIZE", str(min(DEFAULT_BATCH_SIZE, 500))))
STATE_PAGE_SIZE = int(os.getenv("STATE_PAGE_SIZE", str(DEFAULT_BATCH_SIZE)))
STATE_MAX_RESULTS = int(os.getenv("STATE_MAX_RESULTS", "500"))

# Batch-processing telemetry thresholds
BATCH_THROUGHPUT_MIN = float(os.getenv("BATCH_THROUGHPUT_MIN", "50.0"))  # rec/sec
BATCH_LATENCY_MAX_MS = float(os.getenv("BATCH_LATENCY_MAX_MS", "30000.0"))  # ms

# Retry configuration for source-DB connector
DB_MAX_RETRIES = int(os.getenv("DB_MAX_RETRIES", "5"))
DB_BASE_RETRY_DELAY = float(os.getenv("DB_BASE_RETRY_DELAY", "1.0"))
DB_MAX_RETRY_DELAY = float(os.getenv("DB_MAX_RETRY_DELAY", "60.0"))

# Buffer window before final batch commit (seconds)
# Reduced from 120s to 5s to prevent sync delays blocking agent runs
COMMIT_BUFFER_SECONDS = float(os.getenv("PIPELINE_COMMIT_BUFFER_SECONDS", "5"))

# Stale run detection: jobs running longer than this are marked failed (hours)
# Reduced from 24h to 2h to prevent stuck runs from blocking agent execution
STALE_RUN_TIMEOUT_HOURS = int(os.getenv("STALE_RUN_TIMEOUT_HOURS", "2"))

# Scraper-specific timeout to prevent individual scraper calls from blocking the sync loop
SCRAPER_TIMEOUT_SECONDS = float(os.getenv("SCRAPER_TIMEOUT_SECONDS", "30.0"))
MAX_CONSECUTIVE_SCRAPER_FAILURES = int(os.getenv("MAX_CONSECUTIVE_SCRAPER_FAILURES", "10"))


# ---------------------------------------------------------------------------
# Retry decorator for transient DB errors
# ---------------------------------------------------------------------------
# NOTE: async_retry / retry_async are now imported from
# app.services.source_db_connector (canonical source-DB connector).


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class MatchResult:
    subcontractor_id: Optional[uuid.UUID] = None
    match_score: float = 0.0
    match_method: str = ""
    matched_on: str = ""

    def meets_threshold(self, threshold: float = MATCH_THRESHOLD) -> bool:
        """Whether this match is confident enough to persist."""
        return self.subcontractor_id is not None and self.match_score >= threshold


class OSHARecordValidationError(Exception):
    """Raised when an OSHA case record fails pre-load validation."""


def validate_osha_case_record(case: Dict[str, Any]) -> str:
    """Validate a raw OSHA case record before it touches the DB.

    Data-quality gate for the OSHA sync path (previously only state
    credentials had a validation gate). Records that fail validation are
    counted as failed and never written to storage.

    Returns the canonical osha_violation_id for valid records.
    """
    osha_id = str(case.get("id") or case.get("violation_id") or "").strip()
    if not osha_id or len(osha_id) > 64:
        raise OSHARecordValidationError(
            f"missing or oversized osha_violation_id: {osha_id!r}"
        )

    # At least one identity signal is required to match a subcontractor later
    if not (case.get("company_name") or case.get("establishment_name") or case.get("ein")):
        raise OSHARecordValidationError(
            f"osha_violation_id={osha_id}: no company name or EIN present"
        )

    # Dates must parse if present (reject malformed data instead of coercing)
    for field in ("date_opened", "issued_date", "effective_date", "resolution_date"):
        raw = case.get(field)
        if raw and parse_date(raw) is None:
            raise OSHARecordValidationError(
                f"osha_violation_id={osha_id}: unparseable {field}: {raw!r}"
            )

    # Monetary/gravity values must be numeric and non-negative if present
    for field in ("penalty_amount", "initial_penalty", "gravity_score"):
        raw = case.get(field)
        if raw is not None and raw != "":
            parsed = parse_decimal(raw)
            if parsed is None or parsed < 0:
                raise OSHARecordValidationError(
                    f"osha_violation_id={osha_id}: invalid {field}: {raw!r}"
                )

    return osha_id


@dataclass
class PipelineRun:
    id: uuid.UUID = field(default=None)
    job_name: str = ""
    job_type: str = ""
    status: str = "running"
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    records_extracted: int = 0
    records_transformed: int = 0
    records_inserted: int = 0
    records_updated: int = 0
    records_failed: int = 0
    records_matched: int = 0
    error_message: Optional[str] = None
    run_metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.id is None:
            self.id = uuid.uuid4()


# ---------------------------------------------------------------------------
# 1. Subcontractor Matching
# ---------------------------------------------------------------------------


async def find_subcontractor_by_ein(db: AsyncSession, ein: str) -> Optional[uuid.UUID]:
    if not ein:
        return None
    result = await db.execute(
        text("SELECT id FROM subcontractors WHERE ein = :ein LIMIT 1"),
        {"ein": ein.strip().upper()},
    )
    row = result.scalar_one_or_none()
    return row


async def find_subcontractor_by_license(
    db: AsyncSession, license_number: str, license_state: str
) -> Optional[uuid.UUID]:
    if not license_number or not license_state:
        return None
    result = await db.execute(
        text(
            "SELECT id FROM subcontractors WHERE license_number = :num "
            "AND license_state = :st LIMIT 1"
        ),
        {
            "num": license_number.strip().upper(),
            "st": license_state.strip().upper(),
        },
    )
    row = result.scalar_one_or_none()
    return row


async def find_subcontractor_by_name(db: AsyncSession, name: str) -> Optional[uuid.UUID]:
    if not name or len(name.strip()) < 3:
        return None
    clean = name.strip().upper()
    result = await db.execute(
        text("SELECT id FROM subcontractors WHERE UPPER(company_name) = :name LIMIT 1"),
        {"name": clean},
    )
    row = result.scalar_one_or_none()
    if row:
        return row
    # Partial match fallback
    result = await db.execute(
        text(
            "SELECT id FROM subcontractors WHERE UPPER(company_name) LIKE :pat LIMIT 1"
        ),
        {"pat": f"%{clean}%"},
    )
    return result.scalar_one_or_none()


def normalize_company_name(name: str) -> str:
    """Normalize company name for matching."""
    import re
    suffixes = [
        "INC", "LLC", "LTD", "CORP", "CORPORATION", "COMPANY",
        "CO", "LLP", "LP", "PLC", "PTY", "GMBH", "SA", "BV",
    ]
    n = name.upper().strip()
    # Strip common suffixes from end, handling optional preceding comma and trailing period
    for s in suffixes:
        while True:
            if n.endswith(f" {s}."):
                n = n[: -len(s) - 1].strip()
            elif n.endswith(f", {s}."):
                n = n[: -len(s) - 3].strip()
            elif n.endswith(f" {s}"):
                n = n[: -len(s) - 1].strip()
            elif n.endswith(f", {s}"):
                n = n[: -len(s) - 2].strip()
            else:
                break
    n = n.replace("&", "AND").replace(",", " ").replace(".", " ")
    return " ".join(n.split())


async def match_subcontractor(
    db: AsyncSession,
    *,
    ein: Optional[str] = None,
    name: Optional[str] = None,
    license_number: Optional[str] = None,
    license_state: Optional[str] = None,
) -> MatchResult:
    """Best-effort match an external record to an internal subcontractor."""
    if ein:
        sid = await find_subcontractor_by_ein(db, ein)
        if sid:
            return MatchResult(
                subcontractor_id=sid, match_score=1.0, match_method="ein", matched_on=ein
            )

    if license_number and license_state:
        sid = await find_subcontractor_by_license(db, license_number, license_state)
        if sid:
            return MatchResult(
                subcontractor_id=sid,
                match_score=0.95,
                match_method="license",
                matched_on=f"{license_number}/{license_state}",
            )

    if name:
        normalized = normalize_company_name(name)
        sid = await find_subcontractor_by_name(db, normalized)
        if sid:
            return MatchResult(
                subcontractor_id=sid,
                match_score=0.80,
                match_method="name",
                matched_on=name,
            )

    return MatchResult(match_score=0.0, match_method="none", matched_on="")


# ---------------------------------------------------------------------------
# 2. OSHA Sync
# ---------------------------------------------------------------------------


@retry_async()
async def run_osha_sync(
    *,
    db: AsyncSession,
    search: Optional[str] = None,
    state: Optional[str] = None,
    max_pages: int = OSHA_MAX_PAGES,
    triggered_by: str = "schedule",
) -> PipelineRun:
    """Fetch OSHA violations, match to subcontractors, upsert into DB."""
    run = PipelineRun(job_name="osha_daily_sync", job_type="osha_sync")
    logger.info("Starting OSHA sync run_id=%s", run.id)

    try:
        async with OSHAClient() as client:
            cases = await client.paginate_cases(
                search=search,
                state=state,
                date_opened_from=date(date.today().year - 3, 1, 1),
                page_size=OSHA_PAGE_SIZE,
                max_pages=max_pages,
            )

        run.records_extracted = len(cases)
        logger.info("Fetched %d OSHA cases", len(cases))

        # In-batch deduplication: OSHA paginated results can contain the same
        # case on multiple pages. Dedupe before any DB round-trip so we do not
        # pay a SELECT + upsert per duplicate. Last occurrence wins.
        unique_cases: Dict[str, dict] = {}
        for case in cases:
            raw_id = str(case.get("id") or case.get("violation_id") or "").strip()
            if raw_id:
                unique_cases[raw_id] = case
            else:
                # Keep records with no id; the validation gate will reject them
                unique_cases[f"__no_id__{len(unique_cases)}"] = case
        if len(unique_cases) < len(cases):
            logger.info(
                "OSHA batch dedupe: dropped %d duplicate case(s) (%d -> %d)",
                len(cases) - len(unique_cases), len(cases), len(unique_cases),
            )
        run.records_transformed = len(unique_cases)

        for case in unique_cases.values():
            try:
                await _process_osha_case(db, case, run)
            except OSHARecordValidationError as exc:
                logger.warning("Dropping invalid OSHA case record: %s", exc)
                run.records_failed += 1
            except Exception as exc:
                logger.error("Failed to process OSHA case: %s", exc)
                run.records_failed += 1

        run.status = "completed" if run.records_failed == 0 else "partial"
        run.completed_at = datetime.now()

    except Exception as exc:
        logger.exception("OSHA sync failed")
        run.status = "failed"
        run.error_message = str(exc)[:4096]
        run.completed_at = datetime.now()

    await _log_run(db, run, triggered_by)
    return run


async def _process_osha_case(db: AsyncSession, case: dict, run: PipelineRun) -> None:
    """Process a single OSHA case: validate, match, deduplicate, upsert."""
    # Data quality gate: validate raw record before touching the DB
    osha_id = validate_osha_case_record(case)

    existing = await db.execute(
        text("SELECT id, subcontractor_id FROM violations WHERE osha_violation_id = :osha_id"),
        {"osha_id": osha_id},
    )
    existing_row = existing.fetchone()

    company_name = case.get("company_name") or case.get("establishment_name") or ""
    ein = case.get("ein") or ""
    license_num = case.get("license_number") or ""
    license_state = case.get("license_state") or case.get("site_state") or ""

    match = await match_subcontractor(
        db, ein=ein, name=company_name, license_number=license_num, license_state=license_state
    )
    # Enforce MATCH_THRESHOLD: sub-threshold matches are too risky to persist.
    matched_id = match.subcontractor_id if match.meets_threshold() else None
    if match.subcontractor_id and not matched_id:
        logger.info(
            "Discarding sub-threshold match for OSHA case %s (method=%s score=%.2f < %.2f)",
            osha_id, match.match_method, match.match_score, MATCH_THRESHOLD,
        )

    v_data = {
        "id": str(uuid.uuid4()),
        "subcontractor_id": str(matched_id) if matched_id else None,
        "violation_type": case.get("violation_type", "safety"),
        "violation_code": case.get("violation_code") or case.get("citation_number", ""),
        "description": case.get("description") or case.get("violation_description", ""),
        "issued_by": "OSHA",
        "issued_date": parse_date(case.get("date_opened") or case.get("issued_date")) or date.today(),
        "effective_date": parse_date(case.get("effective_date")),
        "resolution_date": parse_date(case.get("resolution_date")),
        "status": map_status(case.get("status"), "open"),
        "penalty_amount": parse_decimal(case.get("penalty_amount") or case.get("initial_penalty")),
        "is_osha_violation": True,
        "osha_violation_id": osha_id,
        "inspection_number": str(case.get("inspection_number") or ""),
        "standard_cited": str(case.get("standard_cited") or ""),
        "gravity_score": parse_decimal(case.get("gravity_score")),
        "site_city": str(case.get("site_city") or ""),
        "site_state": str(case.get("site_state") or ""),
        "site_zip_code": str(case.get("site_zip_code") or ""),
        "naics_code": str(case.get("naics_code") or ""),
    }

    if existing_row:
        await db.execute(
            text(
                """UPDATE violations SET
                    subcontractor_id = :subcontractor_id,
                    violation_type = :violation_type,
                    violation_code = :violation_code,
                    description = :description,
                    issued_date = :issued_date,
                    effective_date = :effective_date,
                    resolution_date = :resolution_date,
                    status = :status,
                    penalty_amount = :penalty_amount,
                    osha_violation_id = :osha_violation_id,
                    inspection_number = :inspection_number,
                    standard_cited = :standard_cited,
                    gravity_score = :gravity_score,
                    site_city = :site_city,
                    site_state = :site_state,
                    site_zip_code = :site_zip_code,
                    naics_code = :naics_code,
                    is_osha_violation = TRUE,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = :id
                """
            ),
            {**v_data, "id": str(existing_row[0])},
        )
        run.records_updated += 1
    else:
        await db.execute(
            text(
                """INSERT INTO violations
                (id, subcontractor_id, violation_type, violation_code, description,
                issued_by, issued_date, effective_date, resolution_date, status,
                penalty_amount, is_osha_violation, osha_violation_id, inspection_number,
                standard_cited, gravity_score, site_city, site_state, site_zip_code, naics_code)
                VALUES
                (:id, :subcontractor_id, :violation_type, :violation_code, :description,
                :issued_by, :issued_date, :effective_date, :resolution_date, :status,
                :penalty_amount, TRUE, :osha_violation_id, :inspection_number,
                :standard_cited, :gravity_score, :site_city, :site_state, :site_zip_code, :naics_code)
                """
            ),
            v_data,
        )
        run.records_inserted += 1

    if matched_id:
        run.records_matched += 1


# ---------------------------------------------------------------------------
# 3. State Credential Sync
# ---------------------------------------------------------------------------


@retry_async()
async def run_state_credential_sync(
    *,
    db: AsyncSession,
    state_code: str,
    triggered_by: str = "schedule",
    search_query: str = "",
    max_results: int = STATE_MAX_RESULTS,
) -> PipelineRun:
    """Fetch state credentials, match to subcontractors, upsert into DB.

    Args:
        db: Database session.
        state_code: Two-letter state code (e.g. 'CA', 'TX').
        triggered_by: Who triggered the run.
        search_query: Optional explicit search query. If empty, the sync
            will look up active subcontractors in the DB for this state.
        max_results: Maximum number of subcontractors to look up when
            using the DB-driven sync path.
    """
    run = PipelineRun(
        job_name=f"state_creds_{state_code}",
        job_type="state_credential_sync",
    )
    logger.info("Starting state credential sync for %s run_id=%s", state_code, run.id)

    try:
        # Determine data path: scraper (preferred) or legacy API
        scraper = get_scraper(state_code.upper())
        api_url = os.getenv(f"STATE_API_URL_{state_code.upper()}")

        if scraper is not None:
            # Scraper path: prefer explicit search query, fallback to DB-driven lookup
            logger.info("Using scraper for state %s", state_code)
            if search_query:
                scraped_records = await asyncio.wait_for(
                    scraper.search_by_business_name(search_query),
                    timeout=SCRAPER_TIMEOUT_SECONDS
                )
                records = [r.__dict__ for r in scraped_records]
            else:
                # DB-driven incremental sync: look up active subcontractors in this state
                result = await db.execute(
                    text(
                        "SELECT company_name, license_number FROM subcontractors "
                        "WHERE license_state = :st AND status = 'active' LIMIT :limit"
                    ),
                    {"st": state_code.upper(), "limit": max_results},
                )
                rows = result.all()[:STATE_MAX_RESULTS]
                records: List[Dict[str, Any]] = []
                consecutive_failures = 0
                for row in rows:
                    if consecutive_failures >= MAX_CONSECUTIVE_SCRAPER_FAILURES:
                        logger.warning(
                            "Stopping sync for %s after %d consecutive scraper failures",
                            state_code, consecutive_failures
                        )
                        run.error_message = (
                            f"Stopped: too many consecutive scraper failures ({MAX_CONSECUTIVE_SCRAPER_FAILURES})"
                        )
                        run.status = "partial"
                        run.completed_at = datetime.now()
                        await _log_run(db, run, triggered_by)
                        return run

                    company_name, license_number = row
                    try:
                        if license_number:
                            recs = await asyncio.wait_for(
                                scraper.search_by_license_number(license_number),
                                timeout=SCRAPER_TIMEOUT_SECONDS
                            )
                        elif company_name:
                            recs = await asyncio.wait_for(
                                scraper.search_by_business_name(company_name),
                                timeout=SCRAPER_TIMEOUT_SECONDS
                            )
                        else:
                            continue
                        consecutive_failures = 0
                    except asyncio.TimeoutError:
                        logger.warning(
                            "Scraper call timed out for %s in state %s after %.1fs",
                            license_number or company_name, state_code, SCRAPER_TIMEOUT_SECONDS
                        )
                        consecutive_failures += 1
                        continue
                    except Exception as exc:
                        logger.error(
                            "Scraper call failed for %s in state %s: %s",
                            license_number or company_name, state_code, exc
                        )
                        consecutive_failures += 1
                        continue

                    records.extend(r.__dict__ for r in recs)
                    await asyncio.sleep(0.5)
            await scraper.close()
        elif api_url:
            # Legacy API path
            client = StateCredentialClient(state_code)
            records = await client.paginate_credentials(query="", page_size=STATE_PAGE_SIZE, max_pages=STATE_MAX_PAGES)
            await client.close()
        else:
            logger.warning("No scraper or API configured for %s -- skipping.", state_code)
            run.status = "skipped"
            run.completed_at = datetime.now()
            run.error_message = f"No data source configured for state {state_code}"
            await _log_run(db, run, triggered_by)
            return run

        run.records_extracted = len(records)
        run.records_transformed = len(records)
        logger.info("Fetched %d credentials for state %s", len(records), state_code)

        for rec in records:
            try:
                await _process_state_credential(db, rec, run)
            except Exception as exc:
                logger.error("Failed to process state credential: %s", exc)
                run.records_failed += 1

        run.status = "completed" if run.records_failed == 0 else "partial"
        run.completed_at = datetime.now()

    except Exception as exc:
        logger.exception("State credential sync failed for %s", state_code)
        run.status = "failed"
        run.error_message = str(exc)[:4096]
        run.completed_at = datetime.now()

    await _log_run(db, run, triggered_by)
    return run


async def _process_state_credential(db: AsyncSession, rec: dict, run: PipelineRun) -> None:
    """Process a single state credential record: validate, match, deduplicate, upsert."""
    # Data quality gate: validate raw record before touching the DB
    try:
        validated = validate_state_credential_record(rec)
    except StateCredentialValidationError as exc:
        logger.warning("Dropping invalid state credential record: %s", exc)
        run.records_failed += 1
        return

    state_code = validated["state_code"]
    cred_num = validated["credential_number"]
    cred_type = validated["credential_type"]

    existing = await db.execute(
        text(
            "SELECT id FROM state_credential_records WHERE state_code = :st "
            "AND credential_number = :num AND credential_type = :ctype"
        ),
        {"st": state_code, "num": cred_num, "ctype": cred_type},
    )
    existing_row = existing.scalar_one_or_none()

    holder_name = str(validated.get("holder_name") or validated.get("name", ""))
    ein = str(validated.get("ein") or "")
    license_num = str(validated.get("license_number") or cred_num)
    license_state = str(validated.get("license_state") or state_code)

    match = await match_subcontractor(
        db, ein=ein, name=holder_name, license_number=license_num, license_state=license_state
    )
    # Enforce MATCH_THRESHOLD: sub-threshold matches are too risky to persist.
    matched_id = match.subcontractor_id if match.meets_threshold() else None
    if match.subcontractor_id and not matched_id:
        logger.info(
            "Discarding sub-threshold match for state credential %s/%s (method=%s score=%.2f < %.2f)",
            state_code, cred_num, match.match_method, match.match_score, MATCH_THRESHOLD,
        )

    values = {
        "id": str(uuid.uuid4()),
        "state_code": state_code,
        "credential_number": cred_num,
        "credential_type": cred_type,
        "issuing_state": str(validated.get("issuing_state") or state_code),
        "holder_name": holder_name,
        "holder_address": validated.get("holder_address"),
        "holder_city": validated.get("holder_city"),
        "holder_state": validated.get("holder_state"),
        "holder_zip": validated.get("holder_zip"),
        "issue_date": validated.get("issue_date"),
        "expiration_date": validated.get("expiration_date"),
        "status": validated.get("status", "active"),
        "external_source_id": validated.get("external_source_id"),
        "external_source_url": validated.get("external_source_url"),
        "last_synced_at": datetime.now(),
        "sync_version": validated.get("sync_version", 1),
        "raw_data": json.dumps(dict(validated)),
        "subcontractor_id": str(matched_id) if matched_id else None,
    }

    if existing_row:
        await db.execute(
            text(
                """UPDATE state_credential_records SET
                    issuing_state = :issuing_state,
                    holder_name = :holder_name,
                    holder_address = :holder_address,
                    holder_city = :holder_city,
                    holder_state = :holder_state,
                    holder_zip = :holder_zip,
                    issue_date = :issue_date,
                    expiration_date = :expiration_date,
                    status = :status,
                    external_source_id = :external_source_id,
                    external_source_url = :external_source_url,
                    last_synced_at = :last_synced_at,
                    sync_version = sync_version + 1,
                    raw_data = :raw_data,
                    subcontractor_id = :subcontractor_id,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = :id
                """
            ),
            {**values, "id": str(existing_row)},
        )
        run.records_updated += 1
    else:
        await db.execute(
            text(
                """INSERT INTO state_credential_records
                (id, state_code, credential_number, credential_type, issuing_state,
                holder_name, holder_address, holder_city, holder_state, holder_zip,
                issue_date, expiration_date, status, external_source_id,
                external_source_url, last_synced_at, sync_version, raw_data, created_at, updated_at)
                VALUES
                (:id, :state_code, :credential_number, :credential_type, :issuing_state,
                :holder_name, :holder_address, :holder_city, :holder_state, :holder_zip,
                :issue_date, :expiration_date, :status, :external_source_id,
                :external_source_url, :last_synced_at, :sync_version, :raw_data,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """
            ),
            values,
        )
        run.records_inserted += 1

    if matched_id:
        run.records_matched += 1


# ---------------------------------------------------------------------------
# 4. Data Quality / Validation
# ---------------------------------------------------------------------------


async def record_pipeline_metric(
    db: AsyncSession,
    *,
    job_name: str,
    metric_name: str,
    metric_value: float,
    metric_unit: str = "count",
) -> None:
    """Record a pipeline health metric to system_health_metrics.

    This provides time-series monitoring for pipeline throughput,
    duration, and success rates.
    """
    try:
        await db.execute(
            text(
                """INSERT INTO system_health_metrics
                (id, service_name, metric_name, metric_value, metric_unit, recorded_at)
                VALUES (gen_random_uuid(), :service_name, :metric_name, :metric_value, :metric_unit, CURRENT_TIMESTAMP)
                """
            ),
            {
                "service_name": job_name,
                "metric_name": metric_name,
                "metric_value": metric_value,
                "metric_unit": metric_unit,
            },
        )
        await db.commit()
    except Exception as exc:
        logger.warning("Failed to record pipeline metric: %s", exc)


async def get_pipeline_health_summary(db: AsyncSession, *, days: int = 7) -> Dict[str, Any]:
    """Return a summary of pipeline health for the last N days.

    Includes throughput, success rates, trend analysis, and alert
    conditions for the data pipeline.
    """
    summary: Dict[str, Any] = {"period_days": days, "jobs": []}

    # MID-613 fix: previously used INTERVAL ':days days' — the parameter was
    # quoted inside a string literal so it never bound, and the query failed
    # with an invalid-interval error on PostgreSQL. make_interval() is the
    # correct parameterised form.
    result = await db.execute(
        text(
            """
            SELECT
                job_name,
                COUNT(*) as total_runs,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as successful_runs,
                AVG(records_processed) as avg_records,
                MAX(records_processed) as max_records,
                AVG(EXTRACT(EPOCH FROM (completed_at - started_at))) as avg_duration_sec
            FROM sync_run_logs
            WHERE started_at > NOW() - make_interval(days => :days)
            GROUP BY job_name
            ORDER BY total_runs DESC
            """
        ),
        {"days": days},
    )
    for row in result.mappings().all():
        total = row["total_runs"]
        success = row["successful_runs"] or 0
        success_rate = round((success / total) * 100, 2) if total else 0.0
        summary["jobs"].append(
            {
                "job_name": row["job_name"],
                "total_runs": total,
                "success_rate": success_rate,
                "avg_records": round(float(row["avg_records"] or 0), 2),
                "max_records": row["max_records"] or 0,
                "avg_duration_sec": round(float(row["avg_duration_sec"] or 0), 2),
                "alert": "critical" if success_rate < 80 else "warning" if success_rate < 95 else "ok",
            }
        )

    # Throughput trend: compare last 24h to previous 24h
    result = await db.execute(
        text(
            """
            SELECT
                SUM(CASE WHEN started_at > NOW() - INTERVAL '1 day' THEN records_processed ELSE 0 END) as last_24h,
                SUM(CASE WHEN started_at <= NOW() - INTERVAL '1 day' AND started_at > NOW() - INTERVAL '2 days' THEN records_processed ELSE 0 END) as prev_24h
            FROM sync_run_logs
            WHERE started_at > NOW() - INTERVAL '2 days'
            """
        )
    )
    row = result.fetchone()
    if row:
        last_24h, prev_24h = row[0] or 0, row[1] or 0
        summary["throughput_trend"] = {
            "last_24h": last_24h,
            "prev_24h": prev_24h,
            "change_pct": round(((last_24h - prev_24h) / max(prev_24h, 1)) * 100, 2),
        }

    return summary


async def cleanup_stale_runs(db: AsyncSession) -> int:
    """Mark runs that have been 'running' longer than STALE_RUN_TIMEOUT_HOURS as failed.

    Returns the number of runs that were cleaned up.
    """
    timeout_interval = f"{STALE_RUN_TIMEOUT_HOURS} hours"
    result = await db.execute(
        text(
            f"""
            UPDATE sync_run_logs
            SET status = 'failed',
                completed_at = NOW(),
                error_message = 'Automatically marked failed: run exceeded {STALE_RUN_TIMEOUT_HOURS}-hour timeout and appeared to be stuck.'
            WHERE status = 'running' AND started_at < NOW() - INTERVAL '{timeout_interval}'
            RETURNING id, job_name, started_at
            """
        )
    )
    cleaned = result.fetchall()
    if cleaned:
        for row in cleaned:
            logger.warning(
                "Cleaned up stale run: id=%s job_name=%s started_at=%s (ran for > %s)",
                row[0], row[1], row[2], timeout_interval,
            )
    await db.commit()
    return len(cleaned)


async def validate_pipeline_health(db: AsyncSession) -> Dict[str, Any]:
    """Run data-quality checks after a sync and clean up stale runs."""
    checks = {}

    cleaned = await cleanup_stale_runs(db)
    checks["stale_runs_cleaned"] = cleaned

    result = await db.execute(
        text("SELECT COUNT(*) FROM violations WHERE subcontractor_id IS NULL AND is_osha_violation = TRUE")
    )
    checks["unmatched_osha_violations"] = result.scalar()

    result = await db.execute(
        text("SELECT COUNT(*) FROM state_credential_records WHERE subcontractor_id IS NULL")
    )
    checks["unmatched_state_credentials"] = result.scalar()

    result = await db.execute(
        text("""
            SELECT COUNT(*) FROM sync_run_logs
            WHERE status = 'running' AND started_at < NOW() - INTERVAL '24 hours'
        """)
    )
    checks["stale_running_jobs"] = result.scalar()

    result = await db.execute(
        text("""
            SELECT COUNT(*) FROM sync_run_logs
            WHERE status = 'failed' AND started_at > NOW() - INTERVAL '7 days'
        """)
    )
    checks["failed_jobs_last_7d"] = result.scalar()

    return checks


# ---------------------------------------------------------------------------
# 5. Audit & Logging
# ---------------------------------------------------------------------------


async def _log_run(db: AsyncSession, run: PipelineRun, triggered_by: str) -> None:
    """Persist pipeline run metadata to sync_run_logs table and record metrics."""
    # Compute batch-level metrics
    duration_sec = (run.completed_at - run.started_at).total_seconds() if run.completed_at else 0.0
    total_processed = run.records_inserted + run.records_updated + run.records_failed
    throughput = total_processed / duration_sec if duration_sec > 0 else 0.0

    # Persist run log
    await db.execute(
        text(
            """INSERT INTO sync_run_logs
            (id, job_name, job_type, status, triggered_by, started_at, completed_at,
            records_processed, records_inserted, records_updated, records_failed,
            error_message, run_metadata)
            VALUES
            (:id, :job_name, :job_type, :status, :triggered_by, :started_at, :completed_at,
            :records_processed, :records_inserted, :records_updated, :records_failed,
            :error_message, :run_metadata)
            """
        ),
        {
            "id": str(run.id),
            "job_name": run.job_name,
            "job_type": run.job_type,
            "status": run.status,
            "triggered_by": triggered_by,
            "started_at": run.started_at,
            "completed_at": run.completed_at,
            "records_processed": total_processed,
            "records_inserted": run.records_inserted,
            "records_updated": run.records_updated,
            "records_failed": run.records_failed,
            "error_message": run.error_message,
            "run_metadata": json.dumps(
                {
                    "records_matched": run.records_matched,
                    "duration_seconds": duration_sec,
                    "throughput_rps": round(throughput, 2),
                    **run.run_metadata,
                }
            ),
        },
    )

    # Also record into pipeline_performance for 95th-percentile latency monitoring
    try:
        await db.execute(
            text(
                "INSERT INTO pipeline_performance (id, pipeline_name, run_start_at, run_end_at, duration_ms, records_processed, records_inserted, records_updated, records_failed, status) VALUES (:id, :pipeline_name, :run_start_at, :run_end_at, :duration_ms, :records_processed, :records_inserted, :records_updated, :records_failed, :status)"
            ),
            {
                "id": str(uuid.uuid4()),
                "pipeline_name": run.job_name,
                "run_start_at": run.started_at,
                "run_end_at": run.completed_at,
                "duration_ms": int(duration_sec * 1000),
                "records_processed": total_processed,
                "records_inserted": run.records_inserted,
                "records_updated": run.records_updated,
                "records_failed": run.records_failed,
                "status": run.status,
            },
        )
    except Exception as exc:
        logger.warning("Failed to record pipeline_performance: %s", exc)

    await asyncio.sleep(COMMIT_BUFFER_SECONDS)
    await db.commit()

    # Record pipeline health metrics
    try:
        await record_pipeline_metric(
            db,
            job_name=run.job_name,
            metric_name="records_extracted",
            metric_value=float(run.records_extracted),
            metric_unit="count",
        )
        await record_pipeline_metric(
            db,
            job_name=run.job_name,
            metric_name="records_inserted",
            metric_value=float(run.records_inserted),
            metric_unit="count",
        )
        await record_pipeline_metric(
            db,
            job_name=run.job_name,
            metric_name="records_updated",
            metric_value=float(run.records_updated),
            metric_unit="count",
        )
        await record_pipeline_metric(
            db,
            job_name=run.job_name,
            metric_name="records_failed",
            metric_value=float(run.records_failed),
            metric_unit="count",
        )
        await record_pipeline_metric(
            db,
            job_name=run.job_name,
            metric_name="duration_seconds",
            metric_value=duration_sec,
            metric_unit="seconds",
        )
        await record_pipeline_metric(
            db,
            job_name=run.job_name,
            metric_name="throughput_rps",
            metric_value=round(throughput, 2),
            metric_unit="records_per_second",
        )
        await record_pipeline_metric(
            db,
            job_name=run.job_name,
            metric_name="success_rate",
            metric_value=100.0 if run.status == "completed" else 0.0,
            metric_unit="percent",
        )
    except Exception as exc:
        logger.warning("Failed to record pipeline health metrics: %s", exc)

    logger.info(
        "Pipeline run logged: %s status=%s inserted=%d updated=%d failed=%d matched=%d",
        run.job_name, run.status, run.records_inserted, run.records_updated,
        run.records_failed, run.records_matched,
    )


# ---------------------------------------------------------------------------
# 6. Batch Health Monitoring
# ---------------------------------------------------------------------------

async def check_batch_health(db: AsyncSession, *, days: int = 7) -> Dict[str, Any]:
    """Check batch processing health and alert on throughput/latency issues.

    MID-613 rewrite: the previous implementation used SQLite-only julianday() /
    datetime('now') in a PostgreSQL-targeted module, so it failed against the
    production database. Duration/throughput math is now computed in Python
    over fetched rows, which is dialect-portable. BATCH_LATENCY_MAX_MS
    (previously defined but never enforced) now triggers latency alerts.

    Returns a summary of batch-level metrics and any triggered alerts.
    """
    summary: Dict[str, Any] = {
        "checked_at": datetime.now().isoformat(),
        "period_days": days,
        "metrics": {},
        "alerts": [],
    }

    cutoff = datetime.now() - timedelta(days=days)
    result = await db.execute(
        text(
            """
            SELECT job_name, records_processed, started_at, completed_at
            FROM sync_run_logs
            WHERE started_at >= :cutoff
            AND completed_at IS NOT NULL
            AND status IN ('completed', 'partial')
            ORDER BY job_name, started_at
            """
        ),
        {"cutoff": cutoff},
    )
    rows = result.mappings().all()

    by_job: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        started = _parse_dt(r["started_at"])
        completed = _parse_dt(r["completed_at"])
        duration_sec = (completed - started).total_seconds() if started and completed else None
        by_job.setdefault(r["job_name"], []).append(
            {
                "records_processed": int(r["records_processed"] or 0),
                "duration_sec": duration_sec,
            }
        )

    for job_name, job_runs in by_job.items():
        durations = [r["duration_sec"] for r in job_runs if r["duration_sec"] is not None and r["duration_sec"] > 0]
        avg_duration = sum(durations) / len(durations) if durations else 0.0
        total_records = sum(r["records_processed"] for r in job_runs)
        max_batch = max((r["records_processed"] for r in job_runs), default=0)
        # Throughput per completed run, averaged per-run (rec/sec)
        run_rates = [
            r["records_processed"] / r["duration_sec"]
            for r in job_runs
            if r["duration_sec"] is not None and r["duration_sec"] > 0
        ]
        avg_throughput = sum(run_rates) / len(run_rates) if run_rates else 0.0

        summary["metrics"][job_name] = {
            "runs": len(job_runs),
            "total_records": total_records,
            "avg_throughput_rps": round(avg_throughput, 2),
            "max_batch_size": max_batch,
            "avg_duration_sec": round(avg_duration, 2),
        }

        # Alert if throughput drops below threshold
        if avg_throughput < BATCH_THROUGHPUT_MIN:
            summary["alerts"].append({
                "alert_type": "batch_throughput_low",
                "severity": "warning",
                "job_name": job_name,
                "message": (
                    f"Batch throughput for {job_name} is {avg_throughput:.2f} rec/sec, "
                    f"below threshold of {BATCH_THROUGHPUT_MIN} rec/sec"
                ),
                "threshold_value": BATCH_THROUGHPUT_MIN,
                "actual_value": round(avg_throughput, 2),
            })

        # Alert if average batch latency exceeds the configured maximum
        if avg_duration * 1000 > BATCH_LATENCY_MAX_MS:
            summary["alerts"].append({
                "alert_type": "batch_latency_high",
                "severity": "error",
                "job_name": job_name,
                "message": (
                    f"Average batch latency for {job_name} is {avg_duration:.1f}s, "
                    f"above threshold of {BATCH_LATENCY_MAX_MS / 1000:.1f}s"
                ),
                "threshold_value": BATCH_LATENCY_MAX_MS,
                "actual_value": int(avg_duration * 1000),
            })

    # Current active batch sizes from environment
    summary["current_config"] = {
        "osha_page_size": OSHA_PAGE_SIZE,
        "state_page_size": STATE_PAGE_SIZE,
        "state_max_results": STATE_MAX_RESULTS,
        "batch_throughput_min": BATCH_THROUGHPUT_MIN,
        "batch_latency_max_ms": BATCH_LATENCY_MAX_MS,
    }

    return summary


# ---------------------------------------------------------------------------
# 7. Utilities
# ---------------------------------------------------------------------------


def _parse_dt(value: Any) -> Optional[datetime]:
    """Coerce a DB value (datetime or ISO string) to a naive datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    s = str(value).strip().replace("Z", "+00:00")
    for fmt in (None, "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            if fmt is None:
                dt = datetime.fromisoformat(s.split(".")[0] if "+" not in s else s)
            else:
                dt = datetime.strptime(s, fmt)
            return dt.replace(tzinfo=None)
        except ValueError:
            continue
    return None


def parse_date(value: Any) -> Optional[date]:
    if not value:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(str(value), fmt).date()
        except ValueError:
            continue
    return None


def parse_decimal(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def map_status(value: Any, default: str = "open") -> str:
    if not value:
        return default
    s = str(value).lower().strip()
    mapping = {
        "open": "open",
        "closed": "resolved",
        "resolved": "resolved",
        "under_review": "under_review",
        "appealed": "appealed",
        "pending": "under_review",
    }
    return mapping.get(s, default)


# ---------------------------------------------------------------------------
# 7. Full Pipeline
# ---------------------------------------------------------------------------


async def run_full_pipeline(
    *,
    state_codes: Optional[List[str]] = None,
    triggered_by: str = "schedule",
) -> Dict[str, Any]:
    """Run the complete external compliance data pipeline."""
    overall_start = datetime.now()
    results: Dict[str, Any] = {
        "started_at": overall_start.isoformat(),
        "osha": None,
        "state_credentials": [],
    }

    db: Optional[AsyncSession] = None
    try:
        db = AsyncSessionLocal()

        try:
            osha_run = await run_osha_sync(db=db, triggered_by=triggered_by)
            results["osha"] = {
                "run_id": str(osha_run.id),
                "status": osha_run.status,
                "extracted": osha_run.records_extracted,
                "inserted": osha_run.records_inserted,
                "updated": osha_run.records_updated,
                "failed": osha_run.records_failed,
                "matched": osha_run.records_matched,
            }
        except Exception as exc:
            logger.exception("OSHA sync step failed")
            results["osha"] = {"status": "failed", "error": str(exc)}
            osha_failed_run = PipelineRun(
                job_name="osha_daily_sync",
                job_type="osha_sync",
                status="failed",
                error_message=str(exc)[:4096],
                completed_at=datetime.now(),
            )
            await _log_run(db, osha_failed_run, triggered_by)

        if not state_codes:
            # Discover states from both scrapers and legacy API env vars
            state_codes = list_supported_states()
            state_codes += [
                k.replace("STATE_API_URL_", "")
                for k in os.environ.keys()
                if k.startswith("STATE_API_URL_")
            ]
            # De-duplicate while preserving order
            state_codes = list(dict.fromkeys(state_codes))

        for sc in (state_codes or []):
            try:
                sc_run = await run_state_credential_sync(
                    db=db, state_code=sc, triggered_by=triggered_by
                )
                results["state_credentials"].append(
                    {
                        "state": sc,
                        "run_id": str(sc_run.id),
                        "status": sc_run.status,
                        "extracted": sc_run.records_extracted,
                        "inserted": sc_run.records_inserted,
                        "updated": sc_run.records_updated,
                        "failed": sc_run.records_failed,
                        "matched": sc_run.records_matched,
                    }
                )
            except Exception as exc:
                logger.exception("State credential sync failed for %s", sc)
                results["state_credentials"].append(
                    {"state": sc, "status": "failed", "error": str(exc)}
                )

        results["completed_at"] = datetime.now().isoformat()

    finally:
        if db is not None:
            await db.close()

    return results


# ---------------------------------------------------------------------------
# 8. Analytics Views Refresh
# ---------------------------------------------------------------------------

async def refresh_analytics_views(db: AsyncSession) -> None:
    """Refresh analytics materialized views for dashboard consumption."""
    logger.info("Refreshing analytics materialized views ...")
    await db.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_compliance_summary"))
    await db.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_violation_trends"))
    await db.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_certification_status"))
    await db.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_project_compliance"))
    await asyncio.sleep(COMMIT_BUFFER_SECONDS)
    await db.commit()
    logger.info("Analytics views refreshed.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="External Compliance Data ETL Pipeline")
    parser.add_argument("--job", choices=["osha", "state-creds", "full-pipeline"], default="full-pipeline")
    parser.add_argument("--state", default="", help="State code for state-creds job")
    parser.add_argument("--search", default=None, help="OSHA search filter")
    parser.add_argument("--max-pages", type=int, default=OSHA_MAX_PAGES)
    parser.add_argument("--triggered-by", default="manual")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    async def _run() -> None:
        db = AsyncSessionLocal()
        try:
            if args.job == "osha":
                run = await run_osha_sync(
                    db=db,
                    search=args.search,
                    max_pages=args.max_pages,
                    triggered_by=args.triggered_by,
                )
                print(f"OSHA sync: {run.status} (inserted={run.records_inserted}, updated={run.records_updated}, failed={run.records_failed})")
            elif args.job == "state-creds":
                if not args.state:
                    print("--state is required for state-creds job")
                    return
                run = await run_state_credential_sync(
                    db=db, state_code=args.state, triggered_by=args.triggered_by
                )
                print(f"State creds sync: {run.status} (inserted={run.records_inserted}, updated={run.records_updated}, failed={run.records_failed})")
            else:
                results = await run_full_pipeline(triggered_by=args.triggered_by)
                print(json.dumps(results, indent=2, default=str))
        finally:
            await db.close()

    asyncio.run(_run())


if __name__ == "__main__":
    main()
