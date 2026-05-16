"""
OSHA Data Ingestion Pipeline.

ETL Flow:
    1. EXTRACT: Fetch OSHA cases via OSHAClient
    2. TRANSFORM: Map case fields to our violations/inspections schema
    3. LOAD: Upsert using SQLAlchemy ORM
    4. LOG: Record API call in osha_api_logs + update osha_data_freshness

Usage:
    python scripts/etl_osha.py

DevOps notes:
    Requires SQLAlchemy and aiohttp to be installed.
    PostgreSQL must be running with the schema from `001_initial_schema`.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from datetime import date, datetime

# Allow imports from project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/prequal_compliance",
)
OSHA_SEARCH_TERM = os.getenv("OSHA_SEARCH_TERM", "")
OSHA_STATE_FILTER = os.getenv("OSHA_STATE_FILTER", "")

# ---------------------------------------------------------------------------
# Data Types
# ---------------------------------------------------------------------------


def iso_or_none(raw: str | None) -> date | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except Exception:
        try:
            return date.fromisoformat(raw)
        except Exception:
            return None


def _extract_violation_record(case: dict) -> dict:
    """Map a raw OSHA case dict to our violations schema."""
    return {
        "violation_type": (case.get("type") or "OSHA").strip().upper(),
        "violation_code": case.get("case_number") or case.get("number"),
        "description": (case.get("allegation") or case.get("summary") or "").strip()[:1000],
        "issued_by": "OSHA",
        "issued_date": iso_or_none(case.get("date_opened") or case.get("date")),
        "effective_date": iso_or_none(case.get("date_filed") or case.get("date_opened")),
        "resolution_date": iso_or_none(case.get("date_closed") or case.get("resolution_date")),
        "status": "open" if (case.get("status") or "").lower() in ("open", "pending") else "resolved",
        "is_osha_violation": True,
        "osha_violation_id": str(case.get("id", "") or "" or "$" + str(case.get("case_number", "") or "")) or None,
        "inspection_number": (case.get("inspection_number") or case.get("inspection_id")) or None,
        "standard_cited": case.get("statute") or case.get("standard") or case.get("cfr") or None,
        "gravity_score": None,
    }


def _extract_inspection_record(case: dict) -> dict:
    """Map a raw OSHA case dict to our osha_inspections schema."""
    return {
        "inspection_number": (case.get("inspection_number") or str(case.get("id", "") or "")) or None,
        "inspection_date": iso_or_none(case.get("date_opened") or case.get("date")) or date.today(),
        "type": (case.get("inspection_type") or case.get("type") or "whistleblower").strip().upper(),
        "site_city": case.get("city") or None,
        "site_state": case.get("state") or None,
        "site_address": case.get("address") or None,
        "naics_code": case.get("naics") or None,
        "reported_by": "OSHA",
        "owner_type": None,
        "total_penalty": 0,
        "abatement_completed": None,
    }


# ---------------------------------------------------------------------------
# Load Stage
# ---------------------------------------------------------------------------

from sqlalchemy import create_engine  # noqa: I001
from sqlalchemy.orm import sessionmaker

engine = None
SessionLocal = None


def _get_engine():
    global engine
    if engine is None:
        engine = create_engine(
            DATABASE_URL.replace("+asyncpg", "").replace("+psycopg2", ""),
            echo=os.getenv("SQL_DEBUG", "false").lower() == "true",
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
        )
    return engine


def _get_session():
    global SessionLocal
    if SessionLocal is None:
        SessionLocal = sessionmaker(bind=_get_engine())
    return SessionLocal()


def _save_api_log(session, request_type, params, response_body, records_processed, records_failed, error_message):
    from sqlalchemy import text
    result = session.execute(
        text(
            """INSERT INTO osha_api_logs (id, request_type, request_parameters,
            request_date, response_status, response_body, records_processed,
            records_failed, error_message) VALUES (gen_random_uuid(), :request_type,
            :request_parameters, now(), :response_status, :response_body, :records_processed,
            :records_failed, :error_message) RETURNING id"""
        ),
        {
            "request_type": request_type,
            "request_parameters": str(params)[:2048],
            "response_status": 200,
            "response_body": str(response_body)[:4096],
            "records_processed": records_processed,
            "records_failed": records_failed,
            "error_message": error_message[:2048] if error_message else None,
        },
    )
    return result.fetchone()[0]


def _load_case(session, case: dict) -> dict:
    from sqlalchemy import text
    summary = {"violation_id": None, "inspection_id": None, "existing": False, "success": False}

    # Extract unified arguments
    vrec = _extract_violation_record(case)
    irect = _extract_inspection_record(case)

    # Upsert violation by osha_violation_id (SELECT then INSERT/UPDATE)
    osha_id = vrec.get("osha_violation_id")
    if osha_id is not None:
        # Check if it exists
        existing = session.execute(
            text("SELECT id FROM violations WHERE osha_violation_id = :osha_id"),
            {"osha_id": osha_id},
        ).fetchone()

        if existing:
            summary["violation_id"] = existing[0]
            summary["existing"] = True
            # Update it
            session.execute(
                text(
                    """UPDATE violations SET status = :status,
                    resolution_date = :resolution_date, description = :description,
                    inspection_number = :inspection_number, standard_cited = :standard_cited,
                    updated_at = CURRENT_TIMESTAMP WHERE osha_violation_id = :osha_id"""
                ),
                {
                    "osha_id": osha_id,
                    "status": vrec["status"],
                    "resolution_date": vrec["resolution_date"],
                    "description": vrec["description"],
                    "inspection_number": vrec["inspection_number"],
                    "standard_cited": vrec["standard_cited"],
                },
            )
        else:
            # Insert it
            result = session.execute(
                text(
                    """INSERT INTO violations (id, violation_type, violation_code, description,
                    issued_by, issued_date, effective_date, resolution_date, status,
                    is_osha_violation, osha_violation_id, inspection_number, standard_cited,
                    gravity_score, is_criminal, penalty_amount) VALUES (gen_random_uuid(),
                    :violation_type, :violation_code, :description, :issued_by, :issued_date,
                    :effective_date, :resolution_date, :status, :is_osha_violation,
                    :osha_violation_id, :inspection_number, :standard_cited, :gravity_score,
                    FALSE, 0) RETURNING id"""
                ),
                vrec,
            )
            summary["violation_id"] = result.fetchone()[0]

    # Upsert inspection by inspection_number
    ins_number = irect.get("inspection_number")
    if ins_number is not None:
        existing_ins = session.execute(
            text("SELECT id FROM osha_inspections WHERE inspection_number = :ins_number"),
            {"ins_number": ins_number},
        ).fetchone()

        if existing_ins:
            summary["inspection_id"] = existing_ins[0]
            session.execute(
                text(
                    """UPDATE osha_inspections SET inspection_date = :inspection_date,
                    type = :type, site_city = :site_city, site_state = :site_state,
                    site_address = :site_address, naics_code = :naics_code,
                    updated_at = CURRENT_TIMESTAMP WHERE inspection_number = :inspection_number"""
                ),
                irect,
            )
        else:
            result = session.execute(
                text(
                    """INSERT INTO osha_inspections (id, inspection_number, inspection_date, type,
                    site_city, site_state, site_address, naics_code, reported_by, owner_type,
                    total_penalty, abatement_completed) VALUES (gen_random_uuid(),
                    :inspection_number, :inspection_date, :type, :site_city, :site_state,
                    :site_address, :naics_code, :reported_by, :owner_type, :total_penalty,
                    :abatement_completed) RETURNING id"""
                ),
                irect,
            )
            summary["inspection_id"] = result.fetchone()[0]

    summary["success"] = True
    return summary


# ---------------------------------------------------------------------------
# Main ETL
# ---------------------------------------------------------------------------

async def run_etl(
    *,
    search: str | None = None,
    state: str | None = None,
    max_pages: int | None = None,
) -> dict:
    from app.services.osha_client import OSHAClient

    case_list: list[dict] = []
    total_inserted = 0
    total_updated = 0
    total_failed = 0
    log_id = None
    session = _get_session()
    params: dict[str, str | None] = {"search": search, "state": state, "max_pages": str(max_pages) if max_pages else None}

    try:
        async with OSHAClient() as client:
            case_list = await client.paginate_cases(
                search=search,
                state=state,
                date_opened_from=date(date.today().year - 3, 1, 1),
                page_size=50,
                max_pages=max_pages,
            )
        logger.info("Fetched %d case(s) from OSHA.", len(case_list))

        for case in case_list:
            try:
                result = _load_case(session, case)
                if result["success"]:
                    if result["existing"]:
                        total_updated += 1
                    else:
                        total_inserted += 1
            except Exception as exc:
                logger.error("Failed to process case id=%s: %s", case.get("id"), exc)
                total_failed += 1

        session.commit()

        # Log the API call
        log_id = _save_api_log(
            session,
            "osha_cases_search",
            params,
            {"total": len(case_list)},
            total_inserted + total_updated,
            total_failed,
            None,
        )

        # Update freshness
        from sqlalchemy import text
        session.execute(
            text(
                """INSERT INTO osha_data_freshness (id, data_type, last_updated,
                next_scheduled_update, update_frequency, status, last_run_log_id,
                error_count) VALUES (gen_random_uuid(), 'violations', CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP + INTERVAL '1 day', 'daily', 'current',
                :log_id, :failed)"""
            ),
            {"log_id": log_id, "failed": total_failed},
        )
        session.commit()

        summary = {
            "cases_fetched": len(case_list),
            "inserted": total_inserted,
            "updated": total_updated,
            "failed": total_failed,
            "log_id": log_id,
        }
        logger.info("ETL summary: %s", summary)
        return summary

    except Exception:
        logger.exception("ETL failed")
        session.rollback()
        raise
    finally:
        session.close()
        engine = _get_engine()
        engine.dispose()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="OSHA ETL Pipeline")
    parser.add_argument("--search", default=OSHA_SEARCH_TERM, help="Fuzzy company name to search")
    parser.add_argument("--state", default=OSHA_STATE_FILTER, help="US state filter (2-letter)")
    parser.add_argument("--max-pages", type=int, default=None, help="Max pagination pages")
    args = parser.parse_args()

    result = asyncio.run(run_etl(search=args.search or None, state=args.state or None, max_pages=args.max_pages))
    print("SUCCESS" if result["failed"] == 0 else "PARTIAL")
    print(result)


if __name__ == "__main__":
    main()
