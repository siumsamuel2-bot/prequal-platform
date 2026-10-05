"""Backend API for the source-DB connector.

Exposes the health, retry policy, circuit-breaker state and metrics of the
resilient source database connector (``app.services.source_db_connector``), and
provides an admin-only read-only query passthrough for operational debugging.
"""

import logging
import re
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.routers.auth import TokenData, get_current_user, require_admin
from app.services.source_db_connector import (
    RETRYABLE_ERROR_CODES,
    NON_RETRYABLE_ERROR_CODES,
    CircuitOpenError,
    RetryConfig,
    SourceDBConnector,
    classify_error,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/source-db", tags=["source-db"])


# Operational API uses a short, bounded retry policy so health probes fail
# fast instead of blocking a request for the full pipeline retry budget.
_API_RETRY_CONFIG = RetryConfig(
    max_retries=2,
    base_delay=0.2,
    max_delay=1.0,
    timeout_seconds=5.0,
)

connector = SourceDBConnector(retry=_API_RETRY_CONFIG)

# Leading keywords that are safe to execute through the connector. Anything
# else (INSERT/UPDATE/DELETE/DDL/multiple statements) is rejected.
_READ_ONLY_PATTERN = re.compile(r"^\s*(select|with|explain|show|table|values)\b", re.IGNORECASE)
_FORBIDDEN_PATTERN = re.compile(
    r"\b(insert|update|delete|drop|alter|truncate|create|grant|revoke|copy|merge|call|do)\b",
    re.IGNORECASE,
)


class QueryRequest(BaseModel):
    sql: str = Field(..., min_length=1, description="Read-only SQL statement")
    params: Optional[Dict[str, Any]] = Field(default=None, description="Bind parameters")


def _assert_read_only(sql: str) -> None:
    """Reject anything that is not a single read-only statement."""
    stripped = sql.strip().rstrip(";")
    if not _READ_ONLY_PATTERN.match(stripped):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only read-only statements (SELECT/WITH/EXPLAIN/SHOW/TABLE/VALUES) are allowed",
        )
    # Disallow stacked statements and any write keyword.
    if ";" in stripped:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Multiple SQL statements are not allowed",
        )
    match = _FORBIDDEN_PATTERN.search(stripped)
    if match:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Write operation '{match.group(0)}' is not allowed",
        )


@router.get("/health", summary="Source-DB connector health")
async def connector_health() -> Dict[str, Any]:
    """Return connector reachability, retry policy and breaker state."""
    report = await connector.test_connection()
    return {
        "status": "healthy" if report["connected"] else "unhealthy",
        "component": "source-db-connector",
        **report,
    }


@router.get("/retry-config", summary="Active retry policy")
async def retry_config(current_user: TokenData = Depends(get_current_user)) -> Dict[str, Any]:
    config = connector.get_retry_config()
    return {
        **config.to_dict(),
        "retryable_error_codes": sorted(RETRYABLE_ERROR_CODES),
        "non_retryable_error_codes": sorted(NON_RETRYABLE_ERROR_CODES),
    }


@router.get("/circuit-breaker", summary="Circuit breaker state")
async def circuit_breaker_state(
    current_user: TokenData = Depends(get_current_user),
) -> Dict[str, Any]:
    return connector.circuit_breaker.snapshot()


@router.get("/metrics", summary="Connector metrics")
async def connector_metrics(current_user: TokenData = Depends(get_current_user)) -> Dict[str, Any]:
    return connector.metrics.snapshot()


@router.post("/metrics/reset", summary="Reset connector metrics")
async def reset_connector_metrics(
    current_user: TokenData = Depends(require_admin),
) -> Dict[str, Any]:
    connector.metrics.reset()
    connector.circuit_breaker.reset()
    return {"status": "reset"}


@router.post("/test-connection", summary="Test source-DB connectivity")
async def test_connection(
    current_user: TokenData = Depends(get_current_user),
) -> Dict[str, Any]:
    return await connector.test_connection()


@router.post("/query", summary="Run a read-only query through the connector")
async def run_query(
    payload: QueryRequest,
    current_user: TokenData = Depends(require_admin),
) -> Dict[str, Any]:
    _assert_read_only(payload.sql)
    try:
        result = await connector.query(payload.sql, payload.params)
    except CircuitOpenError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        classification = classify_error(exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": str(exc), "classification": classification},
        )
    return result.to_dict()
