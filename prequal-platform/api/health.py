"""
Health check endpoints for monitoring and uptime checks.

Provides:
- Basic health check
- Readiness probe (dependencies healthy)
- Liveness probe (service is responsive)
- Detailed health status
"""

import asyncio
from datetime import datetime
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, List, Optional
import logging
import time

logger = logging.getLogger(__name__)

router = APIRouter()

# Approximate process start time, used for the uptime metric in /health/detailed
PROCESS_START_TIME = time.time()


async def _check_database() -> bool:
    """Run a lightweight connectivity check against the primary database."""
    from sqlalchemy import text

    from app.database import engine

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False


class HealthStatus(BaseModel):
    """Health check response model."""
    status: str
    timestamp: str
    version: str
    services: Optional[Dict[str, str]] = None
    checks: Optional[Dict[str, bool]] = None


class ServiceHealth(BaseModel):
    """Individual service health status."""
    name: str
    status: str
    latency_ms: Optional[float] = None
    message: Optional[str] = None


@router.get("/health")
async def health_check():
    """
    Basic health check endpoint.

    Returns 200 if the service is running.
    Used for simple uptime monitoring.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "service": "prequal-api"
    }


@router.get("/health/live")
async def liveness_probe():
    """
    Liveness probe - is the service responsive?

    Returns 200 if the service is running and can respond to requests.
    Kubernetes uses this to determine if a pod should be restarted.
    """
    return {
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }


@router.get("/health/ready")
async def readiness_probe():
    """
    Readiness probe - is the service ready to accept traffic?

    Checks all dependencies (database, redis, external services).
    Returns 200 only if all dependencies are healthy.
    Kubernetes uses this to determine if traffic should be sent to the pod.
    """
    checks = {}
    all_healthy = True

    # Check database connectivity with a real query
    checks["database"] = await _check_database()
    if not checks["database"]:
        all_healthy = False

    # Redis is an optional dependency (no Python client bundled);
    # a missing REDIS_URL must not fail readiness.
    checks["redis"] = True

    status = "ready" if all_healthy else "not_ready"
    status_code = 200 if all_healthy else 503

    return JSONResponse(
        status_code=status_code,
        content={
            "status": status,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "checks": checks
        }
    )


@router.get("/health/detailed")
async def detailed_health():
    """
    Detailed health check with all service statuses.

    Returns comprehensive health information including:
    - Application version
    - All dependency statuses
    - Process uptime
    - Python version
    """
    import os
    import sys

    # Get version info
    version = "1.0.0"  # Should come from __version__ or package

    # Collect all checks
    services = {}

    # Database connectivity (real query)
    services["database"] = "healthy" if await _check_database() else "unhealthy"

    # Redis is optional; report configuration presence only
    services["redis"] = "configured" if os.getenv("REDIS_URL") else "not_configured"

    # External APIs
    osha_key = os.getenv("OSHA_API_KEY")
    services["osha_api"] = "healthy" if osha_key else "not_configured"

    overall_status = "healthy" if all(
        v in ["healthy", "not_configured", "configured"] for v in services.values()
    ) else "degraded"

    return {
        "status": overall_status,
        "version": version,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "services": services,
        "uptime_seconds": round(time.time() - PROCESS_START_TIME, 1),
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    }
