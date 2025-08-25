# app/models/payment_model.py
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from bson import ObjectId
from datetime import datetime
from enum import Enum

class PaymentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"

class PaymentMethod(str, Enum):
    ONLINE = "online"
    CARD = "card"
    UPI = "upi"
    NET_BANKING = "net_banking"
    WALLET = "wallet"
    CASH = "cash"

class ServiceType(str, Enum):
    CERTIFICATE = "certificate"
    GRIEVANCE = "grievance"
    PROPERTY_TAX = "property_tax"
    WATER_BILL = "water_bill"
    GARBAGE_FEE = "garbage_fee"
    FINE = "fine"
    OTHER = "other"

class PaymentCreateModel(BaseModel):
    service_type: ServiceType
    service_id: str  # ID of the bill/certificate/service being paid for
    amount: float
    payment_method: PaymentMethod
    razorpay_order_id: Optional[str] = None
    razorpay_payment_id: Optional[str] = None
    razorpay_signature: Optional[str] = None
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = {}

class PaymentUpdateModel(BaseModel):
    status: Optional[PaymentStatus] = None
    razorpay_payment_id: Optional[str] = None
    razorpay_signature: Optional[str] = None
    failure_reason: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class PaymentResponseModel(BaseModel):
    id: Optional[ObjectId] = Field(alias="_id")
    payment_id: str  # Our internal payment ID
    user_id: str
    service_type: ServiceType
    service_id: str
    amount: float
    status: PaymentStatus
    payment_method: PaymentMethod
    razorpay_order_id: Optional[str]
    razorpay_payment_id: Optional[str]
    transaction_id: Optional[str]  # External transaction ID
    description: Optional[str]
    failure_reason: Optional[str]
    metadata: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime
    processed_at: Optional[datetime] = None

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

class PaymentHistoryResponseModel(BaseModel):
    payments: List[PaymentResponseModel]
    total_count: int
    page: int
    total_pages: int

class PaymentStatsModel(BaseModel):
    total_payments: int
    total_amount: float
    successful_payments: int
    successful_amount: float
    failed_payments: int
    pending_payments: int
    this_month_amount: float
    this_year_amount: float
    by_service_type: Dict[str, Dict[str, Any]]  # service_type -> {count, amount}
    by_month: List[Dict[str, Any]]  # Monthly breakdown
