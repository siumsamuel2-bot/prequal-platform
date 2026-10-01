"""State compliance data integration service.

Provides unified credential lookups, syncing, and validation across state
licensing board APIs.  Delegates ETL work to the external compliance pipeline
and wraps it with domain-level error handling.

Owner: Data Engineer
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.state_compliance import StateComplianceSource
from app.models.compliance import StateCredentialRecord
from app.services.external_compliance_pipeline import (
    run_state_credential_sync,
    validate_pipeline_health,
    PipelineRun,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Supported state codes loaded from environment variables STATE_API_URL_{CODE}.
SUPPORTED_STATE_CODES = {
    k.replace("STATE_API_URL_", ""): v
    for k, v in os.environ.items()
    if k.startswith("STATE_API_URL_")
}


# ---------------------------------------------------------------------------
# Public Service API
# ---------------------------------------------------------------------------


async def get_active_sources(db: AsyncSession) -> List[StateComplianceSource]:
    """Return all active state compliance sources ordered by priority."""
    from sqlalchemy import select
    result = await db.execute(
        select(StateComplianceSource)
        .where(StateComplianceSource.is_active == True)  # noqa: E712
        .order_by(StateComplianceSource.priority)
    )
    return list(result.scalars().all())


async def lookup_contractor_in_state(
    state_code: str,
    query: str,
    db: AsyncSession,
    credential_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Look up a contractor in a single state's credential database.
    
    Searches state_credential_records for records matching the query
    by holder_name (business name) or credential_number.
    """
    from sqlalchemy import select, or_
    source_result = await db.execute(
        select(StateComplianceSource).where(
            StateComplianceSource.state_code == state_code.upper()
        )
    )
    source = source_result.scalar_one_or_none()
    if not source:
        return {"status": "not_found", "message": f"State {state_code} not configured"}

    search_pattern = f"%{query}%"
    stmt = select(StateCredentialRecord).where(
        StateCredentialRecord.state_code == state_code.upper(),
        or_(
            StateCredentialRecord.holder_name.ilike(search_pattern),
            StateCredentialRecord.credential_number.ilike(search_pattern),
        )
    )
    if credential_type:
        stmt = stmt.where(StateCredentialRecord.credential_type == credential_type)
    
    stmt = stmt.order_by(StateCredentialRecord.expiration_date.asc()).limit(50)
    result = await db.execute(stmt)
    records = result.scalars().all()

    source.last_sync_at = datetime.utcnow()
    await db.commit()

    return {
        "status": "success",
        "state": state_code,
        "query": query,
        "last_sync": source.last_sync_at.isoformat() if source.last_sync_at else None,
        "records_synced": source.records_synced,
        "records_found": len(records),
        "results": [
            {
                "id": str(r.id),
                "credential_number": r.credential_number,
                "credential_type": r.credential_type,
                "holder_name": r.holder_name,
                "status": r.status,
                "expiration_date": r.expiration_date.isoformat() if r.expiration_date else None,
                "issuing_state": r.issuing_state,
                "external_source_url": r.external_source_url,
            }
            for r in records
        ],
    }


async def sync_state_credentials(
    state_code: str,
    *,
    db: AsyncSession | None = None,
    triggered_by: str = "schedule",
    search_query: str = "",
    max_results: int = 100,
) -> Dict[str, Any]:
    """Sync state-level credentials for *state_code* using the production ETL.

    This is the canonical entry-point for state compliance data ingestion.
    Delegates to the external compliance pipeline, then validates the
    pipeline health.
    """
    close_db = False
    if db is None:
        db = AsyncSessionLocal()
        close_db = True

    run: Optional[PipelineRun] = None
    try:
        run = await run_state_credential_sync(
            db=db,
            state_code=state_code,
            triggered_by=triggered_by,
            search_query=search_query,
            max_results=max_results,
        )

        validation = await validate_pipeline_health(db)

        return {
            "status": run.status,
            "state": state_code,
            "run_id": str(run.id),
            "extracted": run.records_extracted,
            "inserted": run.records_inserted,
            "updated": run.records_updated,
            "failed": run.records_failed,
            "matched": run.records_matched,
            "validation": validation,
        }
    finally:
        if close_db and db is not None:
            await db.close()


async def check_contractor_across_states(
    company_name: str,
    db: AsyncSession,
) -> Dict[str, Any]:
    """Check a contractor's credentials across all configured states."""
    sources = await get_active_sources(db)
    results: Dict[str, Any] = {}

    for source in sources:
        result = await lookup_contractor_in_state(
            source.state_code, company_name, db=db
        )
        results[source.state_code] = result

    return {
        "company_name": company_name,
        "states_checked": len(sources),
        "results": results,
    }


async def full_state_pipeline_sync(
    state_codes: Optional[List[str]] = None,
    triggered_by: str = "schedule",
) -> Dict[str, Any]:
    """Run the full state-level compliance sync for one or more states.

    If *state_codes* is omitted, all states with a configured STATE_API_URL_*
    environment variable are processed.
    """
    codes = state_codes or list(SUPPORTED_STATE_CODES.keys())
    if not codes:
        return {"status": "no_states_configured", "results": {}}

    overall = {
        "started_at": datetime.utcnow().isoformat(),
        "results": {},
    }

    db = AsyncSessionLocal()
    try:
        for sc in codes:
            try:
                result = await sync_state_credentials(
                    sc, db=db, triggered_by=triggered_by
                )
                overall["results"][sc] = result
            except Exception as exc:
                logger.exception("State sync failed for %s", sc)
                overall["results"][sc] = {"status": "failed", "error": str(exc)}
    finally:
        await db.close()

    overall["completed_at"] = datetime.utcnow().isoformat()
    return overall
