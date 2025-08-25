# app/controllers/paymentController.py
from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
from app.database.database import get_db
from app.models.payment_model import (
    PaymentCreateModel, PaymentUpdateModel, PaymentResponseModel, 
    PaymentHistoryResponseModel, PaymentStatsModel, PaymentStatus, ServiceType
)
from app.models.bill_model import BillResponseModel, BillStatus
from bson import ObjectId
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import uuid
import hashlib
import hmac
import os

def serialize_document(doc):
    """Convert MongoDB document to JSON serializable format"""
    if doc is None:
        return None
    
    if isinstance(doc, list):
        return [serialize_document(item) for item in doc]
    
    if isinstance(doc, dict):
        result = {}
        for key, value in doc.items():
            if isinstance(value, ObjectId):
                result[key] = str(value)
            elif isinstance(value, datetime):
                result[key] = value.isoformat()
            elif isinstance(value, (dict, list)):
                result[key] = serialize_document(value)
            else:
                result[key] = value
        return result
    
    return doc

async def create_payment_record(
    payment_data: PaymentCreateModel,
    current_user: dict
) -> JSONResponse:
    """Create a new payment record"""
    try:
        db = get_db()
        user_id = str(current_user["_id"])
        
        # Generate unique payment ID
        payment_id = f"PAY{datetime.now().strftime('%Y%m%d')}{str(uuid.uuid4())[:8].upper()}"
        
        # Prepare payment document
        payment_doc = {
            "payment_id": payment_id,
            "user_id": user_id,
            "service_type": payment_data.service_type.value,
            "service_id": payment_data.service_id,
            "amount": payment_data.amount,
            "status": PaymentStatus.PENDING.value,
            "payment_method": payment_data.payment_method.value,
            "razorpay_order_id": payment_data.razorpay_order_id,
            "razorpay_payment_id": payment_data.razorpay_payment_id,
            "razorpay_signature": payment_data.razorpay_signature,
            "description": payment_data.description,
            "metadata": payment_data.metadata or {},
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "processed_at": None,
            "failure_reason": None,
            "transaction_id": None
        }
        
        # Insert payment record
        result = await db["payments"].insert_one(payment_doc)
        
        # Fetch the created payment
        payment = await db["payments"].find_one({"_id": result.inserted_id})
        
        serialized_payment = serialize_document(payment)
        
        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={
                "message": "Payment record created successfully",
                "payment": serialized_payment
            }
        )
        
    except Exception as e:
        print(f"Error creating payment record: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create payment record"
        )

async def update_payment_status(
    payment_id: str,
    update_data: PaymentUpdateModel,
    current_user: dict
) -> JSONResponse:
    """Update payment status"""
    try:
        db = get_db()
        user_id = str(current_user["_id"])
        
        # Prepare update data
        update_fields = {
            "updated_at": datetime.utcnow()
        }
        
        if update_data.status:
            update_fields["status"] = update_data.status.value
            if update_data.status == PaymentStatus.SUCCESS:
                update_fields["processed_at"] = datetime.utcnow()
        
        if update_data.razorpay_payment_id:
            update_fields["razorpay_payment_id"] = update_data.razorpay_payment_id
        
        if update_data.razorpay_signature:
            update_fields["razorpay_signature"] = update_data.razorpay_signature
        
        if update_data.failure_reason:
            update_fields["failure_reason"] = update_data.failure_reason
        
        if update_data.metadata:
            update_fields["metadata"] = update_data.metadata
        
        # Update payment record
        payment = await db["payments"].find_one_and_update(
            {
                "payment_id": payment_id,
                "user_id": user_id
            },
            {"$set": update_fields},
            return_document=True
        )
        
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment record not found"
            )
        
        # If payment successful, update the related service (bill/certificate)
        if update_data.status == PaymentStatus.SUCCESS:
            await update_service_payment_status(payment)
        
        serialized_payment = serialize_document(payment)
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "message": "Payment status updated successfully",
                "payment": serialized_payment
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

async def update_service_payment_status(payment: dict):
    """Update the payment status of the related service (bill/certificate)"""
    try:
        db = get_db()
        service_type = payment["service_type"]
        service_id = payment["service_id"]
        payment_id = payment["payment_id"]
        
        if service_type in ["property_tax", "water_bill", "garbage_fee"]:
            # Update bill status
            await db["bills"].update_one(
                {"bill_id": service_id},
                {
                    "$set": {
                        "status": BillStatus.PAID.value,
                        "payment_id": payment_id,
                        "amount_paid": payment["amount"],
                        "paid_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    },
                    "$push": {
                        "payment_history": payment_id
                    }
                }
            )
        
        elif service_type == "certificate":
            # Update certificate payment status
            await db["certificates"].update_one(
                {"application_id": service_id},
                {
                    "$set": {
                        "payment_status": "paid",
                        "payment_id": payment_id,
                        "status": "under_review",
                        "updated_at": datetime.utcnow()
                    },
                    "$push": {
                        "status_history": {
                            "status": "under_review",
                            "changed_at": datetime.utcnow(),
                            "changed_by": "system",
                            "notes": "Payment confirmed - moved to review"
                        }
                    }
                }
            )
        
    except Exception as e:
        print(f"Error updating service payment status: {e}")
        # Don't raise exception here as payment is already processed

async def get_user_payment_history(
    current_user: dict,
    page: int = 1,
    limit: int = 20,
    service_type: Optional[str] = None,
    payment_status: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None
) -> JSONResponse:
    """Get user's payment history with filters"""
    try:
        db = get_db()
        user_id = str(current_user["_id"])
        
        # Build query
        query = {"user_id": user_id}
        
        if service_type:
            query["service_type"] = service_type
        
        if payment_status:
            query["status"] = payment_status
        
        if date_from or date_to:
            date_query = {}
            if date_from:
                date_query["$gte"] = date_from
            if date_to:
                date_query["$lte"] = date_to
            query["created_at"] = date_query
        
        # Calculate pagination
        skip = (page - 1) * limit
        
        # Get total count
        total_count = await db["payments"].count_documents(query)
        total_pages = (total_count + limit - 1) // limit
        
        # Get payments with pagination
        payments_cursor = db["payments"].find(query).sort("created_at", -1).skip(skip).limit(limit)
        payments = await payments_cursor.to_list(length=limit)
        
        serialized_payments = serialize_document(payments)
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "payments": serialized_payments,
                "total_count": total_count,
                "page": page,
                "total_pages": total_pages
            }
        )
        
    except Exception as e:
        print(f"Error fetching payment history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch payment history"
        )

async def get_payment_by_id(
    payment_id: str,
    current_user: dict
) -> JSONResponse:
    """Get payment details by ID"""
    try:
        db = get_db()
        user_id = str(current_user["_id"])
        
        payment = await db["payments"].find_one({
            "payment_id": payment_id,
            "user_id": user_id
        })
        
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment not found"
            )
        
        serialized_payment = serialize_document(payment)
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"payment": serialized_payment}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error fetching payment: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch payment details"
        )

async def get_payment_statistics(
    current_user: dict
) -> JSONResponse:
    """Get user's payment statistics"""
    try:
        db = get_db()
        user_id = str(current_user["_id"])
        
        # Aggregation pipeline for statistics
        pipeline = [
            {"$match": {"user_id": user_id}},
            {
                "$group": {
                    "_id": None,
                    "total_payments": {"$sum": 1},
                    "total_amount": {"$sum": "$amount"},
                    "successful_payments": {
                        "$sum": {"$cond": [{"$eq": ["$status", "success"]}, 1, 0]}
                    },
                    "successful_amount": {
                        "$sum": {"$cond": [{"$eq": ["$status", "success"]}, "$amount", 0]}
                    },
                    "failed_payments": {
                        "$sum": {"$cond": [{"$eq": ["$status", "failed"]}, 1, 0]}
                    },
                    "pending_payments": {
                        "$sum": {"$cond": [{"$eq": ["$status", "pending"]}, 1, 0]}
                    }
                }
            }
        ]
        
        stats = await db["payments"].aggregate(pipeline).to_list(length=1)
        
        # Get monthly breakdown
        current_year = datetime.now().year
        monthly_pipeline = [
            {"$match": {
                "user_id": user_id,
                "created_at": {
                    "$gte": datetime(current_year, 1, 1),
                    "$lt": datetime(current_year + 1, 1, 1)
                }
            }},
            {
                "$group": {
                    "_id": {"$month": "$created_at"},
                    "count": {"$sum": 1},
                    "amount": {"$sum": "$amount"}
                }
            },
            {"$sort": {"_id": 1}}
        ]
        
        monthly_stats = await db["payments"].aggregate(monthly_pipeline).to_list(length=12)
        
        # Get service type breakdown
        service_pipeline = [
            {"$match": {"user_id": user_id}},
            {
                "$group": {
                    "_id": "$service_type",
                    "count": {"$sum": 1},
                    "amount": {"$sum": "$amount"},
                    "successful": {
                        "$sum": {"$cond": [{"$eq": ["$status", "success"]}, 1, 0]}
                    }
                }
            }
        ]
        
        service_stats = await db["payments"].aggregate(service_pipeline).to_list(length=None)
        
        # Prepare response
        result = {
            "total_payments": stats[0]["total_payments"] if stats else 0,
            "total_amount": stats[0]["total_amount"] if stats else 0,
            "successful_payments": stats[0]["successful_payments"] if stats else 0,
            "successful_amount": stats[0]["successful_amount"] if stats else 0,
            "failed_payments": stats[0]["failed_payments"] if stats else 0,
            "pending_payments": stats[0]["pending_payments"] if stats else 0,
            "this_month_amount": 0,
            "this_year_amount": stats[0]["successful_amount"] if stats else 0,
            "by_service_type": {
                item["_id"]: {
                    "count": item["count"],
                    "amount": item["amount"],
                    "successful": item["successful"]
                } for item in service_stats
            },
            "by_month": [
                {
                    "month": item["_id"],
                    "count": item["count"],
                    "amount": item["amount"]
                } for item in monthly_stats
            ]
        }
        
        # Calculate this month amount
        current_month = datetime.now().month
        for month_data in result["by_month"]:
            if month_data["month"] == current_month:
                result["this_month_amount"] = month_data["amount"]
                break
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=result
        )
        
    except Exception as e:
        print(f"Error fetching payment statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch payment statistics"
        )

async def verify_razorpay_payment(
    razorpay_order_id: str,
    razorpay_payment_id: str,
    razorpay_signature: str
) -> bool:
    """Verify Razorpay payment signature"""
    try:
        # Get secret from environment
        razorpay_secret = os.getenv("RAZORPAY_KEY_SECRET")
        if not razorpay_secret:
            print("Razorpay secret not configured")
            return False
        
        # Create signature string
        payload = f"{razorpay_order_id}|{razorpay_payment_id}"
        
        # Calculate expected signature
        expected_signature = hmac.new(
            razorpay_secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # Compare signatures
        return hmac.compare_digest(expected_signature, razorpay_signature)
        
    except Exception as e:
        print(f"Error verifying Razorpay payment: {e}")
        return False
