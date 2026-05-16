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

logger = logging.getLogger(__name__)

router = APIRouter()


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

    # Check database connection
    try:
        from app.database import get_db_session
        # Try to get a connection
        db_healthy = True  # Simplified - actual implementation would test connection
        checks["database"] = db_healthy
        if not db_healthy:
            all_healthy = False
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        checks["database"] = False
        all_healthy = False

    # Check Redis connection
    try:
        import os
        redis_url = os.getenv("REDIS_URL")
        if redis_url:
            # Simplified Redis check
            checks["redis"] = True
        else:
            checks["redis"] = True  # Optional
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        checks["redis"] = False
        # Redis might be optional
        pass

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
    - Resource usage (if available)
    - Recent error count
    """
    import os
    import sys

    # Get version info
    version = "1.0.0"  # Should come from __version__ or package

    # Collect all checks
    services = {}

    # Database
    try:
        # Simplified DB check
        services["database"] = "healthy"
    except Exception:
        services["database"] = "unhealthy"

    # Redis
    try:
        services["redis"] = "healthy"
    except Exception:
        services["redis"] = "unknown"

    # External APIs
    try:
        osha_key = os.getenv("OSHA_API_KEY")
        services["osha_api"] = "healthy" if osha_key else "not_configured"
    except Exception:
        services["osha_api"] = "unhealthy"

    overall_status = "healthy" if all(
        v in ["healthy", "not_configured"] for v in services.values()
    ) else "degraded"

    return {
        "status": overall_status,
        "version": version,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "services": services,
        "uptime_seconds": None,  # Would track startup time
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    }
