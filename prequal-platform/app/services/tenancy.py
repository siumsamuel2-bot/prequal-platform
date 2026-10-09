"""Shared tenant-scoping helpers for multi-tenant read isolation.

The caller's team is resolved from the live ``team_members`` table rather than
the (potentially stale) JWT ``team_id`` claim, so a user who changed teams after
a token was issued cannot read their previous team's data.

Convention used by every caller:

* ``resolve_caller_team_id`` returns ``None`` for admins (who are intentionally
  platform-wide) **and** for non-admins whose team cannot be resolved.
* A non-admin that resolves to ``None`` must be treated as *no access*
  (fail closed), never as unscoped access. Use :func:`is_admin` to distinguish,
  or :func:`require_caller_team_id` which raises instead of returning ``None``.

Owner: Backend Engineer (MID-650 tenant-isolation hardening).
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import TeamMember
from app.schemas.compliance import TokenData


def is_admin(current_user: TokenData) -> bool:
    """True when the caller is a platform administrator (unscoped access)."""
    return getattr(current_user, "role", "viewer") == "admin"


async def resolve_caller_team_id(
    db: AsyncSession, current_user: TokenData
) -> Optional[UUID]:
    """Resolve the caller's team id from live DB membership.

    Returns ``None`` for admins and for any caller whose identity or team cannot
    be resolved. Callers MUST treat ``None`` for a non-admin as "no access".
    """
    if is_admin(current_user):
        return None
    user_id = getattr(current_user, "user_id", None)
    if not user_id:
        return None
    try:
        user_uuid = UUID(str(user_id))
    except (ValueError, TypeError):
        return None
    result = await db.execute(
        select(TeamMember.team_id).where(TeamMember.user_id == user_uuid)
    )
    return result.scalar_one_or_none()


async def require_caller_team_id(
    db: AsyncSession, current_user: TokenData
) -> Optional[UUID]:
    """Team id for scoped endpoints. Admins get ``None`` (unscoped).

    Raises HTTP 403 for a non-admin caller whose team cannot be resolved, which
    is the fail-closed behaviour required for cross-tenant read endpoints.
    """
    if is_admin(current_user):
        return None
    team_id = await resolve_caller_team_id(db, current_user)
    if team_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant scope could not be resolved for this account",
        )
    return team_id
