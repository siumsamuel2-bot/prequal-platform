from fastapi import APIRouter

from app.api.endpoints import events, ingestion, reports

api_router = APIRouter()

api_router.include_router(events.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(ingestion.router, prefix="/analytics", tags=["ingestion"])
api_router.include_router(reports.router, prefix="/analytics", tags=["reports"])
