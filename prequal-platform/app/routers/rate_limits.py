"""
Admin API for viewing and managing rate limit rules and DDoS protection.

All endpoints require an authenticated ``admin`` user and let operators
adjust limits at runtime without a code change or redeploy:

- GET    /api/admin/rate-limits/tiers            list named tiers
- PUT    /api/admin/rate-limits/tiers/{name}      update a tier limit
- POST   /api/admin/rate-limits/tiers/reset       restore default tiers
- GET    /api/admin/rate-limits/rules             list per-route rules
- POST   /api/admin/rate-limits/rules             create/update a route rule
- DELETE /api/admin/rate-limits/rules/{rule_id}   delete a route rule
- POST   /api/admin/rate-limits/resolve           preview the effective limit
- GET    /api/admin/rate-limits/stats             live rate limit metrics
- GET    /api/admin/rate-limits/blocked           list temporarily banned IPs
- POST   /api/admin/rate-limits/blocked           manually block an IP
- DELETE /api/admin/rate-limits/blocked/{ip}      unblock an IP

Owner: Backend Engineer
Ticket: MID-593
"""

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.middleware.rate_limit import (
    DEFAULT_TIERS,
    RateLimitMetrics,
    RateLimitRule,
    _validate_limit_string,
    rate_limit_config,
)
from app.routers.auth import require_admin

router = APIRouter(prefix="/api/admin/rate-limits", tags=["rate-limits"])


class TierUpdate(BaseModel):
    limit: str = Field(..., examples=["100/minute"])


class RuleCreate(BaseModel):
    id: Optional[str] = None
    path_prefix: str = Field(..., examples=["/api/analytics"])
    methods: Optional[List[str]] = None
    tier: str = "authenticated_write"
    applies_to: str = "any"
    enabled: bool = True
    description: str = ""


class BlockRequest(BaseModel):
    ip: str
    seconds: int = 300


class ResolveRequest(BaseModel):
    path: str
    method: str = "GET"
    authenticated: bool = False


def _invalid_limit(limit: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=(
            f"Invalid limit {limit!r}; expected '<amount>/<second|minute|hour|day>', "
            "e.g. '100/minute'"
        ),
    )


@router.get("/tiers")
async def list_tiers(_=Depends(require_admin)):
    """List all named rate limit tiers and their current values."""
    return {"defaults": DEFAULT_TIERS, "tiers": rate_limit_config.list_tiers()}


@router.put("/tiers/{name}")
async def update_tier(name: str, payload: TierUpdate, _=Depends(require_admin)):
    """Update a named tier limit (e.g. ``unauthenticated_login``)."""
    try:
        value = rate_limit_config.set_tier(name, payload.limit)
    except ValueError:
        raise _invalid_limit(payload.limit)
    return {"name": name, "limit": value}


@router.post("/tiers/reset")
async def reset_tiers(_=Depends(require_admin)):
    """Restore all named tiers to their shipped defaults."""
    return {"tiers": rate_limit_config.reset_tiers()}


@router.get("/rules")
async def list_rules(_=Depends(require_admin)):
    """List per-route rate limit rules."""
    return {"rules": rate_limit_config.list_rules()}


@router.post("/rules")
async def upsert_rule(payload: RuleCreate, _=Depends(require_admin)):
    """Create or update a per-route rule.

    Rules are matched by ``path_prefix`` (plus optional ``methods`` and
    authentication scope) and take precedence over the default tiers.
    """
    if payload.tier not in rate_limit_config.list_tiers():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown tier {payload.tier!r}; create the tier first",
        )
    if payload.applies_to not in ("any", "authenticated", "unauthenticated"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="applies_to must be one of: any, authenticated, unauthenticated",
        )
    rule = RateLimitRule(
        rule_id=payload.id or uuid.uuid4().hex[:12],
        path_prefix=payload.path_prefix,
        methods=payload.methods,
        tier=payload.tier,
        applies_to=payload.applies_to,
        enabled=payload.enabled,
        description=payload.description,
    )
    return rate_limit_config.upsert_rule(rule)


@router.delete("/rules/{rule_id}")
async def delete_rule(rule_id: str, _=Depends(require_admin)):
    if not rate_limit_config.delete_rule(rule_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
    return {"deleted": rule_id}


@router.post("/resolve")
async def resolve_limit(payload: ResolveRequest, _=Depends(require_admin)):
    """Preview which limit would apply to a synthetic request."""
    limit, source = rate_limit_config.resolve_limit(
        payload.path, payload.method, payload.authenticated
    )
    return {"path": payload.path, "method": payload.method, "limit": limit, "source": source}


@router.get("/stats")
async def get_stats(_=Depends(require_admin)):
    """Return live rate limit and DDoS metrics."""
    return {
        "limits": RateLimitMetrics.get_stats(),
        "blocked": rate_limit_config.list_blocked(),
    }


@router.get("/blocked")
async def list_blocked(_=Depends(require_admin)):
    return {"blocked": rate_limit_config.list_blocked()}


@router.post("/blocked")
async def block_ip(payload: BlockRequest, _=Depends(require_admin)):
    rate_limit_config.block_ip(payload.ip, payload.seconds)
    RateLimitMetrics.record_blocked(payload.ip, "admin", "manual block")
    return {"ip": payload.ip, "seconds": payload.seconds}


@router.delete("/blocked/{ip}")
async def unblock_ip(ip: str, _=Depends(require_admin)):
    if not rate_limit_config.unblock_ip(ip):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="IP not blocked")
    return {"unblocked": ip}


@router.post("/reset-metrics")
async def reset_metrics(_=Depends(require_admin)):
    RateLimitMetrics.clear()
    return {"reset": True}
