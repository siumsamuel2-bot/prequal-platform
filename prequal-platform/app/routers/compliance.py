import io
import logging
from datetime import date, timedelta

logger = logging.getLogger(__name__)
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
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
    ViolationCreate, ViolationUpdate, ViolationResponse, ViolationWithSubcontractor,
    ProjectCreate, ProjectUpdate, ProjectResponse, ProjectWithSubcontractors,
    ProjectSubcontractorCreate, ProjectSubcontractorUpdate, ProjectSubcontractorResponse,
    ComplianceStatusResponse, DashboardSummary,
    AlertPreferenceCreate, AlertPreferenceUpdate, AlertPreferenceResponse,
    AlertNotificationUpdate, AlertNotificationResponse,
    CertificationRenewalCreate, CertificationRenewalUpdate, CertificationRenewalResponse,
    SubcontractorStatus, CertificationStatus, ViolationStatus
)
from app.routers.auth import get_current_user, TokenData

router = APIRouter(prefix="/api", tags=["compliance"])


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
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    query = select(Subcontractor)
    
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
    
    query = query.offset(skip).limit(limit).order_by(Subcontractor.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/subcontractors/{subcontractor_id}", response_model=SubcontractorWithDetails)
async def get_subcontractor(
    subcontractor_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    result = await db.execute(
        select(Subcontractor)
        .options(
            selectinload(Subcontractor.certifications),
            selectinload(Subcontractor.violations),
            selectinload(Subcontractor.project_assignments)
        )
        .where(Subcontractor.id == subcontractor_id)
    )
    subcontractor = result.scalar_one_or_none()
    
    if not subcontractor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subcontractor not found"
        )
    
    active_projects = sum(1 for a in subcontractor.project_assignments if a.status == "active")
    compliance_score = await get_subcontractor_compliance_score(db, subcontractor_id)
    
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
            "ein": subcontractor.ein,
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
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
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
    db.add(db_subcontractor)
    await db.commit()
    await db.refresh(db_subcontractor)
    return db_subcontractor


@router.patch("/subcontractors/{subcontractor_id}", response_model=SubcontractorResponse)
async def update_subcontractor(
    subcontractor_id: UUID,
    subcontractor_update: SubcontractorUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    result = await db.execute(
        select(Subcontractor).where(Subcontractor.id == subcontractor_id)
    )
    db_subcontractor = result.scalar_one_or_none()
    
    if not db_subcontractor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subcontractor not found"
        )
    
    update_data = subcontractor_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_subcontractor, field, value)
    
    await db.commit()
    await db.refresh(db_subcontractor)
    return db_subcontractor


@router.delete("/subcontractors/{subcontractor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subcontractor(
    subcontractor_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    result = await db.execute(
        select(Subcontractor).where(Subcontractor.id == subcontractor_id)
    )
    db_subcontractor = result.scalar_one_or_none()
    
    if not db_subcontractor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subcontractor not found"
        )
    
    await db.delete(db_subcontractor)
    await db.commit()


@router.get("/certifications", response_model=List[CertificationResponse])
async def get_certifications(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    subcontractor_id: Optional[UUID] = None,
    status_filter: Optional[CertificationStatus] = None,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    query = select(Certification)
    
    if subcontractor_id:
        query = query.where(Certification.subcontractor_id == subcontractor_id)
    
    if status_filter:
        query = query.where(Certification.status == status_filter.value)
    
    query = query.offset(skip).limit(limit).order_by(Certification.expiration_date.asc())
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/certifications/{certification_id}", response_model=CertificationResponse)
async def get_certification(
    certification_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    result = await db.execute(
        select(Certification).where(Certification.id == certification_id)
    )
    certification = result.scalar_one_or_none()
    
    if not certification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certification not found"
        )
    
    return certification


@router.post("/certifications", response_model=CertificationResponse, status_code=status.HTTP_201_CREATED)
async def create_certification(
    certification: CertificationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    result = await db.execute(
        select(Subcontractor).where(Subcontractor.id == certification.subcontractor_id)
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
    return db_certification


@router.patch("/certifications/{certification_id}", response_model=CertificationResponse)
async def update_certification(
    certification_id: UUID,
    certification_update: CertificationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    result = await db.execute(
        select(Certification).where(Certification.id == certification_id)
    )
    db_certification = result.scalar_one_or_none()
    
    if not db_certification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certification not found"
        )
    
    update_data = certification_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_certification, field, value)
    
    await db.commit()
    await db.refresh(db_certification)
    return db_certification


@router.delete("/certifications/{certification_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_certification(
    certification_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    result = await db.execute(
        select(Certification).where(Certification.id == certification_id)
    )
    db_certification = result.scalar_one_or_none()
    
    if not db_certification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certification not found"
        )
    
    await db.delete(db_certification)
    await db.commit()


@router.get("/contractors/{contractor_id}/certifications", response_model=List[CertificationWithSubcontractor])
async def get_contractor_certifications(
    contractor_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    result = await db.execute(
        select(Certification, Subcontractor.company_name)
        .join(Subcontractor, Certification.subcontractor_id == Subcontractor.id)
        .where(Certification.subcontractor_id == contractor_id)
        .order_by(Certification.expiration_date.asc())
    )
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
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    query = select(Violation)
    
    if subcontractor_id:
        query = query.where(Violation.subcontractor_id == subcontractor_id)
    
    if status_filter:
        query = query.where(Violation.status == status_filter.value)
    
    query = query.offset(skip).limit(limit).order_by(Violation.issued_date.desc())
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/violations/{violation_id}", response_model=ViolationResponse)
async def get_violation(
    violation_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    result = await db.execute(
        select(Violation).where(Violation.id == violation_id)
    )
    violation = result.scalar_one_or_none()
    
    if not violation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Violation not found"
        )
    
    return violation


@router.post("/violations", response_model=ViolationResponse, status_code=status.HTTP_201_CREATED)
async def create_violation(
    violation: ViolationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    result = await db.execute(
        select(Subcontractor).where(Subcontractor.id == violation.subcontractor_id)
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
    return db_violation


@router.patch("/violations/{violation_id}", response_model=ViolationResponse)
async def update_violation(
    violation_id: UUID,
    violation_update: ViolationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    result = await db.execute(
        select(Violation).where(Violation.id == violation_id)
    )
    db_violation = result.scalar_one_or_none()
    
    if not db_violation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Violation not found"
        )
    
    update_data = violation_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_violation, field, value)
    
    await db.commit()
    await db.refresh(db_violation)
    return db_violation


@router.delete("/violations/{violation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_violation(
    violation_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    result = await db.execute(
        select(Violation).where(Violation.id == violation_id)
    )
    db_violation = result.scalar_one_or_none()
    
    if not db_violation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Violation not found"
        )
    
    await db.delete(db_violation)
    await db.commit()


@router.get("/contractors/{contractor_id}/violations", response_model=List[ViolationWithSubcontractor])
async def get_contractor_violations(
    contractor_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    result = await db.execute(
        select(Violation, Subcontractor.company_name)
        .join(Subcontractor, Violation.subcontractor_id == Subcontractor.id)
        .where(Violation.subcontractor_id == contractor_id)
        .order_by(Violation.issued_date.desc())
    )
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
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    query = select(Project)
    
    if status_filter:
        query = query.where(Project.status == status_filter)
    
    query = query.offset(skip).limit(limit).order_by(Project.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    return project


@router.post("/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    db_project = Project(**project.model_dump())
    db.add(db_project)
    await db.commit()
    await db.refresh(db_project)
    return db_project


@router.patch("/projects/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: UUID,
    project_update: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    db_project = result.scalar_one_or_none()
    
    if not db_project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    update_data = project_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_project, field, value)
    
    await db.commit()
    await db.refresh(db_project)
    return db_project


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    db_project = result.scalar_one_or_none()
    
    if not db_project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    await db.delete(db_project)
    await db.commit()


@router.get("/compliance/status", response_model=List[ComplianceStatusResponse])
async def get_compliance_status(
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    result = await db.execute(
        select(Subcontractor).order_by(Subcontractor.company_name)
    )
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
    thirty_days_from_now = date.today() + timedelta(days=30)
    
    result = await db.execute(
        select(Certification, Subcontractor.company_name)
        .join(Subcontractor, Certification.subcontractor_id == Subcontractor.id)
        .where(
            and_(
                Certification.expiration_date <= thirty_days_from_now,
                Certification.expiration_date >= date.today(),
                Certification.status == CertificationStatus.VALID.value
            )
        )
        .order_by(Certification.expiration_date.asc())
    )
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
    total_subs_result = await db.execute(select(func.count(Subcontractor.id)))
    total_subcontractors = total_subs_result.scalar() or 0
    
    active_subs_result = await db.execute(
        select(func.count(Subcontractor.id)).where(Subcontractor.status == SubcontractorStatus.ACTIVE.value)
    )
    active_subcontractors = active_subs_result.scalar() or 0
    
    total_projects_result = await db.execute(select(func.count(Project.id)))
    total_projects = total_projects_result.scalar() or 0
    
    active_projects_result = await db.execute(
        select(func.count(Project.id)).where(Project.status == Project.Status.ACTIVE.value if hasattr(Project.Status, 'ACTIVE') else "active")
    )
    active_projects = active_projects_result.scalar() or 0
    
    thirty_days_from_now = date.today() + timedelta(days=30)
    expiring_certs_result = await db.execute(
        select(func.count(Certification.id)).where(
            and_(
                Certification.expiration_date <= thirty_days_from_now,
                Certification.expiration_date >= date.today()
            )
        )
    )
    expiring_this_month = expiring_certs_result.scalar() or 0
    
    open_violations_result = await db.execute(
        select(func.count(Violation.id)).where(
            Violation.status.in_([ViolationStatus.OPEN.value, ViolationStatus.UNDER_REVIEW.value])
        )
    )
    open_violations = open_violations_result.scalar() or 0
    
    recent_alerts_result = await db.execute(
        select(AlertNotification)
        .order_by(AlertNotification.created_at.desc())
        .limit(5)
    )
    recent_alerts = recent_alerts_result.scalars().all()
    
    compliance_rate = (active_subcontractors / total_subcontractors * 100) if total_subcontractors > 0 else 100.0
    
    return DashboardSummary(
        total_subcontractors=total_subcontractors,
        active_subcontractors=active_subcontractors,
        compliance_rate=round(compliance_rate, 2),
        total_projects=total_projects,
        active_projects=active_projects,
        expiring_this_month=expiring_this_month,
        open_violations=open_violations,
        recent_alerts=[AlertNotificationResponse.model_validate(a) for a in recent_alerts]
    )


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