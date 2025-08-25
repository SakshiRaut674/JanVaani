# app/models/certificate_model.py
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from bson import ObjectId
from datetime import datetime
from enum import Enum

class CertificateType(str, Enum):
    BIRTH = "birth"
    DEATH = "death"
    MARRIAGE = "marriage"
    INCOME = "income"
    DOMICILE = "domicile"
    CASTE = "caste"
    OTHER = "other"

class CertificateStatus(str, Enum):
    PENDING = "pending"
    UNDER_REVIEW = "under_review"
    DOCUMENT_REQUIRED = "document_required"
    APPROVED = "approved"
    REJECTED = "rejected"
    ISSUED = "issued"
    COMPLETED = "completed"

class CertificatePriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

# Base model for common certificate fields
class CertificateBaseModel(BaseModel):
    certificate_type: CertificateType
    applicant_name: str = Field(..., min_length=2, max_length=100)
    applicant_mobile: Optional[str] = None
    applicant_email: Optional[str] = None
    applicant_address: str = Field(..., min_length=10, max_length=500)
    documents: List[str] = []
    additional_notes: Optional[str] = None

# Birth Certificate specific fields
class BirthCertificateData(BaseModel):
    child_name: str = Field(..., min_length=2, max_length=100)
    date_of_birth: str  # ISO date string
    place_of_birth: str = Field(..., min_length=2, max_length=200)
    father_name: str = Field(..., min_length=2, max_length=100)
    mother_name: str = Field(..., min_length=2, max_length=100)
    father_occupation: Optional[str] = None
    mother_occupation: Optional[str] = None
    permanent_address: str = Field(..., min_length=10, max_length=500)
    hospital_name: Optional[str] = None
    birth_weight: Optional[str] = None
    gender: Optional[str] = None

# Death Certificate specific fields
class DeathCertificateData(BaseModel):
    deceased_name: str = Field(..., min_length=2, max_length=100)
    date_of_death: str  # ISO date string
    place_of_death: str = Field(..., min_length=2, max_length=200)
    cause_of_death: Optional[str] = None
    father_husband_name: str = Field(..., min_length=2, max_length=100)
    permanent_address: str = Field(..., min_length=10, max_length=500)
    age_at_death: int = Field(..., ge=0, le=150)
    gender: str = Field(..., min_length=1)
    hospital_name: Optional[str] = None
    doctor_name: Optional[str] = None

# Marriage Certificate specific fields
class MarriageCertificateData(BaseModel):
    groom_name: str = Field(..., min_length=2, max_length=100)
    bride_name: str = Field(..., min_length=2, max_length=100)
    date_of_marriage: str  # ISO date string
    place_of_marriage: str = Field(..., min_length=2, max_length=200)
    groom_father_name: str = Field(..., min_length=2, max_length=100)
    bride_father_name: str = Field(..., min_length=2, max_length=100)
    groom_age: int = Field(..., ge=18, le=100)
    bride_age: int = Field(..., ge=18, le=100)
    groom_address: str = Field(..., min_length=10, max_length=500)
    bride_address: str = Field(..., min_length=10, max_length=500)
    witness1_name: str = Field(..., min_length=2, max_length=100)
    witness2_name: str = Field(..., min_length=2, max_length=100)
    marriage_type: Optional[str] = "civil"  # civil, religious, etc.

# Create Application Request Models
class CertificateCreateModel(CertificateBaseModel):
    certificate_data: Dict[str, Any]  # Will contain type-specific data
    priority: Optional[CertificatePriority] = CertificatePriority.MEDIUM
    urgent_reason: Optional[str] = None

# Update Application Request Model
class CertificateUpdateModel(BaseModel):
    applicant_name: Optional[str] = Field(None, min_length=2, max_length=100)
    applicant_mobile: Optional[str] = None
    applicant_email: Optional[str] = None
    applicant_address: Optional[str] = Field(None, min_length=10, max_length=500)
    certificate_data: Optional[Dict[str, Any]] = None
    additional_notes: Optional[str] = None
    priority: Optional[CertificatePriority] = None

# Admin Status Update Model
class CertificateStatusUpdateModel(BaseModel):
    status: CertificateStatus
    admin_notes: Optional[str] = None
    admin_id: Optional[str] = None
    estimated_completion_date: Optional[datetime] = None
    required_documents: Optional[List[str]] = None
    rejection_reason: Optional[str] = None

# Response Models
class CertificateResponseModel(BaseModel):
    id: Optional[ObjectId] = Field(alias="_id")
    application_id: str
    certificate_type: CertificateType
    status: CertificateStatus
    priority: CertificatePriority
    applicant_name: str
    applicant_mobile: Optional[str]
    applicant_email: Optional[str]
    applicant_address: str
    certificate_data: Dict[str, Any]
    documents: List[str]
    additional_notes: Optional[str]
    user_id: str
    admin_notes: Optional[str] = None
    admin_id: Optional[str] = None
    estimated_completion_date: Optional[datetime] = None
    actual_completion_date: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    required_documents: Optional[List[str]] = None
    fee_amount: Optional[float] = None
    payment_status: Optional[str] = "pending"  # pending, paid, refunded
    payment_id: Optional[str] = None
    certificate_number: Optional[str] = None
    issued_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    status_history: List[Dict] = []

    class Config:
        arbitrary_types_allowed = True
        populate_by_name = True
        json_encoders = {
            ObjectId: lambda oid: str(oid),
        }

# Certificate Types Info Model (for frontend)
class CertificateTypeInfo(BaseModel):
    type: CertificateType
    name: str
    description: str
    requirements: List[str]
    processing_time: str
    fee: float
    urgent_fee: Optional[float] = None
    documents_required: List[str]

# Search and Filter Models
class CertificateSearchModel(BaseModel):
    search_term: Optional[str] = None
    certificate_type: Optional[CertificateType] = None
    status: Optional[CertificateStatus] = None
    priority: Optional[CertificatePriority] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    user_id: Optional[str] = None

# Statistics Model
class CertificateStatsModel(BaseModel):
    total_applications: int
    pending: int
    under_review: int
    approved: int
    rejected: int
    issued: int
    by_type: Dict[str, int]
    this_month: int
    this_week: int
