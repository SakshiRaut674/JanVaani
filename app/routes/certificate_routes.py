# app/routes/certificate_routes.py
from fastapi import APIRouter, Depends, UploadFile, File, Query, Path
from app.controllers.certificateController import (
    create_certificate_application,
    get_user_certificates,
    get_certificate_by_id,
    update_certificate_application,
    get_certificate_types,
    get_certificate_requirements,
    track_certificate_status,
    upload_certificate_document,
    update_payment_status,
    get_user_certificate_stats
)
from app.models.certificate_model import (
    CertificateCreateModel,
    CertificateUpdateModel,
    CertificateType,
    CertificateStatus,
    CertificatePriority
)
from app.middlewares.authMiddleware import get_current_user
from typing import Optional

router = APIRouter(tags=["Certificates"])

# Public routes (no authentication required)
@router.get("/types")
async def get_available_certificate_types():
    """Get all available certificate types with their details"""
    return await get_certificate_types()

@router.get("/requirements/{cert_type}")
async def get_requirements_for_certificate_type(
    cert_type: str = Path(..., description="Certificate type (birth, death, marriage, etc.)")
):
    """Get requirements for a specific certificate type"""
    return await get_certificate_requirements(cert_type)

@router.get("/track/{application_id}")
async def track_application_status(
    application_id: str = Path(..., description="Certificate application ID")
):
    """Public endpoint to track certificate application status"""
    return await track_certificate_status(application_id)

# Protected routes (require authentication)
@router.post("/apply")
async def apply_for_certificate(
    certificate_data: CertificateCreateModel,
    current_user: dict = Depends(get_current_user)
):
    """Submit a new certificate application"""
    return await create_certificate_application(certificate_data, current_user)

@router.get("/my-applications")
async def get_my_certificate_applications(
    certificate_type: Optional[CertificateType] = Query(None, description="Filter by certificate type"),
    status: Optional[CertificateStatus] = Query(None, description="Filter by status"),
    limit: int = Query(20, ge=1, le=100, description="Number of applications per page"),
    skip: int = Query(0, ge=0, description="Number of applications to skip"),
    current_user: dict = Depends(get_current_user)
):
    """Get user's certificate applications with optional filters"""
    return await get_user_certificates(certificate_type, status, limit, skip, current_user)

@router.get("/my-applications/{certificate_id}")
async def get_certificate_application_details(
    certificate_id: str = Path(..., description="Certificate ID"),
    current_user: dict = Depends(get_current_user)
):
    """Get specific certificate application details"""
    return await get_certificate_by_id(certificate_id, current_user)

@router.put("/my-applications/{certificate_id}")
async def update_certificate_application_details(
    certificate_id: str = Path(..., description="Certificate ID"),
    update_data: CertificateUpdateModel = ...,
    current_user: dict = Depends(get_current_user)
):
    """Update certificate application (only if status allows)"""
    return await update_certificate_application(certificate_id, update_data, current_user)

@router.post("/my-applications/{certificate_id}/upload-document")
async def upload_certificate_document_file(
    certificate_id: str = Path(..., description="Certificate ID"),
    file: UploadFile = File(..., description="Document file to upload"),
    current_user: dict = Depends(get_current_user)
):
    """Upload supporting document for certificate application"""
    return await upload_certificate_document(certificate_id, file, current_user)

@router.post("/payment/update")
async def update_certificate_payment_status(
    application_id: str = Query(..., description="Certificate application ID"),
    payment_id: str = Query(..., description="Payment transaction ID"),
    payment_status: str = Query(..., description="Payment status (paid, failed, pending)"),
    current_user: dict = Depends(get_current_user)
):
    """Update payment status for certificate application"""
    return await update_payment_status(application_id, payment_id, payment_status, current_user)

@router.get("/statistics")
async def get_certificate_statistics(
    current_user: dict = Depends(get_current_user)
):
    """Get user's certificate application statistics"""
    return await get_user_certificate_stats(current_user)

# Specific certificate type applications
@router.post("/apply/birth")
async def apply_for_birth_certificate(
    certificate_data: CertificateCreateModel,
    current_user: dict = Depends(get_current_user)
):
    """Apply for birth certificate (convenience endpoint)"""
    certificate_data.certificate_type = CertificateType.BIRTH
    return await create_certificate_application(certificate_data, current_user)

@router.post("/apply/death")
async def apply_for_death_certificate(
    certificate_data: CertificateCreateModel,
    current_user: dict = Depends(get_current_user)
):
    """Apply for death certificate (convenience endpoint)"""
    certificate_data.certificate_type = CertificateType.DEATH
    return await create_certificate_application(certificate_data, current_user)

@router.post("/apply/marriage")
async def apply_for_marriage_certificate(
    certificate_data: CertificateCreateModel,
    current_user: dict = Depends(get_current_user)
):
    """Apply for marriage certificate (convenience endpoint)"""
    certificate_data.certificate_type = CertificateType.MARRIAGE
    return await create_certificate_application(certificate_data, current_user)

@router.post("/apply/income")
async def apply_for_income_certificate(
    certificate_data: CertificateCreateModel,
    current_user: dict = Depends(get_current_user)
):
    """Apply for income certificate (convenience endpoint)"""
    certificate_data.certificate_type = CertificateType.INCOME
    return await create_certificate_application(certificate_data, current_user)

@router.post("/apply/domicile")
async def apply_for_domicile_certificate(
    certificate_data: CertificateCreateModel,
    current_user: dict = Depends(get_current_user)
):
    """Apply for domicile certificate (convenience endpoint)"""
    certificate_data.certificate_type = CertificateType.DOMICILE
    return await create_certificate_application(certificate_data, current_user)

@router.post("/apply/caste")
async def apply_for_caste_certificate(
    certificate_data: CertificateCreateModel,
    current_user: dict = Depends(get_current_user)
):
    """Apply for caste certificate (convenience endpoint)"""
    certificate_data.certificate_type = CertificateType.CASTE
    return await create_certificate_application(certificate_data, current_user)

# Search and filter endpoints
@router.get("/search")
async def search_certificate_applications(
    search_term: Optional[str] = Query(None, description="Search in application ID, name, etc."),
    certificate_type: Optional[CertificateType] = Query(None, description="Filter by certificate type"),
    status: Optional[CertificateStatus] = Query(None, description="Filter by status"),
    priority: Optional[CertificatePriority] = Query(None, description="Filter by priority"),
    limit: int = Query(20, ge=1, le=100, description="Number of results per page"),
    skip: int = Query(0, ge=0, description="Number of results to skip"),
    current_user: dict = Depends(get_current_user)
):
    """Search and filter certificate applications"""
    return await get_user_certificates(certificate_type, status, limit, skip, current_user)

# Bulk operations endpoints
@router.get("/download-documents/{certificate_id}")
async def download_certificate_documents(
    certificate_id: str = Path(..., description="Certificate ID"),
    current_user: dict = Depends(get_current_user)
):
    """Download all documents for a certificate application"""
    # This would implement document zip download in production
    from fastapi import HTTPException
    raise HTTPException(status_code=501, detail="Document download not implemented yet")

@router.get("/download-certificate/{certificate_id}")
async def download_issued_certificate(
    certificate_id: str = Path(..., description="Certificate ID"),
    current_user: dict = Depends(get_current_user)
):
    """Download issued certificate PDF"""
    # This would implement PDF generation and download in production
    from fastapi import HTTPException
    raise HTTPException(status_code=501, detail="Certificate download not implemented yet")
