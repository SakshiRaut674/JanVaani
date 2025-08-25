# app/models/bill_model.py
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from bson import ObjectId
from datetime import datetime
from enum import Enum

class BillType(str, Enum):
    PROPERTY_TAX = "property_tax"
    WATER_BILL = "water_bill"
    GARBAGE_FEE = "garbage_fee"
    SEWAGE_FEE = "sewage_fee"
    STREET_LIGHT_FEE = "street_light_fee"
    OTHER = "other"

class BillStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"
    PARTIAL = "partial"

class BillPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

class BillCreateModel(BaseModel):
    bill_type: BillType
    amount: float
    due_date: datetime
    description: str
    year: str
    period: Optional[str] = None  # For monthly bills like water
    property_id: Optional[str] = None  # For property-related bills
    meter_reading: Optional[float] = None  # For water bills
    previous_reading: Optional[float] = None  # For water bills
    consumption: Optional[float] = None  # For water bills
    late_fee: Optional[float] = 0.0
    penalty: Optional[float] = 0.0
    discount: Optional[float] = 0.0
    metadata: Optional[Dict[str, Any]] = {}

class BillUpdateModel(BaseModel):
    amount: Optional[float] = None
    due_date: Optional[datetime] = None
    status: Optional[BillStatus] = None
    description: Optional[str] = None
    late_fee: Optional[float] = None
    penalty: Optional[float] = None
    discount: Optional[float] = None
    payment_id: Optional[str] = None
    paid_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None

class BillPaymentModel(BaseModel):
    bill_id: str
    payment_method: str
    amount_paid: float
    razorpay_order_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = {}

class BillResponseModel(BaseModel):
    id: Optional[ObjectId] = Field(alias="_id")
    bill_id: str  # Our internal bill ID
    user_id: str
    bill_type: BillType
    amount: float
    amount_paid: Optional[float] = 0.0
    balance_amount: Optional[float] = None
    status: BillStatus
    priority: BillPriority
    due_date: datetime
    description: str
    year: str
    period: Optional[str] = None
    property_id: Optional[str] = None
    meter_reading: Optional[float] = None
    previous_reading: Optional[float] = None
    consumption: Optional[float] = None
    late_fee: Optional[float] = 0.0
    penalty: Optional[float] = 0.0
    discount: Optional[float] = 0.0
    payment_id: Optional[str] = None  # Payment record ID if paid
    payment_history: Optional[List[str]] = []  # List of payment IDs
    created_at: datetime
    updated_at: datetime
    paid_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = {}

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

class BillSummaryModel(BaseModel):
    total_pending: float
    total_paid: float
    total_overdue: float
    total_bills: int
    pending_bills: int
    paid_bills: int
    overdue_bills: int
    by_type: Dict[str, Dict[str, Any]]  # bill_type -> {count, amount, status_breakdown}
    upcoming_due: List[BillResponseModel]  # Bills due in next 30 days
    overdue_bills: List[BillResponseModel]  # Overdue bills

class BillSearchModel(BaseModel):
    search_term: Optional[str] = None
    bill_type: Optional[BillType] = None
    status: Optional[BillStatus] = None
    priority: Optional[BillPriority] = None
    year: Optional[str] = None
    due_date_from: Optional[datetime] = None
    due_date_to: Optional[datetime] = None
    amount_min: Optional[float] = None
    amount_max: Optional[float] = None
    property_id: Optional[str] = None

class BillListResponseModel(BaseModel):
    bills: List[BillResponseModel]
    summary: BillSummaryModel
    total_count: int
    page: int
    total_pages: int
