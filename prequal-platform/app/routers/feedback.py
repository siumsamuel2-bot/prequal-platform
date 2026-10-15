"""Feedback API (MID-666).

Customer-care loop backend: authenticated users submit feedback; admin/org-owner
callers review and disposition it. Every submission is org-scoped server-side
from the caller's authenticated identity (never client-trusted).

Endpoints:
* ``POST   /api/v1/feedback``      - any authenticated user
* ``GET    /api/v1/feedback``      - admin/org-owner only, org-scoped, paginated
* ``PATCH  /api/v1/feedback/{id}`` - admin/org-owner only, org-scoped
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.auth import User
from app.models.feedback import FeedbackSubmission
from app.routers.auth import get_current_user, TokenData
from app.services.tenancy import (
    caller_is_org_owner as _caller_is_org_owner,
    is_admin as _is_admin,
    require_caller_org_id as _require_caller_org_id,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/feedback", tags=["feedback"])

FeedbackType = Literal["rating", "comment", "support"]
FeedbackStatus = Literal["new", "triaged", "declined", "duplicate", "resolved"]

# Dispositions that are only valid with a human-readable reason attached.
NOTE_REQUIRED_STATUSES = {"declined", "duplicate"}


class FeedbackCreate(BaseModel):
    type: FeedbackType
    surface: str = Field(..., min_length=1, max_length=100)
    page_url: Optional[str] = Field(None, max_length=1024)
    rating: Optional[int] = Field(None, ge=1, le=5)
    message: Optional[str] = Field(None, max_length=5000)


class FeedbackUpdate(BaseModel):
    status: Optional[FeedbackStatus] = None
    owner_user_id: Optional[UUID] = None
    linked_issue_id: Optional[UUID] = None
    disposition_note: Optional[str] = Field(None, max_length=5000)


class FeedbackResponse(BaseModel):
    id: str
    org_id: str
    user_id: Optional[str] = None
    type: str
    surface: str
    page_url: Optional[str] = None
    rating: Optional[int] = None
    message: Optional[str] = None
    status: str
    owner_user_id: Optional[str] = None
    linked_issue_id: Optional[str] = None
    disposition_note: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class FeedbackListResponse(BaseModel):
    """Envelope matching the frontend ``FeedbackListResponse`` contract.

    ``X-Total-Count`` remains for back-compat, but the body carries both the
    page of ``items`` and the unpaginated ``total``.
    """

    items: List[FeedbackResponse]
    total: int


def _serialize(row: FeedbackSubmission) -> FeedbackResponse:
    return FeedbackResponse(
        id=str(row.id),
        org_id=str(row.org_id),
        user_id=str(row.user_id) if row.user_id else None,
        type=row.type,
        surface=row.surface,
        page_url=row.page_url,
        rating=row.rating,
        message=row.message,
        status=row.status,
        owner_user_id=str(row.owner_user_id) if row.owner_user_id else None,
        linked_issue_id=str(row.linked_issue_id) if row.linked_issue_id else None,
        disposition_note=row.disposition_note,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def _require_review_scope(
    db: AsyncSession, current_user: TokenData
) -> Optional[UUID]:
    """Return the org id to scope review reads/writes to.

    Admins are platform-wide (``None``). A non-admin must resolve to a live
    organization *and* own it, otherwise fail closed with 403.
    """
    if _is_admin(current_user):
        return None
    org_id = await _require_caller_org_id(db, current_user)
    if not await _caller_is_org_owner(db, current_user, org_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or organization owner privileges required",
        )
    return org_id


async def _resolve_submitter_org_id(
    db: AsyncSession, current_user: TokenData
) -> UUID:
    """Resolve the submitter's org server-side; fail closed (403) if absent.

    Unlike the review path, this does **not** grant admins access to other orgs:
    every submission must belong to a concrete org, so the caller's own
    ``users.org_id`` is the only trusted source.
    """
    user_id = getattr(current_user, "user_id", None)
    try:
        user_uuid = UUID(str(user_id))
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant scope could not be resolved for this account",
        )
    result = await db.execute(select(User.org_id).where(User.id == user_uuid))
    org_id = result.scalar_one_or_none()
    if org_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant scope could not be resolved for this account",
        )
    return org_id


@router.post("", status_code=201, response_model=FeedbackResponse)
async def submit_feedback(
    payload: FeedbackCreate,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Record a feedback/support submission for the caller's organization."""
    org_id = await _resolve_submitter_org_id(db, current_user)
    user_id = UUID(str(current_user.user_id))

    submission = FeedbackSubmission(
        org_id=org_id,
        user_id=user_id,
        type=payload.type,
        surface=payload.surface,
        page_url=payload.page_url,
        rating=payload.rating,
        message=payload.message,
        status="new",
    )
    db.add(submission)
    await db.commit()
    await db.refresh(submission)
    return _serialize(submission)


@router.get("", response_model=FeedbackListResponse)
async def list_feedback(
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    status_filter: Optional[FeedbackStatus] = Query(None, alias="status"),
    type_filter: Optional[FeedbackType] = Query(None, alias="type"),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List feedback submissions scoped to the caller's org (admins: all orgs)."""
    scope_org_id = await _require_review_scope(db, current_user)

    query = select(FeedbackSubmission)
    if scope_org_id is not None:
        query = query.where(FeedbackSubmission.org_id == scope_org_id)
    if status_filter is not None:
        query = query.where(FeedbackSubmission.status == status_filter)
    if type_filter is not None:
        query = query.where(FeedbackSubmission.type == type_filter)

    total = (
        await db.execute(select(func.count()).select_from(query.subquery()))
    ).scalar() or 0

    query = (
        query.order_by(desc(FeedbackSubmission.created_at)).offset(skip).limit(limit)
    )
    rows = (await db.execute(query)).scalars().all()

    response.headers["X-Total-Count"] = str(total)
    return FeedbackListResponse(
        items=[_serialize(row) for row in rows],
        total=total,
    )


@router.patch("/{feedback_id}", response_model=FeedbackResponse)
async def update_feedback(
    feedback_id: str,
    payload: FeedbackUpdate,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Disposition a feedback submission (status/owner/issue/note).

    Org-scoped: a caller can only patch a row in the org they review. A
    ``declined``/``duplicate`` disposition requires a non-empty note (422).
    """
    scope_org_id = await _require_review_scope(db, current_user)

    try:
        submission_id = UUID(str(feedback_id))
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="feedback id must be a valid UUID",
        )

    query = select(FeedbackSubmission).where(FeedbackSubmission.id == submission_id)
    if scope_org_id is not None:
        query = query.where(FeedbackSubmission.org_id == scope_org_id)

    submission = (await db.execute(query)).scalar_one_or_none()
    if submission is None:
        # 404 (not 403) so existence in another org is never disclosed.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Feedback submission not found"
        )

    data = payload.model_dump(exclude_unset=True)
    # ``status`` is NOT NULL: an explicit null means "no change", not "clear".
    if data.get("status") is None:
        data.pop("status", None)
    effective_status = data.get("status", submission.status)
    effective_note = data.get("disposition_note", submission.disposition_note)
    if effective_status in NOTE_REQUIRED_STATUSES and not (
        effective_note and effective_note.strip()
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"A disposition_note is required when status is '{effective_status}'"
            ),
        )

    for field, value in data.items():
        setattr(submission, field, value)

    await db.commit()
    await db.refresh(submission)
    return _serialize(submission)
