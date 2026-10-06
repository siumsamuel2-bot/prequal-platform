import uuid
from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, status
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.compliance import Subcontractor, Certification
from app.models.credential_upload import UploadedCredential
from app.schemas.compliance import CertificationCreate, CertificationResponse
from app.schemas.credential_upload import (
    CredentialUploadResponse,
    CredentialUploadWithExtraction,
    CredentialUploadStatusResponse,
    UploadStatus,
    ExtractionStatus,
    VirusScanStatus,
)
from app.services.credential_service import CredentialUploadService
from app.routers.auth import get_current_user, TokenData

router = APIRouter(prefix="/api", tags=["credentials"])

upload_service = CredentialUploadService()


def convert_mime_type(mime_type: str) -> str:
    return mime_type.lower().strip()


def _team_id_from_user(current_user: TokenData) -> Optional[uuid.UUID]:
    return uuid.UUID(current_user.team_id) if current_user.team_id else None


async def _get_subcontractor_scoped(
    db: AsyncSession,
    subcontractor_id: uuid.UUID,
    team_id: Optional[uuid.UUID],
) -> Subcontractor:
    """Fetch a subcontractor scoped to the caller's team, or raise 404."""
    conditions = [Subcontractor.id == subcontractor_id]
    if team_id:
        conditions.append(Subcontractor.team_id == team_id)
    result = await db.execute(select(Subcontractor).where(and_(*conditions)))
    subcontractor = result.scalar_one_or_none()
    if not subcontractor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subcontractor not found"
        )
    return subcontractor


async def _get_upload_scoped(
    db: AsyncSession,
    upload_id: uuid.UUID,
    team_id: Optional[uuid.UUID],
) -> UploadedCredential:
    """Fetch an upload whose subcontractor belongs to the caller's team, or 404."""
    query = (
        select(UploadedCredential)
        .join(Subcontractor, UploadedCredential.subcontractor_id == Subcontractor.id)
        .where(UploadedCredential.id == upload_id)
    )
    if team_id:
        query = query.where(Subcontractor.team_id == team_id)
    result = await db.execute(query)
    upload = result.scalar_one_or_none()
    if not upload:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Upload not found"
        )
    return upload


@router.post("/subcontractors/{subcontractor_id}/credentials/upload", response_model=CredentialUploadStatusResponse, status_code=status.HTTP_201_CREATED)
async def upload_credential(
    subcontractor_id: uuid.UUID,
    file: UploadFile = File(...),
    certification_type: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    team_id = _team_id_from_user(current_user)
    await _get_subcontractor_scoped(db, subcontractor_id, team_id)
    
    content = await file.read()
    content_type = convert_mime_type(file.content_type or "application/octet-stream")
    
    stored_filename, file_path, error = await upload_service.process_upload(
        content=content,
        original_filename=file.filename or "unknown",
        content_type=content_type,
        subcontractor_id=subcontractor_id,
    )
    
    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Upload failed: {error}"
        )
    
    uploaded_credential = UploadedCredential(
        subcontractor_id=subcontractor_id,
        original_filename=file.filename or "unknown",
        stored_filename=stored_filename,
        file_path=file_path,
        file_size=len(content),
        mime_type=content_type,
        status=UploadStatus.PENDING.value,
        extraction_status=ExtractionStatus.PENDING.value,
    )
    
    db.add(uploaded_credential)
    await db.commit()
    await db.refresh(uploaded_credential)
    
    return CredentialUploadStatusResponse(
        upload_id=uploaded_credential.id,
        status=UploadStatus(uploaded_credential.status),
        message="File uploaded successfully. Ready for processing.",
    )


@router.get("/subcontractors/{subcontractor_id}/credentials/uploads", response_model=List[CredentialUploadResponse])
async def get_subcontractor_uploads(
    subcontractor_id: uuid.UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    team_id = _team_id_from_user(current_user)
    await _get_subcontractor_scoped(db, subcontractor_id, team_id)
    
    query = (
        select(UploadedCredential)
        .where(UploadedCredential.subcontractor_id == subcontractor_id)
        .offset(skip)
        .limit(limit)
        .order_by(UploadedCredential.created_at.desc())
    )
    
    result = await db.execute(query)
    uploads = result.scalars().all()
    
    return [
        CredentialUploadResponse(
            id=u.id,
            subcontractor_id=u.subcontractor_id,
            certification_id=u.certification_id,
            original_filename=u.original_filename,
            stored_filename=u.stored_filename,
            file_size=u.file_size,
            mime_type=u.mime_type,
            status=UploadStatus(u.status),
            extraction_status=ExtractionStatus(u.extraction_status),
            virus_scan_status=VirusScanStatus(u.virus_scan_status),
            created_at=u.created_at,
            updated_at=u.updated_at,
        )
        for u in uploads
    ]


@router.get("/credentials/uploads/{upload_id}", response_model=CredentialUploadWithExtraction)
async def get_upload(
    upload_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    team_id = _team_id_from_user(current_user)
    upload = await _get_upload_scoped(db, upload_id, team_id)
    
    return CredentialUploadWithExtraction(
        id=upload.id,
        subcontractor_id=upload.subcontractor_id,
        certification_id=upload.certification_id,
        original_filename=upload.original_filename,
        stored_filename=upload.stored_filename,
        file_size=upload.file_size,
        mime_type=upload.mime_type,
        status=UploadStatus(upload.status),
        extraction_status=ExtractionStatus(upload.extraction_status),
        virus_scan_status=VirusScanStatus(upload.virus_scan_status),
        extracted_cert_type=upload.extracted_cert_type,
        extracted_cert_number=upload.extracted_cert_number,
        extracted_issue_date=upload.extracted_issue_date,
        extracted_expiration_date=upload.extracted_expiration_date,
        extracted_issuing_authority=upload.extracted_issuing_authority,
        ocr_raw_text=upload.ocr_raw_text,
        created_at=upload.created_at,
        updated_at=upload.updated_at,
    )


@router.post("/credentials/uploads/{upload_id}/process", response_model=CredentialUploadStatusResponse)
async def process_upload(
    upload_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    team_id = _team_id_from_user(current_user)
    upload = await _get_upload_scoped(db, upload_id, team_id)
    
    if upload.status == UploadStatus.PROCESSING.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upload is already being processed"
        )
    
    upload.status = UploadStatus.PROCESSING.value
    await db.commit()
    
    extracted_data = await upload_service.extract_credential_data(upload.file_path, upload.mime_type)
    
    upload.extraction_status = ExtractionStatus.SUCCESS.value if extracted_data.cert_type else ExtractionStatus.NO_DATA.value
    upload.extracted_cert_type = extracted_data.cert_type
    upload.extracted_cert_number = extracted_data.cert_number
    upload.extracted_issue_date = extracted_data.issue_date
    upload.extracted_expiration_date = extracted_data.expiration_date
    upload.extracted_issuing_authority = extracted_data.issuing_authority
    upload.ocr_raw_text = extracted_data.raw_text
    upload.status = UploadStatus.COMPLETED.value
    upload.virus_scan_status = VirusScanStatus.CLEAN.value
    
    await db.commit()
    await db.refresh(upload)
    
    message = "Processing completed."
    if extracted_data.cert_type:
        message += f" Extracted certification type: {extracted_data.cert_type}"
    else:
        message += " No credential data extracted."
    
    return CredentialUploadStatusResponse(
        upload_id=upload.id,
        status=UploadStatus(upload.status),
        message=message,
        certification_id=upload.certification_id,
    )


@router.post("/credentials/uploads/{upload_id}/create-certification", response_model=CertificationResponse, status_code=status.HTTP_201_CREATED)
async def create_certification_from_upload(
    upload_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    team_id = _team_id_from_user(current_user)
    upload = await _get_upload_scoped(db, upload_id, team_id)
    
    if upload.certification_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Certification already created from this upload"
        )
    
    if not upload.extracted_cert_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No extracted credential data. Process the upload first."
        )
    
    cert_data = CertificationCreate(
        subcontractor_id=upload.subcontractor_id,
        certification_type=upload.extracted_cert_type,
        certification_number=upload.extracted_cert_number,
        issuing_authority=upload.extracted_issuing_authority,
        issue_date=_parse_date(upload.extracted_issue_date) if upload.extracted_issue_date else None,
        expiration_date=_parse_date(upload.extracted_expiration_date) if upload.extracted_expiration_date else None,
        document_url=f"/files/credentials/{upload.stored_filename}",
    )
    
    certification = Certification(**cert_data.model_dump())
    db.add(certification)
    
    upload.certification_id = certification.id
    upload.status = UploadStatus.COMPLETED.value
    
    await db.commit()
    await db.refresh(certification)
    
    return certification


def _parse_date(date_str: Optional[str]) -> Optional[date]:
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            from datetime import datetime
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


@router.delete("/credentials/uploads/{upload_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_upload(
    upload_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    team_id = _team_id_from_user(current_user)
    upload = await _get_upload_scoped(db, upload_id, team_id)
    
    await upload_service.delete_uploaded_file(upload.stored_filename)
    
    await db.delete(upload)
    await db.commit()