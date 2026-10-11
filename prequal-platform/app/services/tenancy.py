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

from app.models.auth import OrganizationMembership, TeamMember, User
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


async def resolve_caller_org_id(
    db: AsyncSession, current_user: TokenData
) -> Optional[UUID]:
    """Resolve the caller's organization id from live DB state.

    Returns ``None`` for admins (who are intentionally platform-wide) **and** for
    any caller whose user row or ``org_id`` cannot be resolved. Callers MUST
    treat ``None`` for a non-admin as "no access" (fail closed).
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
    result = await db.execute(select(User.org_id).where(User.id == user_uuid))
    return result.scalar_one_or_none()


async def require_caller_org_id(
    db: AsyncSession, current_user: TokenData
) -> Optional[UUID]:
    """Org id for org-scoped endpoints. Admins get ``None`` (unscoped).

    Raises HTTP 403 for a non-admin caller whose organization cannot be
    resolved, which is the fail-closed behaviour required for cross-tenant
    endpoints (parity with :func:`require_caller_team_id`).
    """
    if is_admin(current_user):
        return None
    org_id = await resolve_caller_org_id(db, current_user)
    if org_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant scope could not be resolved for this account",
        )
    return org_id


async def caller_is_org_owner(
    db: AsyncSession, current_user: TokenData, org_id: UUID
) -> bool:
    """True when a non-admin caller owns ``org_id``.

    Ownership is resolved server-side: an ``organization_memberships`` row with
    role ``owner``/``admin`` for the org, or (fallback for accounts provisioned
    before org memberships existed) a ``team_members`` row with role ``owner``.
    Never trust a client-supplied role/org.
    """
    user_id = getattr(current_user, "user_id", None)
    if not user_id:
        return False
    try:
        user_uuid = UUID(str(user_id))
    except (ValueError, TypeError):
        return False

    membership_roles = await db.execute(
        select(OrganizationMembership.role).where(
            OrganizationMembership.user_id == user_uuid,
            OrganizationMembership.org_id == org_id,
        )
    )
    if any((row[0] or "").lower() in {"owner", "admin"} for row in membership_roles.all()):
        return True

    team_roles = await db.execute(
        select(TeamMember.role).where(TeamMember.user_id == user_uuid)
    )
    return any((row[0] or "").lower() == "owner" for row in team_roles.all())
