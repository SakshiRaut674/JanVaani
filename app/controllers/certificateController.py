# app/controllers/certificateController.py
from fastapi import HTTPException, status, UploadFile
from fastapi.responses import JSONResponse
from app.models.certificate_model import (
    CertificateCreateModel, 
    CertificateUpdateModel, 
    CertificateStatusUpdateModel,
    CertificateResponseModel,
    CertificateType,
    CertificateStatus,
    CertificatePriority,
    CertificateTypeInfo,
    CertificateSearchModel,
    BirthCertificateData,
    DeathCertificateData,
    MarriageCertificateData
)
from typing import Optional, List, Dict, Any
from pymongo import ReturnDocument
from bson import ObjectId
from app.database.database import get_db
from datetime import datetime, timedelta
import uuid
import re

# Helper function to make MongoDB documents JSON serializable
def serialize_document(doc):
    if isinstance(doc, dict):
        return {k: serialize_document(v) for k, v in doc.items()}
    elif isinstance(doc, list):
        return [serialize_document(item) for item in doc]
    elif isinstance(doc, ObjectId):
        return str(doc)
    elif isinstance(doc, datetime):
        return doc.isoformat()
    else:
        return doc

# Generate unique application ID
def generate_application_id(cert_type: str) -> str:
    prefix = cert_type.upper()[:4]
    timestamp = datetime.now().strftime("%Y%m%d")
    unique_suffix = str(uuid.uuid4())[:8].upper()
    return f"{prefix}{timestamp}{unique_suffix}"

# Validate certificate-specific data
def validate_certificate_data(cert_type: CertificateType, data: Dict[str, Any]) -> bool:
    try:
        if cert_type == CertificateType.BIRTH:
            BirthCertificateData(**data)
        elif cert_type == CertificateType.DEATH:
            DeathCertificateData(**data)
        elif cert_type == CertificateType.MARRIAGE:
            MarriageCertificateData(**data)
        return True
    except Exception as e:
        print(f"Validation error for {cert_type}: {e}")
        return False

# Get certificate fee based on type and priority
def calculate_certificate_fee(cert_type: CertificateType, priority: CertificatePriority) -> float:
    base_fees = {
        CertificateType.BIRTH: 50.0,
        CertificateType.DEATH: 50.0,
        CertificateType.MARRIAGE: 100.0,
        CertificateType.INCOME: 75.0,
        CertificateType.DOMICILE: 50.0,
        CertificateType.CASTE: 25.0,
        CertificateType.OTHER: 50.0
    }
    
    base_fee = base_fees.get(cert_type, 50.0)
    
    # Add urgent processing fee
    if priority == CertificatePriority.URGENT:
        base_fee += 200.0
    elif priority == CertificatePriority.HIGH:
        base_fee += 100.0
    
    return base_fee

# Create new certificate application
async def create_certificate_application(
    certificate_data: CertificateCreateModel,
    current_user: dict
) -> JSONResponse:
    try:
        db = get_db()
        user_id = str(current_user["_id"])
        
        # Validate certificate-specific data
        if not validate_certificate_data(certificate_data.certificate_type, certificate_data.certificate_data):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid data for {certificate_data.certificate_type} certificate"
            )
        
        # Generate application ID
        application_id = generate_application_id(certificate_data.certificate_type.value)
        
        # Calculate fee
        fee_amount = calculate_certificate_fee(certificate_data.certificate_type, certificate_data.priority)
        
        # Create certificate document
        certificate_doc = {
            "application_id": application_id,
            "certificate_type": certificate_data.certificate_type.value,
            "status": CertificateStatus.PENDING.value,
            "priority": certificate_data.priority.value,
            "applicant_name": certificate_data.applicant_name,
            "applicant_mobile": certificate_data.applicant_mobile or current_user.get("mobile"),
            "applicant_email": certificate_data.applicant_email or current_user.get("email"),
            "applicant_address": certificate_data.applicant_address,
            "certificate_data": certificate_data.certificate_data,
            "documents": certificate_data.documents,
            "additional_notes": certificate_data.additional_notes,
            "user_id": user_id,
            "fee_amount": fee_amount,
            "payment_status": "pending",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "status_history": [{
                "status": CertificateStatus.PENDING.value,
                "changed_at": datetime.utcnow(),
                "changed_by": "user",
                "notes": "Application submitted"
            }]
        }
        
        # Add urgent processing fields if applicable
        if certificate_data.priority == CertificatePriority.URGENT:
            certificate_doc["urgent_reason"] = certificate_data.urgent_reason
            certificate_doc["estimated_completion_date"] = datetime.utcnow() + timedelta(days=3)
        else:
            certificate_doc["estimated_completion_date"] = datetime.utcnow() + timedelta(days=7)
        
        # Insert into database
        result = await db["certificates"].insert_one(certificate_doc)
        
        # Get the inserted document
        created_certificate = await db["certificates"].find_one({"_id": result.inserted_id})
        serialized_certificate = serialize_document(created_certificate)
        
        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={
                "message": "Certificate application created successfully",
                "application_id": application_id,
                "certificate": serialized_certificate,
                "fee_amount": fee_amount,
                "payment_required": True
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error creating certificate application: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create certificate application: {str(e)}"
        )

# Get user's certificate applications
async def get_user_certificates(
    certificate_type: Optional[CertificateType] = None,
    status_filter: Optional[CertificateStatus] = None,
    limit: int = 10,
    skip: int = 0,
    current_user: dict = None
) -> JSONResponse:
    try:
        db = get_db()
        user_id = str(current_user["_id"])
        
        # Build query
        query = {"user_id": user_id}
        
        if certificate_type:
            query["certificate_type"] = certificate_type.value
        
        if status_filter:
            query["status"] = status_filter.value
        
        # Get certificates with pagination
        cursor = db["certificates"].find(query).sort("created_at", -1).skip(skip).limit(limit)
        certificates = await cursor.to_list(length=None)
        
        # Get total count
        total_count = await db["certificates"].count_documents(query)
        
        # Serialize documents
        serialized_certificates = [serialize_document(cert) for cert in certificates]
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "certificates": serialized_certificates,
                "total_count": total_count,
                "page": skip // limit + 1,
                "total_pages": (total_count + limit - 1) // limit
            }
        )
        
    except Exception as e:
        print(f"Error fetching user certificates: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch certificates: {str(e)}"
        )

# Get certificate by ID
async def get_certificate_by_id(certificate_id: str, current_user: dict) -> JSONResponse:
    try:
        db = get_db()
        user_id = str(current_user["_id"])
        
        # Validate ObjectId
        if not ObjectId.is_valid(certificate_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid certificate ID"
            )
        
        # Find certificate
        certificate = await db["certificates"].find_one({
            "_id": ObjectId(certificate_id),
            "user_id": user_id
        })
        
        if not certificate:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Certificate not found"
            )
        
        serialized_certificate = serialize_document(certificate)
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "certificate": serialized_certificate
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error fetching certificate: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch certificate: {str(e)}"
        )

# Update certificate application
async def update_certificate_application(
    certificate_id: str,
    update_data: CertificateUpdateModel,
    current_user: dict
) -> JSONResponse:
    try:
        db = get_db()
        user_id = str(current_user["_id"])
        
        # Validate ObjectId
        if not ObjectId.is_valid(certificate_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid certificate ID"
            )
        
        # Check if certificate exists and belongs to user
        certificate = await db["certificates"].find_one({
            "_id": ObjectId(certificate_id),
            "user_id": user_id
        })
        
        if not certificate:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Certificate not found"
            )
        
        # Check if certificate can be updated (only pending or document_required status)
        if certificate["status"] not in [CertificateStatus.PENDING.value, CertificateStatus.DOCUMENT_REQUIRED.value]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Certificate cannot be updated in current status"
            )
        
        # Build update data
        update_fields = {k: v for k, v in update_data.model_dump(exclude_unset=True).items() if v is not None}
        
        if update_fields:
            update_fields["updated_at"] = datetime.utcnow()
            
            # Validate certificate data if provided
            if "certificate_data" in update_fields:
                cert_type = CertificateType(certificate["certificate_type"])
                if not validate_certificate_data(cert_type, update_fields["certificate_data"]):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid certificate data"
                    )
            
            # Update certificate
            updated_certificate = await db["certificates"].find_one_and_update(
                {"_id": ObjectId(certificate_id)},
                {"$set": update_fields},
                return_document=ReturnDocument.AFTER
            )
            
            serialized_certificate = serialize_document(updated_certificate)
            
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "message": "Certificate updated successfully",
                    "certificate": serialized_certificate
                }
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields to update"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error updating certificate: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update certificate: {str(e)}"
        )

# Get certificate types and their information
async def get_certificate_types() -> JSONResponse:
    certificate_types = [
        {
            "type": "birth",
            "name": "Birth Certificate",
            "description": "Official document certifying the birth of a person",
            "requirements": [
                "Hospital birth record or delivery certificate",
                "Parents' identity proof (Aadhar/Voter ID/Passport)",
                "Address proof",
                "Application form (filled and signed)"
            ],
            "processing_time": "7-10 working days",
            "fee": 50.0,
            "urgent_fee": 250.0,
            "documents_required": ["birth_record", "parent_id", "address_proof", "application_form"]
        },
        {
            "type": "death",
            "name": "Death Certificate",
            "description": "Official document certifying the death of a person",
            "requirements": [
                "Medical certificate of death",
                "Identity proof of deceased",
                "Applicant's identity proof",
                "Address proof",
                "Hospital/cremation certificate"
            ],
            "processing_time": "5-7 working days",
            "fee": 50.0,
            "urgent_fee": 250.0,
            "documents_required": ["death_certificate", "deceased_id", "applicant_id", "address_proof"]
        },
        {
            "type": "marriage",
            "name": "Marriage Certificate",
            "description": "Official document certifying the marriage between two individuals",
            "requirements": [
                "Marriage registration form",
                "Identity proof of both parties",
                "Age proof of both parties",
                "Address proof",
                "Passport size photographs (both parties)",
                "Witness identity proofs (2 witnesses)"
            ],
            "processing_time": "10-15 working days",
            "fee": 100.0,
            "urgent_fee": 300.0,
            "documents_required": ["marriage_form", "bride_id", "groom_id", "age_proof", "photos", "witness_ids"]
        },
        {
            "type": "income",
            "name": "Income Certificate",
            "description": "Certificate stating the annual income of an individual/family",
            "requirements": [
                "Income declaration form",
                "Salary certificate/business income proof",
                "Bank statements (last 6 months)",
                "Identity proof",
                "Address proof"
            ],
            "processing_time": "7-10 working days",
            "fee": 75.0,
            "urgent_fee": 275.0,
            "documents_required": ["income_form", "salary_certificate", "bank_statements", "id_proof", "address_proof"]
        },
        {
            "type": "domicile",
            "name": "Domicile Certificate",
            "description": "Certificate proving residence in a particular state/district",
            "requirements": [
                "Domicile application form",
                "Birth certificate",
                "Educational certificates",
                "Address proof (minimum 3 years)",
                "Identity proof"
            ],
            "processing_time": "10-15 working days",
            "fee": 50.0,
            "urgent_fee": 250.0,
            "documents_required": ["domicile_form", "birth_certificate", "education_certificates", "address_proof", "id_proof"]
        },
        {
            "type": "caste",
            "name": "Caste Certificate",
            "description": "Certificate verifying the caste/community of an individual",
            "requirements": [
                "Caste certificate application",
                "Birth certificate",
                "School leaving certificate",
                "Parent's caste certificate (if available)",
                "Identity proof",
                "Address proof"
            ],
            "processing_time": "15-20 working days",
            "fee": 25.0,
            "urgent_fee": 225.0,
            "documents_required": ["caste_form", "birth_certificate", "school_certificate", "parent_caste_cert", "id_proof"]
        }
    ]
    
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "certificate_types": certificate_types
        }
    )

# Get certificate requirements by type
async def get_certificate_requirements(cert_type: str) -> JSONResponse:
    certificate_types = {
        "birth": {
            "requirements": [
                "Hospital birth record or delivery certificate",
                "Parents' identity proof (Aadhar/Voter ID/Passport)",
                "Address proof",
                "Application form (filled and signed)"
            ],
            "processing_time": "7-10 working days",
            "fee": 50.0,
            "documents_needed": ["birth_record", "parent_id", "address_proof", "application_form"]
        },
        "death": {
            "requirements": [
                "Medical certificate of death",
                "Identity proof of deceased",
                "Applicant's identity proof",
                "Address proof",
                "Hospital/cremation certificate"
            ],
            "processing_time": "5-7 working days",
            "fee": 50.0,
            "documents_needed": ["death_certificate", "deceased_id", "applicant_id", "address_proof"]
        },
        "marriage": {
            "requirements": [
                "Marriage registration form",
                "Identity proof of both parties",
                "Age proof of both parties",
                "Address proof",
                "Passport size photographs (both parties)",
                "Witness identity proofs (2 witnesses)"
            ],
            "processing_time": "10-15 working days",
            "fee": 100.0,
            "documents_needed": ["marriage_form", "bride_id", "groom_id", "age_proof", "photos", "witness_ids"]
        }
    }
    
    if cert_type not in certificate_types:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certificate type not found"
        )
    
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=certificate_types[cert_type]
    )

# Track certificate status (public endpoint)
async def track_certificate_status(application_id: str) -> JSONResponse:
    try:
        db = get_db()
        
        # Find certificate by application ID
        certificate = await db["certificates"].find_one({"application_id": application_id})
        
        if not certificate:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Certificate application not found"
            )
        
        # Return limited information for public tracking
        tracking_info = {
            "application_id": certificate["application_id"],
            "certificate_type": certificate["certificate_type"],
            "status": certificate["status"],
            "created_at": certificate["created_at"].isoformat(),
            "estimated_completion_date": certificate.get("estimated_completion_date", "").isoformat() if certificate.get("estimated_completion_date") else None,
            "last_updated": certificate["updated_at"].isoformat()
        }
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "tracking_info": tracking_info
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error tracking certificate: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to track certificate"
        )

# Upload certificate document
async def upload_certificate_document(
    certificate_id: str,
    file: UploadFile,
    current_user: dict
) -> JSONResponse:
    try:
        db = get_db()
        user_id = str(current_user["_id"])
        
        # Validate ObjectId
        if not ObjectId.is_valid(certificate_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid certificate ID"
            )
        
        # Check if certificate exists and belongs to user
        certificate = await db["certificates"].find_one({
            "_id": ObjectId(certificate_id),
            "user_id": user_id
        })
        
        if not certificate:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Certificate not found"
            )
        
        # For now, just store the filename - in production, upload to cloud storage
        document_name = f"{certificate_id}_{file.filename}"
        
        # Update certificate with new document
        await db["certificates"].update_one(
            {"_id": ObjectId(certificate_id)},
            {
                "$push": {"documents": document_name},
                "$set": {"updated_at": datetime.utcnow()}
            }
        )
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "message": "Document uploaded successfully",
                "document_name": document_name
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error uploading document: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload document"
        )

# Update payment status
async def update_payment_status(
    application_id: str,
    payment_id: str,
    payment_status: str,
    current_user: dict
) -> JSONResponse:
    try:
        db = get_db()
        user_id = str(current_user["_id"])
        
        # Find and update certificate
        certificate = await db["certificates"].find_one_and_update(
            {
                "application_id": application_id,
                "user_id": user_id
            },
            {
                "$set": {
                    "payment_status": payment_status,
                    "payment_id": payment_id,
                    "updated_at": datetime.utcnow()
                }
            },
            return_document=ReturnDocument.AFTER
        )
        
        if not certificate:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Certificate application not found"
            )
        
        # If payment successful, update status to under_review
        if payment_status == "paid":
            await db["certificates"].update_one(
                {"application_id": application_id},
                {
                    "$set": {
                        "status": CertificateStatus.UNDER_REVIEW.value,
                        "updated_at": datetime.utcnow()
                    },
                    "$push": {
                        "status_history": {
                            "status": CertificateStatus.UNDER_REVIEW.value,
                            "changed_at": datetime.utcnow(),
                            "changed_by": "system",
                            "notes": "Payment confirmed - moved to review"
                        }
                    }
                }
            )
        
        serialized_certificate = serialize_document(certificate)
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "message": "Payment status updated successfully",
                "certificate": serialized_certificate
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error updating payment status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update payment status"
        )

# Get user certificate statistics
async def get_user_certificate_stats(current_user: dict) -> JSONResponse:
    try:
        db = get_db()
        user_id = str(current_user["_id"])
        
        # Aggregate statistics
        pipeline = [
            {"$match": {"user_id": user_id}},
            {
                "$group": {
                    "_id": None,
                    "total": {"$sum": 1},
                    "pending": {"$sum": {"$cond": [{"$eq": ["$status", "pending"]}, 1, 0]}},
                    "under_review": {"$sum": {"$cond": [{"$eq": ["$status", "under_review"]}, 1, 0]}},
                    "approved": {"$sum": {"$cond": [{"$eq": ["$status", "approved"]}, 1, 0]}},
                    "rejected": {"$sum": {"$cond": [{"$eq": ["$status", "rejected"]}, 1, 0]}},
                    "issued": {"$sum": {"$cond": [{"$eq": ["$status", "issued"]}, 1, 0]}}
                }
            }
        ]
        
        stats_cursor = db["certificates"].aggregate(pipeline)
        stats_list = await stats_cursor.to_list(length=None)
        
        if stats_list:
            stats = stats_list[0]
            stats.pop("_id", None)
        else:
            stats = {
                "total": 0,
                "pending": 0,
                "under_review": 0,
                "approved": 0,
                "rejected": 0,
                "issued": 0
            }
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"statistics": stats}
        )
        
    except Exception as e:
        print(f"Error fetching certificate stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch statistics"
        )
