import csv
import io
import logging
from datetime import date, timedelta

logger = logging.getLogger(__name__)
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.compliance import (
    Subcontractor, Project, Certification, Violation,
    ProjectSubcontractor, AlertPreference, AlertNotification,
    CertificationRenewal
)
from app.schemas.compliance import (
    SubcontractorCreate, SubcontractorUpdate, SubcontractorResponse, SubcontractorWithDetails,
    CertificationCreate, CertificationUpdate, CertificationResponse, CertificationWithSubcontractor,
    SubcontractorCertificationCreate,
    ViolationCreate, ViolationUpdate, ViolationResponse, ViolationWithSubcontractor,
    ProjectCreate, ProjectUpdate, ProjectResponse, ProjectWithSubcontractors,
    ProjectSubcontractorCreate, ProjectSubcontractorUpdate, ProjectSubcontractorResponse,
    ComplianceStatusResponse, DashboardSummary,
    AlertPreferenceCreate, AlertPreferenceUpdate, AlertPreferenceResponse,
    AlertNotificationUpdate, AlertNotificationResponse,
    CertificationRenewalCreate, CertificationRenewalUpdate, CertificationRenewalResponse,
    SubcontractorStatus, CertificationStatus, ViolationStatus,
    ComplianceSummaryResponse, ComplianceTrendPoint, CertificationExportRow
)
from app.routers.auth import get_current_user, TokenData
from app.services.analytics_pipeline import (
    get_compliance_summary,
    get_compliance_trends,
    get_certification_export_rows,
)
from app.services.pdf_service import (
    generate_subcontractor_pdf,
    generate_compliance_dashboard_pdf,
)
from app.services.encryption_service import encrypt_value, decrypt_value
from app.services.security_service import log_data_access
from app.services.cache_service import (
    build_cache_key,
    cache_service,
    get_cache_stats,
)

router = APIRouter(prefix="/api", tags=["compliance"])


async def _invalidate_compliance_cache(team_id: Optional[UUID]) -> None:
    """Invalidate cached compliance responses for a team after a write."""
    try:
        await cache_service.invalidate_team_cache(team_id)
    except Exception:  # pragma: no cover - cache must never break a write
        logger.warning("Failed to invalidate compliance cache", exc_info=True)


@router.get("/cache/stats")
async def get_cache_statistics(
    current_user: TokenData = Depends(get_current_user),
):
    """Cache hit/miss monitoring for the compliance dashboard endpoints.

    Returns aggregate counters plus whether the Redis backend is reachable.
    Intended for dashboards/alerting and TTL tuning.
    """
    stats = get_cache_stats()
    stats["cache_available"] = await cache_service.is_available()
    return stats


def get_subcontractor_ein(subcontractor: Subcontractor) -> Optional[str]:
    if subcontractor.encrypted_ein:
        return decrypt_value(subcontractor.encrypted_ein)
    return subcontractor.ein


PII_FIELDS = [
    'contact_first_name',
    'contact_last_name',
    'phone',
    'address_line1',
    'address_line2',
    'city',
    'state',
    'zip_code',
]


def decrypt_pii(subcontractor: Subcontractor, field: str) -> Optional[str]:
    encrypted_val = getattr(subcontractor, f"encrypted_{field}", None)
    if encrypted_val:
        return decrypt_value(encrypted_val)
    return getattr(subcontractor, field, None)


def _subcontractor_response_data(sub: Subcontractor) -> dict:
    """Build detached response data for a subcontractor with decrypted PII.

    Returns a plain dict instead of mutating the ORM object: pending
    attribute writes on the ORM instance would otherwise leak into later
    commits on the same session (e.g. audit-log commits), persisting
    plaintext PII back into the database and expiring server-managed
    columns like ``updated_at``.
    """
    return {
        "id": sub.id,
        "company_name": sub.company_name,
        "contact_first_name": decrypt_pii(sub, "contact_first_name") or sub.contact_first_name,
        "contact_last_name": decrypt_pii(sub, "contact_last_name") or sub.contact_last_name,
        "email": decrypt_pii(sub, "email") or sub.email,
        "phone": decrypt_pii(sub, "phone") or sub.phone,
        "address_line1": decrypt_pii(sub, "address_line1") or sub.address_line1,
        "address_line2": decrypt_pii(sub, "address_line2") or sub.address_line2,
        "city": decrypt_pii(sub, "city") or sub.city,
        "state": decrypt_pii(sub, "state") or sub.state,
        "zip_code": decrypt_pii(sub, "zip_code") or sub.zip_code,
        "country": sub.country,
        "ein": get_subcontractor_ein(sub),
        "license_number": sub.license_number,
        "license_state": sub.license_state,
        "license_expiration": sub.license_expiration,
        "status": sub.status,
        "created_at": sub.created_at,
        "updated_at": sub.updated_at,
    }


CLIENT_FIELDS = [
    'client_name',
    'client_contact',
]


def decrypt_client(project: Project, field: str) -> Optional[str]:
    encrypted_val = getattr(project, f"encrypted_{field}", None)
    if encrypted_val:
        return decrypt_value(encrypted_val)
    return getattr(project, field, None)


def _encrypt_client_fields(proj: Project, data: dict) -> None:
    for field in CLIENT_FIELDS:
        val = data.get(field)
        if val:
            setattr(proj, f"encrypted_{field}", encrypt_value(val))
            setattr(proj, field, None)


def _encrypt_pii_fields(sub: Subcontractor, data: dict) -> None:
    for field in PII_FIELDS:
        val = data.get(field)
        if val:
            setattr(sub, f"encrypted_{field}", encrypt_value(val))
            setattr(sub, field, None)
    if data.get("ein"):
        setattr(sub, "encrypted_ein", encrypt_value(data["ein"]))
        setattr(sub, "ein", None)
    if data.get("email"):
        setattr(sub, "encrypted_email", encrypt_value(data["email"]))


async def get_subcontractor_compliance_score(
    db: AsyncSession, 
    subcontractor_id: UUID
) -> float:
    result = await db.execute(
        select(func.count(Certification.id)).where(
            and_(
                Certification.subcontractor_id == subcontractor_id,
                Certification.status == CertificationStatus.VALID.value
            )
        )
    )
    valid_certs = result.scalar() or 0
    
    result = await db.execute(
        select(func.count(Violation.id)).where(
            and_(
                Violation.subcontractor_id == subcontractor_id,
                Violation.status.in_([ViolationStatus.OPEN.value, ViolationStatus.UNDER_REVIEW.value])
            )
        )
    )
    open_violations = result.scalar() or 0
    
    if valid_certs == 0 and open_violations == 0:
        return 100.0
    
    score = max(0, min(100, (valid_certs * 10) - (open_violations * 20)))
    return float(score)


@router.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": date.today().isoformat()}


@router.get("/subcontractors", response_model=List[SubcontractorResponse])
async def get_subcontractors(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status_filter: Optional[SubcontractorStatus] = None,
    search: Optional[str] = None,
    state: Optional[str] = Query(None, max_length=50, description="Filter by business address state"),
    city: Optional[str] = Query(None, max_length=100, description="Filter by business address city"),
    license_state: Optional[str] = Query(None, max_length=50, description="Filter by license issuing state"),
    license_expiring_within_days: Optional[int] = Query(None, ge=0, le=3650, description="Only subcontractors whose license expires within N days"),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    team_id = UUID(current_user.team_id) if current_user.team_id else None
    cache_key = build_cache_key(
        "subcontractors",
        team_id=str(team_id),
        status_filter=status_filter.value if status_filter else None,
        search=search,
        state=state,
        city=city,
        license_state=license_state,
        license_expiring_within_days=license_expiring_within_days,
        skip=skip,
        limit=limit,
    )

    cached = await cache_service.get(cache_key)
    if cached is not None:
        if request:
            client_ip = request.client.host if request.client else None
            await log_data_access(
                db=db,
                action="cache_hit",
                resource="subcontractors",
                resource_id="list",
                user_id=UUID(current_user.user_id),
                ip_address=client_ip,
                details=f"Cache hit for subcontractors list (key: {cache_key[:16]}...)"
            )
        return cached

    query = select(Subcontractor)

    if team_id:
        query = query.where(Subcontractor.team_id == team_id)

    if status_filter:
        query = query.where(Subcontractor.status == status_filter.value)

    if search:
        search_term = f"%{search}%"
        query = query.where(
            or_(
                Subcontractor.company_name.ilike(search_term),
                Subcontractor.email.ilike(search_term)
            )
        )

    if state:
        query = query.where(func.lower(Subcontractor.state) == state.lower())

    if city:
        query = query.where(func.lower(Subcontractor.city) == city.lower())

    if license_state:
        query = query.where(func.lower(Subcontractor.license_state) == license_state.lower())

    if license_expiring_within_days is not None:
        cutoff = date.today() + timedelta(days=license_expiring_within_days)
        query = query.where(Subcontractor.license_expiration != None).where(  # noqa: E711
            Subcontractor.license_expiration <= cutoff
        )

    query = query.offset(skip).limit(limit).order_by(Subcontractor.created_at.desc())
    result = await db.execute(query)
    subcontractors = result.scalars().all()
    response_data = [_subcontractor_response_data(sub) for sub in subcontractors]

    await cache_service.set(cache_key, response_data)

    if request:
        client_ip = request.client.host if request.client else None
        await log_data_access(
            db=db,
            action="cache_miss",
            resource="subcontractors",
            resource_id="list",
            user_id=UUID(current_user.user_id),
            ip_address=client_ip,
            details=f"Cache miss for subcontractors list (key: {cache_key[:16]}...)"
        )

    return response_data


@router.get("/subcontractors/{subcontractor_id}", response_model=SubcontractorWithDetails)
async def get_subcontractor(
    subcontractor_id: UUID,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    team_id = UUID(current_user.team_id) if current_user.team_id else None
    conditions = [Subcontractor.id == subcontractor_id]
    if team_id:
        conditions.append(Subcontractor.team_id == team_id)
    result = await db.execute(
        select(Subcontractor)
        .options(
            selectinload(Subcontractor.certifications),
            selectinload(Subcontractor.violations),
            selectinload(Subcontractor.project_assignments)
        )
        .where(and_(*conditions))
    )
    subcontractor = result.scalar_one_or_none()

    if not subcontractor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subcontractor not found"
        )

    active_projects = sum(1 for a in subcontractor.project_assignments if a.status == "active")
    compliance_score = await get_subcontractor_compliance_score(db, subcontractor_id)

    if request:
        client_ip = request.client.host if request.client else None
        await log_data_access(
            db=db,
            action="read",
            resource="subcontractor",
            resource_id=str(subcontractor_id),
            user_id=UUID(current_user.user_id),
            ip_address=client_ip,
            details=f"Read subcontractor: {subcontractor.company_name}"
        )

    return SubcontractorWithDetails(
        **{
            "id": str(subcontractor.id),
            "company_name": subcontractor.company_name,
            "contact_first_name": subcontractor.contact_first_name,
            "contact_last_name": subcontractor.contact_last_name,
            "email": subcontractor.email,
            "phone": subcontractor.phone,
            "address_line1": subcontractor.address_line1,
            "address_line2": subcontractor.address_line2,
            "city": subcontractor.city,
            "state": subcontractor.state,
            "zip_code": subcontractor.zip_code,
            "country": subcontractor.country,
            "ein": get_subcontractor_ein(subcontractor),
            "license_number": subcontractor.license_number,
            "license_state": subcontractor.license_state,
            "license_expiration": subcontractor.license_expiration,
            "status": subcontractor.status,
            "created_at": subcontractor.created_at,
            "updated_at": subcontractor.updated_at,
        },
        certifications=[
            CertificationResponse.model_validate(c) for c in subcontractor.certifications
        ],
        violations=[
            ViolationResponse.model_validate(v) for v in subcontractor.violations
        ],
        active_projects_count=active_projects,
        compliance_score=compliance_score
    )


@router.post("/subcontractors", response_model=SubcontractorResponse, status_code=status.HTTP_201_CREATED)
async def create_subcontractor(
    subcontractor: SubcontractorCreate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    team_id = UUID(current_user.team_id) if current_user.team_id else None
    result = await db.execute(
        select(Subcontractor).where(Subcontractor.email == subcontractor.email)
    )
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    db_subcontractor = Subcontractor(**subcontractor.model_dump())
    if team_id:
        db_subcontractor.team_id = team_id
    _encrypt_pii_fields(db_subcontractor, subcontractor.model_dump())
    db.add(db_subcontractor)
    await db.commit()
    await db.refresh(db_subcontractor)
    await _invalidate_compliance_cache(team_id)

    if request:
        client_ip = request.client.host if request.client else None
        await log_data_access(
            db=db,
            action="create",
            resource="subcontractor",
            resource_id=str(db_subcontractor.id),
            user_id=UUID(current_user.user_id),
            ip_address=client_ip,
            details=f"Created subcontractor: {subcontractor.company_name}"
        )

    return _subcontractor_response_data(db_subcontractor)


@router.patch("/subcontractors/{subcontractor_id}", response_model=SubcontractorResponse)
async def update_subcontractor(
    subcontractor_id: UUID,
    subcontractor_update: SubcontractorUpdate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    team_id = UUID(current_user.team_id) if current_user.team_id else None
    conditions = [Subcontractor.id == subcontractor_id]
    if team_id:
        conditions.append(Subcontractor.team_id == team_id)
    result = await db.execute(
        select(Subcontractor).where(and_(*conditions))
    )
    db_subcontractor = result.scalar_one_or_none()

    if not db_subcontractor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subcontractor not found"
        )

    update_data = subcontractor_update.model_dump(exclude_unset=True)
    changed_fields = list(update_data.keys())
    for field, value in update_data.items():
        if field in (PII_FIELDS + ["ein", "email"]) and value:
            encrypted_col = f"encrypted_{field}" if field != "ein" else "encrypted_ein"
            setattr(db_subcontractor, encrypted_col, encrypt_value(value))
            setattr(db_subcontractor, field, None)
        else:
            setattr(db_subcontractor, field, value)

    await db.commit()
    await db.refresh(db_subcontractor)
    await _invalidate_compliance_cache(team_id)

    if request:
        client_ip = request.client.host if request.client else None
        await log_data_access(
            db=db,
            action="update",
            resource="subcontractor",
            resource_id=str(subcontractor_id),
            user_id=UUID(current_user.user_id),
            ip_address=client_ip,
            details=f"Updated subcontractor fields: {changed_fields}"
        )

    return _subcontractor_response_data(db_subcontractor)


@router.delete("/subcontractors/{subcontractor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subcontractor(
    subcontractor_id: UUID,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    team_id = UUID(current_user.team_id) if current_user.team_id else None
    conditions = [Subcontractor.id == subcontractor_id]
    if team_id:
        conditions.append(Subcontractor.team_id == team_id)
    result = await db.execute(
        select(Subcontractor).where(and_(*conditions))
    )
    db_subcontractor = result.scalar_one_or_none()

    if not db_subcontractor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subcontractor not found"
        )

    company_name = db_subcontractor.company_name
    await db.delete(db_subcontractor)
    await db.commit()
    await _invalidate_compliance_cache(team_id)

    if request:
        client_ip = request.client.host if request.client else None
        await log_data_access(
            db=db,
            action="delete",
            resource="subcontractor",
            resource_id=str(subcontractor_id),
            user_id=UUID(current_user.user_id),
            ip_address=client_ip,
            details=f"Deleted subcontractor: {company_name}"
        )


# ---------------------------------------------------------------------------
# Nested certification endpoints under a subcontractor
# ---------------------------------------------------------------------------


async def _get_subcontractor_scoped(
    db: AsyncSession,
    subcontractor_id: UUID,
    team_id: Optional[UUID],
) -> Subcontractor:
    """Fetch a subcontractor scoped to the caller's team, or raise 404."""
    conditions = [Subcontractor.id == subcontractor_id]
    if team_id:
        conditions.append(Subcontractor.team_id == team_id)
    result = await db.execute(
        select(Subcontractor).where(and_(*conditions))
    )
    subcontractor = result.scalar_one_or_none()
    if not subcontractor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subcontractor not found"
        )
    return subcontractor


@router.get(
    "/subcontractors/{subcontractor_id}/certifications",
    response_model=List[CertificationResponse],
)
async def get_subcontractor_certifications(
    subcontractor_id: UUID,
    status_filter: Optional[CertificationStatus] = None,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    """List all certifications held by a subcontractor."""
    team_id = UUID(current_user.team_id) if current_user.team_id else None
    await _get_subcontractor_scoped(db, subcontractor_id, team_id)

    conditions = [Certification.subcontractor_id == subcontractor_id]
    if status_filter:
        conditions.append(Certification.status == status_filter.value)
    result = await db.execute(
        select(Certification)
        .where(and_(*conditions))
        .order_by(Certification.expiration_date.asc())
    )
    certifications = result.scalars().all()

    if request:
        client_ip = request.client.host if request.client else None
        await log_data_access(
            db=db,
            action="list",
            resource="certification",
            resource_id=str(subcontractor_id),
            user_id=UUID(current_user.user_id),
            ip_address=client_ip,
            details=f"Listed {len(certifications)} certifications for subcontractor"
        )

    return certifications


@router.post(
    "/subcontractors/{subcontractor_id}/certifications",
    response_model=CertificationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_subcontractor_certification(
    subcontractor_id: UUID,
    certification: SubcontractorCertificationCreate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    """Add a certification to a subcontractor."""
    team_id = UUID(current_user.team_id) if current_user.team_id else None
    await _get_subcontractor_scoped(db, subcontractor_id, team_id)

    db_certification = Certification(
        subcontractor_id=subcontractor_id,
        **certification.model_dump()
    )
    db.add(db_certification)
    await db.commit()
    await db.refresh(db_certification)
    await _invalidate_compliance_cache(team_id)

    if request:
        client_ip = request.client.host if request.client else None
        await log_data_access(
            db=db,
            action="create",
            resource="certification",
            resource_id=str(db_certification.id),
            user_id=UUID(current_user.user_id),
            ip_address=client_ip,
            details=f"Added certification: {certification.certification_type} to subcontractor {subcontractor_id}"
        )

    return db_certification


@router.delete(
    "/subcontractors/{subcontractor_id}/certifications/{certification_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_subcontractor_certification(
    subcontractor_id: UUID,
    certification_id: UUID,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    """Remove a certification from a subcontractor (scoped to that sub)."""
    team_id = UUID(current_user.team_id) if current_user.team_id else None
    await _get_subcontractor_scoped(db, subcontractor_id, team_id)

    result = await db.execute(
        select(Certification).where(
            and_(
                Certification.id == certification_id,
                Certification.subcontractor_id == subcontractor_id,
            )
        )
    )
    db_certification = result.scalar_one_or_none()
    if not db_certification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certification not found for this subcontractor"
        )

    cert_type = db_certification.certification_type
    await db.delete(db_certification)
    await db.commit()
    await _invalidate_compliance_cache(team_id)

    if request:
        client_ip = request.client.host if request.client else None
        await log_data_access(
            db=db,
            action="delete",
            resource="certification",
            resource_id=str(certification_id),
            user_id=UUID(current_user.user_id),
            ip_address=client_ip,
            details=f"Removed certification: {cert_type} from subcontractor {subcontractor_id}"
        )


@router.get("/certifications", response_model=List[CertificationResponse])
async def get_certifications(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    subcontractor_id: Optional[UUID] = None,
    status_filter: Optional[CertificationStatus] = None,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    team_id = UUID(current_user.team_id) if current_user.team_id else None
    query = select(Certification).join(Subcontractor, Certification.subcontractor_id == Subcontractor.id)

    if team_id:
        query = query.where(Subcontractor.team_id == team_id)

    if subcontractor_id:
        query = query.where(Certification.subcontractor_id == subcontractor_id)

    if status_filter:
        query = query.where(Certification.status == status_filter.value)

    query = query.offset(skip).limit(limit).order_by(Certification.expiration_date.asc())
    result = await db.execute(query)
    certifications = result.scalars().all()

    if request:
        client_ip = request.client.host if request.client else None
        await log_data_access(
            db=db,
            action="list",
            resource="certifications",
            resource_id="all",
            user_id=UUID(current_user.user_id),
            ip_address=client_ip,
            details=f"Listed {len(certifications)} certifications"
        )

    return certifications


@router.get("/certifications/{certification_id}", response_model=CertificationResponse)
async def get_certification(
    certification_id: UUID,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    team_id = UUID(current_user.team_id) if current_user.team_id else None
    query = select(Certification).join(Subcontractor, Certification.subcontractor_id == Subcontractor.id).where(Certification.id == certification_id)
    if team_id:
        query = query.where(Subcontractor.team_id == team_id)
    result = await db.execute(query)
    certification = result.scalar_one_or_none()

    if not certification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certification not found"
        )

    if request:
        client_ip = request.client.host if request.client else None
        await log_data_access(
            db=db,
            action="read",
            resource="certification",
            resource_id=str(certification_id),
            user_id=UUID(current_user.user_id),
            ip_address=client_ip,
            details=f"Read certification: {certification.certification_type}"
        )

    return certification


@router.post("/certifications", response_model=CertificationResponse, status_code=status.HTTP_201_CREATED)
async def create_certification(
    certification: CertificationCreate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    team_id = UUID(current_user.team_id) if current_user.team_id else None
    conditions = [Subcontractor.id == certification.subcontractor_id]
    if team_id:
        conditions.append(Subcontractor.team_id == team_id)
    result = await db.execute(
        select(Subcontractor).where(and_(*conditions))
    )
    subcontractor = result.scalar_one_or_none()

    if not subcontractor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subcontractor not found"
        )

    db_certification = Certification(**certification.model_dump())
    db.add(db_certification)
    await db.commit()
    await db.refresh(db_certification)
    await _invalidate_compliance_cache(team_id)

    if request:
        client_ip = request.client.host if request.client else None
        await log_data_access(
            db=db,
            action="create",
            resource="certification",
            resource_id=str(db_certification.id),
            user_id=UUID(current_user.user_id),
            ip_address=client_ip,
            details=f"Created certification: {certification.certification_type} for subcontractor {certification.subcontractor_id}"
        )

    return db_certification


@router.patch("/certifications/{certification_id}", response_model=CertificationResponse)
async def update_certification(
    certification_id: UUID,
    certification_update: CertificationUpdate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    team_id = UUID(current_user.team_id) if current_user.team_id else None
    query = select(Certification).join(Subcontractor, Certification.subcontractor_id == Subcontractor.id).where(Certification.id == certification_id)
    if team_id:
        query = query.where(Subcontractor.team_id == team_id)
    result = await db.execute(query)
    db_certification = result.scalar_one_or_none()

    if not db_certification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certification not found"
        )

    update_data = certification_update.model_dump(exclude_unset=True)
    changed_fields = list(update_data.keys())
    for field, value in update_data.items():
        setattr(db_certification, field, value)

    await db.commit()
    await db.refresh(db_certification)
    await _invalidate_compliance_cache(team_id)

    if request:
        client_ip = request.client.host if request.client else None
        await log_data_access(
            db=db,
            action="update",
            resource="certification",
            resource_id=str(certification_id),
            user_id=UUID(current_user.user_id),
            ip_address=client_ip,
            details=f"Updated certification fields: {changed_fields}"
        )

    return db_certification


@router.delete("/certifications/{certification_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_certification(
    certification_id: UUID,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    team_id = UUID(current_user.team_id) if current_user.team_id else None
    query = select(Certification).join(Subcontractor, Certification.subcontractor_id == Subcontractor.id).where(Certification.id == certification_id)
    if team_id:
        query = query.where(Subcontractor.team_id == team_id)
    result = await db.execute(query)
    db_certification = result.scalar_one_or_none()

    if not db_certification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certification not found"
        )

    cert_type = db_certification.certification_type
    await db.delete(db_certification)
    await db.commit()
    await _invalidate_compliance_cache(team_id)

    if request:
        client_ip = request.client.host if request.client else None
        await log_data_access(
            db=db,
            action="delete",
            resource="certification",
            resource_id=str(certification_id),
            user_id=UUID(current_user.user_id),
            ip_address=client_ip,
            details=f"Deleted certification: {cert_type}"
        )


@router.get("/contractors/{contractor_id}/certifications", response_model=List[CertificationWithSubcontractor])
async def get_contractor_certifications(
    contractor_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    team_id = UUID(current_user.team_id) if current_user.team_id else None
    query = select(Certification, Subcontractor.company_name)\
        .join(Subcontractor, Certification.subcontractor_id == Subcontractor.id)\
        .where(and_(
            Certification.subcontractor_id == contractor_id,
            Subcontractor.team_id == team_id if team_id else True
        ))\
        .order_by(Certification.expiration_date.asc())
    result = await db.execute(query)
    rows = result.all()
    
    return [
        CertificationWithSubcontractor(
            **CertificationResponse.model_validate(cert).model_dump(),
            subcontractor_company_name=company_name
        )
        for cert, company_name in rows
    ]


@router.get("/violations", response_model=List[ViolationResponse])
async def get_violations(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    subcontractor_id: Optional[UUID] = None,
    status_filter: Optional[ViolationStatus] = None,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    team_id = UUID(current_user.team_id) if current_user.team_id else None
    query = select(Violation).join(Subcontractor, Violation.subcontractor_id == Subcontractor.id)

    if team_id:
        query = query.where(Subcontractor.team_id == team_id)

    if subcontractor_id:
        query = query.where(Violation.subcontractor_id == subcontractor_id)

    if status_filter:
        query = query.where(Violation.status == status_filter.value)

    query = query.offset(skip).limit(limit).order_by(Violation.issued_date.desc())
    result = await db.execute(query)
    violations = result.scalars().all()

    if request:
        client_ip = request.client.host if request.client else None
        await log_data_access(
            db=db,
            action="list",
            resource="violations",
            resource_id="all",
            user_id=UUID(current_user.user_id),
            ip_address=client_ip,
            details=f"Listed {len(violations)} violations"
        )

    return violations


@router.get("/violations/{violation_id}", response_model=ViolationResponse)
async def get_violation(
    violation_id: UUID,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    team_id = UUID(current_user.team_id) if current_user.team_id else None
    query = select(Violation).join(Subcontractor, Violation.subcontractor_id == Subcontractor.id).where(Violation.id == violation_id)
    if team_id:
        query = query.where(Subcontractor.team_id == team_id)
    result = await db.execute(query)
    violation = result.scalar_one_or_none()

    if not violation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Violation not found"
        )

    if request:
        client_ip = request.client.host if request.client else None
        await log_data_access(
            db=db,
            action="read",
            resource="violation",
            resource_id=str(violation_id),
            user_id=UUID(current_user.user_id),
            ip_address=client_ip,
            details=f"Read violation: {violation.violation_type}"
        )

    return violation


@router.post("/violations", response_model=ViolationResponse, status_code=status.HTTP_201_CREATED)
async def create_violation(
    violation: ViolationCreate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    team_id = UUID(current_user.team_id) if current_user.team_id else None
    conditions = [Subcontractor.id == violation.subcontractor_id]
    if team_id:
        conditions.append(Subcontractor.team_id == team_id)
    result = await db.execute(
        select(Subcontractor).where(and_(*conditions))
    )
    subcontractor = result.scalar_one_or_none()

    if not subcontractor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subcontractor not found"
        )

    db_violation = Violation(**violation.model_dump())
    db.add(db_violation)
    await db.commit()
    await db.refresh(db_violation)
    await _invalidate_compliance_cache(team_id)

    if request:
        client_ip = request.client.host if request.client else None
        await log_data_access(
            db=db,
            action="create",
            resource="violation",
            resource_id=str(db_violation.id),
            user_id=UUID(current_user.user_id),
            ip_address=client_ip,
            details=f"Created violation: {violation.violation_type} for subcontractor {violation.subcontractor_id}"
        )

    return db_violation


@router.patch("/violations/{violation_id}", response_model=ViolationResponse)
async def update_violation(
    violation_id: UUID,
    violation_update: ViolationUpdate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    team_id = UUID(current_user.team_id) if current_user.team_id else None
    query = select(Violation).join(Subcontractor, Violation.subcontractor_id == Subcontractor.id).where(Violation.id == violation_id)
    if team_id:
        query = query.where(Subcontractor.team_id == team_id)
    result = await db.execute(query)
    db_violation = result.scalar_one_or_none()

    if not db_violation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Violation not found"
        )

    update_data = violation_update.model_dump(exclude_unset=True)
    changed_fields = list(update_data.keys())
    for field, value in update_data.items():
        setattr(db_violation, field, value)

    await db.commit()
    await db.refresh(db_violation)
    await _invalidate_compliance_cache(team_id)

    if request:
        client_ip = request.client.host if request.client else None
        await log_data_access(
            db=db,
            action="update",
            resource="violation",
            resource_id=str(violation_id),
            user_id=UUID(current_user.user_id),
            ip_address=client_ip,
            details=f"Updated violation fields: {changed_fields}"
        )

    return db_violation


@router.delete("/violations/{violation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_violation(
    violation_id: UUID,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    team_id = UUID(current_user.team_id) if current_user.team_id else None
    query = select(Violation).join(Subcontractor, Violation.subcontractor_id == Subcontractor.id).where(Violation.id == violation_id)
    if team_id:
        query = query.where(Subcontractor.team_id == team_id)
    result = await db.execute(query)
    db_violation = result.scalar_one_or_none()

    if not db_violation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Violation not found"
        )

    violation_type = db_violation.violation_type
    await db.delete(db_violation)
    await db.commit()
    await _invalidate_compliance_cache(team_id)

    if request:
        client_ip = request.client.host if request.client else None
        await log_data_access(
            db=db,
            action="delete",
            resource="violation",
            resource_id=str(violation_id),
            user_id=UUID(current_user.user_id),
            ip_address=client_ip,
            details=f"Deleted violation: {violation_type}"
        )


@router.get("/contractors/{contractor_id}/violations", response_model=List[ViolationWithSubcontractor])
async def get_contractor_violations(
    contractor_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    team_id = UUID(current_user.team_id) if current_user.team_id else None
    query = select(Violation, Subcontractor.company_name)\
        .join(Subcontractor, Violation.subcontractor_id == Subcontractor.id)\
        .where(and_(
            Violation.subcontractor_id == contractor_id,
            Subcontractor.team_id == team_id if team_id else True
        ))\
        .order_by(Violation.issued_date.desc())
    result = await db.execute(query)
    rows = result.all()
    
    return [
        ViolationWithSubcontractor(
            **ViolationResponse.model_validate(v).model_dump(),
            subcontractor_company_name=company_name
        )
        for v, company_name in rows
    ]


@router.get("/projects", response_model=List[ProjectResponse])
async def get_projects(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status_filter: Optional[str] = None,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    team_id = UUID(current_user.team_id) if current_user.team_id else None
    query = select(Project)

    if team_id:
        query = query.where(Project.team_id == team_id)

    if status_filter:
        query = query.where(Project.status == status_filter)

    query = query.offset(skip).limit(limit).order_by(Project.created_at.desc())
    result = await db.execute(query)
    projects = result.scalars().all()
    for proj in projects:
        for field in CLIENT_FIELDS:
            val = decrypt_client(proj, field)
            if val:
                setattr(proj, field, val)

    if request:
        client_ip = request.client.host if request.client else None
        await log_data_access(
            db=db,
            action="list",
            resource="projects",
            resource_id="all",
            user_id=UUID(current_user.user_id),
            ip_address=client_ip,
            details=f"Listed {len(projects)} projects"
        )

    return projects


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: UUID,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    team_id = UUID(current_user.team_id) if current_user.team_id else None
    conditions = [Project.id == project_id]
    if team_id:
        conditions.append(Project.team_id == team_id)
    result = await db.execute(
        select(Project).where(and_(*conditions))
    )
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    if request:
        client_ip = request.client.host if request.client else None
        await log_data_access(
            db=db,
            action="read",
            resource="project",
            resource_id=str(project_id),
            user_id=UUID(current_user.user_id),
            ip_address=client_ip,
            details=f"Read project: {project.project_name}"
        )

    for field in CLIENT_FIELDS:
        val = decrypt_client(project, field)
        if val:
            setattr(project, field, val)

    return project


@router.post("/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project: ProjectCreate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    team_id = UUID(current_user.team_id) if current_user.team_id else None
    db_project = Project(**project.model_dump())
    if team_id:
        db_project.team_id = team_id
    _encrypt_client_fields(db_project, project.model_dump())
    db.add(db_project)
    await db.commit()
    await db.refresh(db_project)
    for field in CLIENT_FIELDS:
        val = decrypt_client(db_project, field)
        if val:
            setattr(db_project, field, val)

    if request:
        client_ip = request.client.host if request.client else None
        await log_data_access(
            db=db,
            action="create",
            resource="project",
            resource_id=str(db_project.id),
            user_id=UUID(current_user.user_id),
            ip_address=client_ip,
            details=f"Created project: {project.project_name}"
        )

    return db_project


@router.patch("/projects/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: UUID,
    project_update: ProjectUpdate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    team_id = UUID(current_user.team_id) if current_user.team_id else None
    conditions = [Project.id == project_id]
    if team_id:
        conditions.append(Project.team_id == team_id)
    result = await db.execute(
        select(Project).where(and_(*conditions))
    )
    db_project = result.scalar_one_or_none()

    if not db_project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    update_data = project_update.model_dump(exclude_unset=True)
    changed_fields = list(update_data.keys())
    for field, value in update_data.items():
        if field in CLIENT_FIELDS and value:
            encrypted_col = f"encrypted_{field}"
            setattr(db_project, encrypted_col, encrypt_value(value))
            setattr(db_project, field, None)
        else:
            setattr(db_project, field, value)

    await db.commit()
    await db.refresh(db_project)
    for field in CLIENT_FIELDS:
        val = decrypt_client(db_project, field)
        if val:
            setattr(db_project, field, val)

    if request:
        client_ip = request.client.host if request.client else None
        await log_data_access(
            db=db,
            action="update",
            resource="project",
            resource_id=str(project_id),
            user_id=UUID(current_user.user_id),
            ip_address=client_ip,
            details=f"Updated project fields: {changed_fields}"
        )

    return db_project


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: UUID,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    team_id = UUID(current_user.team_id) if current_user.team_id else None
    conditions = [Project.id == project_id]
    if team_id:
        conditions.append(Project.team_id == team_id)
    result = await db.execute(
        select(Project).where(and_(*conditions))
    )
    db_project = result.scalar_one_or_none()

    if not db_project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    project_name = db_project.project_name
    await db.delete(db_project)
    await db.commit()

    if request:
        client_ip = request.client.host if request.client else None
        await log_data_access(
            db=db,
            action="delete",
            resource="project",
            resource_id=str(project_id),
            user_id=UUID(current_user.user_id),
            ip_address=client_ip,
            details=f"Deleted project: {project_name}"
        )


@router.get("/projects/{project_id}/subcontractors", response_model=List[SubcontractorWithDetails])
async def get_project_subcontractors(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    team_id = UUID(current_user.team_id) if current_user.team_id else None
    conditions = [Project.id == project_id]
    if team_id:
        conditions.append(Project.team_id == team_id)
    result = await db.execute(
        select(Project).where(and_(*conditions))
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    result = await db.execute(
        select(Subcontractor)
        .join(ProjectSubcontractor, Subcontractor.id == ProjectSubcontractor.subcontractor_id)
        .options(
            selectinload(Subcontractor.certifications),
            selectinload(Subcontractor.violations),
            selectinload(Subcontractor.project_assignments)
        )
        .where(and_(
            ProjectSubcontractor.project_id == project_id,
            Subcontractor.team_id == team_id if team_id else True
        ))
        .order_by(Subcontractor.company_name)
    )
    subcontractors = result.scalars().all()

    return [
        SubcontractorWithDetails(
            **{
                "id": str(sub.id),
                "company_name": sub.company_name,
                "contact_first_name": decrypt_pii(sub, "contact_first_name") or sub.contact_first_name,
                "contact_last_name": decrypt_pii(sub, "contact_last_name") or sub.contact_last_name,
                "email": decrypt_pii(sub, "email") or sub.email,
                "phone": decrypt_pii(sub, "phone") or sub.phone,
                "address_line1": decrypt_pii(sub, "address_line1") or sub.address_line1,
                "address_line2": decrypt_pii(sub, "address_line2") or sub.address_line2,
                "city": decrypt_pii(sub, "city") or sub.city,
                "state": decrypt_pii(sub, "state") or sub.state,
                "zip_code": decrypt_pii(sub, "zip_code") or sub.zip_code,
                "country": sub.country,
                "ein": get_subcontractor_ein(sub),
                "license_number": sub.license_number,
                "license_state": sub.license_state,
                "license_expiration": sub.license_expiration,
                "status": sub.status,
                "created_at": sub.created_at,
                "updated_at": sub.updated_at,
            },
            certifications=[CertificationResponse.model_validate(c) for c in sub.certifications],
            violations=[ViolationResponse.model_validate(v) for v in sub.violations],
            active_projects_count=sum(1 for a in sub.project_assignments if a.status == "active"),
            compliance_score=await get_subcontractor_compliance_score(db, sub.id)
        )
        for sub in subcontractors
    ]


@router.post("/projects/{project_id}/subcontractors/quick-add", response_model=SubcontractorWithDetails, status_code=status.HTTP_201_CREATED)
async def quick_add_subcontractor_to_project(
    project_id: UUID,
    subcontractor_data: SubcontractorCreate,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    """Quick-add a new subcontractor to a project with auto-compliance check.
    
    Creates the subcontractor, assigns them to the project, and returns
    compliance status including any auto-detected issues.
    """
    team_id = UUID(current_user.team_id) if current_user.team_id else None
    conditions = [Project.id == project_id]
    if team_id:
        conditions.append(Project.team_id == team_id)
    result = await db.execute(
        select(Project).where(and_(*conditions))
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    result = await db.execute(
        select(Subcontractor).where(Subcontractor.email == subcontractor_data.email)
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    db_subcontractor = Subcontractor(**subcontractor_data.model_dump())
    if team_id:
        db_subcontractor.team_id = team_id
    _encrypt_pii_fields(db_subcontractor, subcontractor_data.model_dump())
    db.add(db_subcontractor)
    await db.flush()
    
    project_assignment = ProjectSubcontractor(
        project_id=project_id,
        subcontractor_id=db_subcontractor.id,
        status="active"
    )
    db.add(project_assignment)
    await db.commit()
    await db.refresh(db_subcontractor)
    await _invalidate_compliance_cache(team_id)
    
    result = await db.execute(
        select(Subcontractor)
        .options(
            selectinload(Subcontractor.certifications),
            selectinload(Subcontractor.violations),
            selectinload(Subcontractor.project_assignments)
        )
        .where(Subcontractor.id == db_subcontractor.id)
    )
    sub = result.scalar_one()
    
    return SubcontractorWithDetails(
        **{
            "id": str(sub.id),
            "company_name": sub.company_name,
            "contact_first_name": decrypt_pii(sub, "contact_first_name") or sub.contact_first_name,
            "contact_last_name": decrypt_pii(sub, "contact_last_name") or sub.contact_last_name,
            "email": decrypt_pii(sub, "email") or sub.email,
            "phone": decrypt_pii(sub, "phone") or sub.phone,
            "address_line1": decrypt_pii(sub, "address_line1") or sub.address_line1,
            "address_line2": decrypt_pii(sub, "address_line2") or sub.address_line2,
            "city": decrypt_pii(sub, "city") or sub.city,
            "state": decrypt_pii(sub, "state") or sub.state,
            "zip_code": decrypt_pii(sub, "zip_code") or sub.zip_code,
            "country": sub.country,
            "ein": get_subcontractor_ein(sub),
            "license_number": sub.license_number,
            "license_state": sub.license_state,
            "license_expiration": sub.license_expiration,
            "status": sub.status,
            "created_at": sub.created_at,
            "updated_at": sub.updated_at,
        },
        certifications=[CertificationResponse.model_validate(c) for c in sub.certifications],
        violations=[ViolationResponse.model_validate(v) for v in sub.violations],
        active_projects_count=sum(1 for a in sub.project_assignments if a.status == "active"),
        compliance_score=await get_subcontractor_compliance_score(db, sub.id)
    )


@router.get("/compliance/status", response_model=List[ComplianceStatusResponse])
async def get_compliance_status(
    project_id: Optional[UUID] = Query(None, description="Filter by project ID"),
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    team_id = UUID(current_user.team_id) if current_user.team_id else None
    if project_id:
        project_conditions = [Project.id == project_id]
        if team_id:
            project_conditions.append(Project.team_id == team_id)
        project_result = await db.execute(
            select(Project).where(and_(*project_conditions))
        )
        if not project_result.scalar_one_or_none():
            return []
        result = await db.execute(
            select(Subcontractor)
            .join(ProjectSubcontractor, Subcontractor.id == ProjectSubcontractor.subcontractor_id)
            .where(and_(
                ProjectSubcontractor.project_id == project_id,
                Subcontractor.team_id == team_id if team_id else True
            ))
            .order_by(Subcontractor.company_name)
        )
    else:
        query = select(Subcontractor)
        if team_id:
            query = query.where(Subcontractor.team_id == team_id)
        result = await db.execute(query.order_by(Subcontractor.company_name))
    subcontractors = result.scalars().all()
    
    compliance_list = []
    for sub in subcontractors:
        score = await get_subcontractor_compliance_score(db, sub.id)
        
        active_certs_result = await db.execute(
            select(func.count(Certification.id)).where(
                and_(
                    Certification.subcontractor_id == sub.id,
                    Certification.status == CertificationStatus.VALID.value
                )
            )
        )
        active_certs = active_certs_result.scalar() or 0
        
        expiring_soon_date = date.today() + timedelta(days=30)
        expiring_certs_result = await db.execute(
            select(func.count(Certification.id)).where(
                and_(
                    Certification.subcontractor_id == sub.id,
                    Certification.expiration_date <= expiring_soon_date,
                    Certification.expiration_date >= date.today()
                )
            )
        )
        expiring_certs = expiring_certs_result.scalar() or 0
        
        expired_certs_result = await db.execute(
            select(func.count(Certification.id)).where(
                and_(
                    Certification.subcontractor_id == sub.id,
                    Certification.expiration_date < date.today()
                )
            )
        )
        expired_certs = expired_certs_result.scalar() or 0
        
        open_violations_result = await db.execute(
            select(func.count(Violation.id)).where(
                and_(
                    Violation.subcontractor_id == sub.id,
                    Violation.status.in_([ViolationStatus.OPEN.value, ViolationStatus.UNDER_REVIEW.value])
                )
            )
        )
        open_violations = open_violations_result.scalar() or 0
        
        resolved_violations_result = await db.execute(
            select(func.count(Violation.id)).where(
                and_(
                    Violation.subcontractor_id == sub.id,
                    Violation.status == ViolationStatus.RESOLVED.value
                )
            )
        )
        resolved_violations = resolved_violations_result.scalar() or 0
        
        compliance_list.append(ComplianceStatusResponse(
            subcontractor_id=sub.id,
            company_name=sub.company_name,
            state=decrypt_pii(sub, "state") or sub.state,
            compliance_score=score,
            status="COMPLIANT" if score >= 70 else "NON_COMPLIANT",
            active_certifications=active_certs,
            expiring_certifications=expiring_certs,
            expired_certifications=expired_certs,
            open_violations=open_violations,
            resolved_violations=resolved_violations
        ))
    
    return compliance_list


@router.get("/compliance/alerts")
async def get_compliance_alerts(
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    team_id = UUID(current_user.team_id) if current_user.team_id else None
    thirty_days_from_now = date.today() + timedelta(days=30)
    
    query = select(Certification, Subcontractor.company_name)\
        .join(Subcontractor, Certification.subcontractor_id == Subcontractor.id)\
        .where(
            and_(
                Certification.expiration_date <= thirty_days_from_now,
                Certification.expiration_date >= date.today(),
                Certification.status == CertificationStatus.VALID.value,
                Subcontractor.team_id == team_id if team_id else True
            )
        )\
        .order_by(Certification.expiration_date.asc())
    result = await db.execute(query)
    rows = result.all()
    
    alerts = []
    for cert, company_name in rows:
        days_until = (cert.expiration_date - date.today()).days
        alerts.append({
            "id": str(cert.id),
            "type": "warning" if days_until > 7 else "critical",
            "message": f"Certification {cert.certification_type} for {company_name} expires in {days_until} days",
            "certification_id": str(cert.id),
            "subcontractor_id": str(cert.subcontractor_id),
            "expiration_date": cert.expiration_date.isoformat(),
            "days_until_expiration": days_until
        })
    
    return alerts


@router.get("/dashboard/summary", response_model=DashboardSummary)
async def get_dashboard_summary(
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    team_id = UUID(current_user.team_id) if current_user.team_id else None

    cache_key = build_cache_key("compliance:dashboard:summary", team_id)
    cached = await cache_service.get(cache_key)
    if cached is not None:
        return cached

    subs_filter = [Subcontractor.team_id == team_id] if team_id else []
    total_subs_result = await db.execute(select(func.count(Subcontractor.id)).where(and_(*subs_filter)) if subs_filter else select(func.count(Subcontractor.id)))
    total_subcontractors = total_subs_result.scalar() or 0
    
    active_subs_filter = [Subcontractor.status == SubcontractorStatus.ACTIVE.value] + (subs_filter if team_id else [])
    active_subs_result = await db.execute(
        select(func.count(Subcontractor.id)).where(and_(*active_subs_filter))
    )
    active_subcontractors = active_subs_result.scalar() or 0
    
    projects_filter = [Project.team_id == team_id] if team_id else []
    total_projects_result = await db.execute(select(func.count(Project.id)).where(and_(*projects_filter)) if projects_filter else select(func.count(Project.id)))
    total_projects = total_projects_result.scalar() or 0
    
    active_projects_filter = [Project.status == (Project.Status.ACTIVE.value if hasattr(Project.Status, 'ACTIVE') else "active")] + (projects_filter if team_id else [])
    active_projects_result = await db.execute(
        select(func.count(Project.id)).where(and_(*active_projects_filter))
    )
    active_projects = active_projects_result.scalar() or 0
    
    thirty_days_from_now = date.today() + timedelta(days=30)
    cert_filter = [Certification.expiration_date <= thirty_days_from_now, Certification.expiration_date >= date.today()]
    if team_id:
        cert_filter.append(Certification.subcontractor_id.in_(
            select(Subcontractor.id).where(Subcontractor.team_id == team_id)
        ))
    expiring_certs_result = await db.execute(
        select(func.count(Certification.id)).where(and_(*cert_filter))
    )
    expiring_this_month = expiring_certs_result.scalar() or 0
    
    viol_filter = [Violation.status.in_([ViolationStatus.OPEN.value, ViolationStatus.UNDER_REVIEW.value])]
    if team_id:
        viol_filter.append(Violation.subcontractor_id.in_(
            select(Subcontractor.id).where(Subcontractor.team_id == team_id)
        ))
    open_violations_result = await db.execute(
        select(func.count(Violation.id)).where(and_(*viol_filter))
    )
    open_violations = open_violations_result.scalar() or 0
    
    alert_filter = []
    if team_id:
        alert_filter.append(AlertNotification.certification_id.in_(
            select(Certification.id).join(Subcontractor, Certification.subcontractor_id == Subcontractor.id).where(Subcontractor.team_id == team_id)
        ))
    
    alert_query = select(AlertNotification)
    if alert_filter:
        alert_query = alert_query.where(and_(*alert_filter))
    recent_alerts_result = await db.execute(
        alert_query.order_by(AlertNotification.created_at.desc()).limit(5)
    )
    recent_alerts = recent_alerts_result.scalars().all()
    
    compliance_rate = (active_subcontractors / total_subcontractors * 100) if total_subcontractors > 0 else 100.0

    result = DashboardSummary(
        total_subcontractors=total_subcontractors,
        active_subcontractors=active_subcontractors,
        compliance_rate=round(compliance_rate, 2),
        total_projects=total_projects,
        active_projects=active_projects,
        expiring_this_month=expiring_this_month,
        open_violations=open_violations,
        recent_alerts=[AlertNotificationResponse.model_validate(a) for a in recent_alerts]
    )
    await cache_service.set(cache_key, result.model_dump())
    return result


@router.get("/subcontractors/{subcontractor_id}/report")
async def get_subcontractor_pdf_report(
    subcontractor_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    """Generate and download a PDF compliance report for a subcontractor."""
    from fastapi.responses import StreamingResponse
    from app.services.pdf_service import generate_subcontractor_pdf

    try:
        pdf_bytes = await generate_subcontractor_pdf(db, subcontractor_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.error(f"PDF generation failed: {e}")
        raise HTTPException(status_code=500, detail="PDF generation failed") from e

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=compliance-report-{subcontractor_id}.pdf"
        }
    )


@router.get("/compliance/summary", response_model=ComplianceSummaryResponse)
async def compliance_summary(
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    """Return a single-row compliance summary for the dashboard card view."""
    team_id = UUID(current_user.team_id) if current_user.team_id else None
    cache_key = build_cache_key("compliance:summary", team_id)
    cached = await cache_service.get(cache_key)
    if cached is not None:
        return ComplianceSummaryResponse(**cached)

    data = await get_compliance_summary(db)
    await cache_service.set(cache_key, data)
    return ComplianceSummaryResponse(**data)


@router.get("/compliance/trends", response_model=list[ComplianceTrendPoint])
async def compliance_trends(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    """Return daily compliance trend points for the last ``days`` days."""
    team_id = UUID(current_user.team_id) if current_user.team_id else None
    cache_key = build_cache_key("compliance:trends", team_id, days=days)
    cached = await cache_service.get(cache_key)
    if cached is not None:
        return cached

    data = await get_compliance_trends(db, days=days)
    result = [ComplianceTrendPoint(**row).model_dump() for row in data]
    await cache_service.set(cache_key, result)
    return result


@router.get("/compliance/export")
async def compliance_export(
    format: str = Query("csv", pattern="^(csv|json)$"),
    expiration_bucket: Optional[str] = None,
    limit: int = Query(5000, ge=1, le=10000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    """Export certification status rows (CSV or JSON)."""
    try:
        rows = await get_certification_export_rows(
            db,
            expiration_bucket=expiration_bucket,
            limit=limit,
            offset=offset,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Database query failed: {exc}") from exc

    if format == "json":
        return rows

    if not rows:
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=CertificationExportRow.model_fields.keys())
        writer.writeheader()
        return StreamingResponse(
            io.BytesIO(buffer.getvalue().encode("utf-8")),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=compliance_export.csv"},
        )

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=rows[0].keys())
    writer.writeheader()
    for row in rows:
        writer.writerow(row)

    return StreamingResponse(
        io.BytesIO(buffer.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=compliance_export.csv"},
    )


@router.get("/compliance/dashboard/pdf")
async def get_compliance_dashboard_pdf(
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    """Generate and download a PDF compliance dashboard report."""
    try:
        pdf_bytes = await generate_compliance_dashboard_pdf(db)
    except Exception as e:
        logger.error(f"Dashboard PDF generation failed: {e}")
        raise HTTPException(status_code=500, detail="PDF generation failed") from e

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=compliance-dashboard-{date.today().isoformat()}.pdf"
        }
    )