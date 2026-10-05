"""State compliance data sources API."""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.state_compliance import StateComplianceSource
from app.services.state_compliance_service import (
    lookup_contractor_in_state,
    sync_state_credentials,
    check_contractor_across_states
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/compliance/states", tags=["state-compliance"])


class StateSourceResponse:
    def __init__(self, id: str, state_code: str, state_name: str, is_active: bool, priority: int,
                 source_type: str, last_sync_at: Optional[str], records_synced: int):
        self.id = id
        self.state_code = state_code
        self.state_name = state_name
        self.is_active = is_active
        self.priority = priority
        self.source_type = source_type
        self.last_sync_at = last_sync_at
        self.records_synced = records_synced


@router.get("/sources")
async def list_state_sources(
    db: AsyncSession = Depends(get_db),
    active_only: bool = Query(False)
):
    query = select(StateComplianceSource)
    if active_only:
        query = query.where(StateComplianceSource.is_active == True)
    query = query.order_by(StateComplianceSource.priority)

    result = await db.execute(query)
    sources = result.scalars().all()

    return [
        {
            "id": str(s.id),
            "state_code": s.state_code,
            "state_name": s.state_name,
            "is_active": s.is_active,
            "priority": s.priority,
            "source_type": s.source_type,
            "last_sync_at": s.last_sync_at.isoformat() if s.last_sync_at else None,
            "records_synced": s.records_synced
        }
        for s in sources
    ]


@router.get("/sources/{state_code}")
async def get_state_source(state_code: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(StateComplianceSource).where(StateComplianceSource.state_code == state_code.upper())
    )
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail=f"State {state_code} not found")

    return {
        "id": str(source.id),
        "state_code": source.state_code,
        "state_name": source.state_name,
        "is_active": source.is_active,
        "priority": source.priority,
        "source_type": source.source_type,
        "last_sync_at": source.last_sync_at.isoformat() if source.last_sync_at else None,
        "records_synced": source.records_synced
    }


@router.get("/lookup/{state_code}")
async def lookup_in_state(
    state_code: str,
    q: str = Query(..., min_length=2),
    credential_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    return await lookup_contractor_in_state(state_code, q, db, credential_type=credential_type)


@router.get("/search")
async def search_across_states(
    company_name: str = Query(..., min_length=2),
    db: AsyncSession = Depends(get_db)
):
    return await check_contractor_across_states(company_name, db)


@router.post("/sync/{state_code}")
async def trigger_state_sync(state_code: str, db: AsyncSession = Depends(get_db)):
    return await sync_state_credentials(state_code, db=db)


@router.post("/sources")
async def create_state_source(
    state_code: str,
    state_name: str,
    source_type: str = "license_board",
    api_url: Optional[str] = None,
    api_key_env_var: Optional[str] = None,
    priority: int = 0,
    db: AsyncSession = Depends(get_db)
):
    existing = await db.execute(
        select(StateComplianceSource).where(StateComplianceSource.state_code == state_code.upper())
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"State {state_code} already exists")

    source = StateComplianceSource(
        state_code=state_code.upper(),
        state_name=state_name,
        source_type=source_type,
        api_url=api_url,
        api_key_env_var=api_key_env_var,
        priority=priority
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)

    return {
        "id": str(source.id),
        "state_code": source.state_code,
        "state_name": source.state_name,
        "is_active": source.is_active,
        "priority": source.priority,
        "source_type": source.source_type
    }