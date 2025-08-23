# app/models/grievance_model.py
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from bson import ObjectId
from datetime import datetime
from enum import Enum

class GrievanceCategory(str, Enum):
    GARBAGE = "garbage"
    WATER_SUPPLY = "water_supply"
    DRAINAGE = "drainage"
    STREET_LIGHTS = "street_lights"
    ROADS = "roads"
    SEWAGE = "sewage"
    NOISE_POLLUTION = "noise_pollution"
    ILLEGAL_CONSTRUCTION = "illegal_construction"
    PROPERTY_TAX = "property_tax"
    OTHER = "other"

class GrievanceStatus(str, Enum):
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"
    REJECTED = "rejected"

class GrievancePriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

class GrievanceCreateModel(BaseModel):
    title: str = Field(..., min_length=5, max_length=200)
    description: str = Field(..., min_length=10, max_length=1000)
    category: GrievanceCategory
    location: str = Field(..., min_length=5, max_length=500)
    address: Optional[str] = None
    landmark: Optional[str] = None
    ward_number: Optional[str] = None
    pin_code: Optional[str] = None
    contact_person: Optional[str] = None
    alternate_mobile: Optional[str] = None
    priority: Optional[GrievancePriority] = GrievancePriority.MEDIUM
    anonymous: Optional[bool] = False

class GrievanceUpdateModel(BaseModel):
    title: Optional[str] = Field(None, min_length=5, max_length=200)
    description: Optional[str] = Field(None, min_length=10, max_length=1000)
    category: Optional[GrievanceCategory] = None
    location: Optional[str] = Field(None, min_length=5, max_length=500)
    address: Optional[str] = None
    landmark: Optional[str] = None
    ward_number: Optional[str] = None
    pin_code: Optional[str] = None
    contact_person: Optional[str] = None
    alternate_mobile: Optional[str] = None
    priority: Optional[GrievancePriority] = None

class GrievanceStatusUpdateModel(BaseModel):
    status: GrievanceStatus
    admin_notes: Optional[str] = None
    estimated_resolution_date: Optional[datetime] = None

class GrievanceResponseModel(BaseModel):
    id: Optional[ObjectId] = Field(alias="_id")
    grievance_id: str
    title: str
    description: str
    category: GrievanceCategory
    status: GrievanceStatus
    priority: GrievancePriority
    location: str
    address: Optional[str] = None
    landmark: Optional[str] = None
    ward_number: Optional[str] = None
    pin_code: Optional[str] = None
    contact_person: Optional[str] = None
    alternate_mobile: Optional[str] = None
    user_id: str
    user_mobile: str
    anonymous: bool
    attachments: List[str] = []
    admin_notes: Optional[str] = None
    assigned_to: Optional[str] = None
    estimated_resolution_date: Optional[datetime] = None
    actual_resolution_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    status_history: List[Dict] = []

    class Config:
        arbitrary_types_allowed = True
        populate_by_name = True
        json_encoders = {
            ObjectId: lambda oid: str(oid),
        }