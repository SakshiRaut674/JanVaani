# app/controllers/billController.py
from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
from app.database.database import get_db
from app.models.bill_model import (
    BillCreateModel, BillUpdateModel, BillResponseModel, BillSearchModel,
    BillSummaryModel, BillListResponseModel, BillStatus, BillType, BillPriority
)
from bson import ObjectId
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import uuid

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

async def create_bill(
    bill_data: BillCreateModel,
    current_user: dict
) -> JSONResponse:
    """Create a new bill"""
    try:
        db = get_db()
        user_id = str(current_user["_id"])
        
        # Generate unique bill ID
        bill_id = f"{bill_data.bill_type.value.upper()}{datetime.now().strftime('%Y%m%d')}{str(uuid.uuid4())[:8].upper()}"
        
        # Calculate priority based on due date
        days_to_due = (bill_data.due_date - datetime.now()).days
        if days_to_due < 0:
            priority = BillPriority.URGENT
            status = BillStatus.OVERDUE
        elif days_to_due <= 7:
            priority = BillPriority.HIGH
            status = BillStatus.PENDING
        elif days_to_due <= 30:
            priority = BillPriority.MEDIUM
            status = BillStatus.PENDING
        else:
            priority = BillPriority.LOW
            status = BillStatus.PENDING
        
        # Calculate balance amount
        balance_amount = bill_data.amount + (bill_data.late_fee or 0) + (bill_data.penalty or 0) - (bill_data.discount or 0)
        
        # Prepare bill document
        bill_doc = {
            "bill_id": bill_id,
            "user_id": user_id,
            "bill_type": bill_data.bill_type.value,
            "amount": bill_data.amount,
            "amount_paid": 0.0,
            "balance_amount": balance_amount,
            "status": status.value,
            "priority": priority.value,
            "due_date": bill_data.due_date,
            "description": bill_data.description,
            "year": bill_data.year,
            "period": bill_data.period,
            "property_id": bill_data.property_id,
            "meter_reading": bill_data.meter_reading,
            "previous_reading": bill_data.previous_reading,
            "consumption": bill_data.consumption,
            "late_fee": bill_data.late_fee or 0.0,
            "penalty": bill_data.penalty or 0.0,
            "discount": bill_data.discount or 0.0,
            "payment_id": None,
            "payment_history": [],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "paid_at": None,
            "metadata": bill_data.metadata or {}
        }
        
        # Insert bill record
        result = await db["bills"].insert_one(bill_doc)
        
        # Fetch the created bill
        bill = await db["bills"].find_one({"_id": result.inserted_id})
        
        serialized_bill = serialize_document(bill)
        
        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={
                "message": "Bill created successfully",
                "bill": serialized_bill
            }
        )
        
    except Exception as e:
        print(f"Error creating bill: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create bill"
        )

async def get_user_bills(
    current_user: dict,
    page: int = 1,
    limit: int = 20,
    search: Optional[BillSearchModel] = None
) -> JSONResponse:
    """Get user's bills with optional filters"""
    try:
        db = get_db()
        user_id = str(current_user["_id"])
        
        # Build query
        query = {"user_id": user_id}
        
        if search:
            if search.search_term:
                query["$or"] = [
                    {"bill_id": {"$regex": search.search_term, "$options": "i"}},
                    {"description": {"$regex": search.search_term, "$options": "i"}}
                ]
            
            if search.bill_type:
                query["bill_type"] = search.bill_type.value
            
            if search.status:
                query["status"] = search.status.value
            
            if search.priority:
                query["priority"] = search.priority.value
            
            if search.year:
                query["year"] = search.year
            
            if search.property_id:
                query["property_id"] = search.property_id
            
            if search.due_date_from or search.due_date_to:
                date_query = {}
                if search.due_date_from:
                    date_query["$gte"] = search.due_date_from
                if search.due_date_to:
                    date_query["$lte"] = search.due_date_to
                query["due_date"] = date_query
            
            if search.amount_min is not None or search.amount_max is not None:
                amount_query = {}
                if search.amount_min is not None:
                    amount_query["$gte"] = search.amount_min
                if search.amount_max is not None:
                    amount_query["$lte"] = search.amount_max
                query["balance_amount"] = amount_query
        
        # Calculate pagination
        skip = (page - 1) * limit
        
        # Get total count
        total_count = await db["bills"].count_documents(query)
        total_pages = (total_count + limit - 1) // limit
        
        # Get bills with pagination
        bills_cursor = db["bills"].find(query).sort("due_date", 1).skip(skip).limit(limit)
        bills = await bills_cursor.to_list(length=limit)
        
        # Get summary statistics
        summary = await get_bills_summary(user_id, db)
        
        serialized_bills = serialize_document(bills)
        serialized_summary = serialize_document(summary)
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "bills": serialized_bills,
                "summary": serialized_summary,
                "total_count": total_count,
                "page": page,
                "total_pages": total_pages
            }
        )
        
    except Exception as e:
        print(f"Error fetching bills: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch bills"
        )

async def get_bills_summary(user_id: str, db) -> dict:
    """Get bill summary statistics"""
    try:
        # Aggregation pipeline for summary
        pipeline = [
            {"$match": {"user_id": user_id}},
            {
                "$group": {
                    "_id": "$status",
                    "count": {"$sum": 1},
                    "amount": {"$sum": "$balance_amount"}
                }
            }
        ]
        
        status_stats = await db["bills"].aggregate(pipeline).to_list(length=None)
        
        # Initialize summary
        summary = {
            "total_pending": 0,
            "total_paid": 0,
            "total_overdue": 0,
            "total_bills": 0,
            "pending_bills": 0,
            "paid_bills": 0,
            "overdue_bills": 0,
            "by_type": {},
            "upcoming_due": [],
            "overdue_bills": []
        }
        
        # Process status statistics
        for stat in status_stats:
            summary["total_bills"] += stat["count"]
            
            if stat["_id"] == "pending":
                summary["total_pending"] = stat["amount"]
                summary["pending_bills"] = stat["count"]
            elif stat["_id"] == "paid":
                summary["total_paid"] = stat["amount"]
                summary["paid_bills"] = stat["count"]
            elif stat["_id"] == "overdue":
                summary["total_overdue"] = stat["amount"]
                summary["overdue_bills"] = stat["count"]
        
        # Get type breakdown
        type_pipeline = [
            {"$match": {"user_id": user_id}},
            {
                "$group": {
                    "_id": "$bill_type",
                    "count": {"$sum": 1},
                    "amount": {"$sum": "$balance_amount"},
                    "status_breakdown": {
                        "$push": "$status"
                    }
                }
            }
        ]
        
        type_stats = await db["bills"].aggregate(type_pipeline).to_list(length=None)
        
        for stat in type_stats:
            status_counts = {}
            for status in stat["status_breakdown"]:
                status_counts[status] = status_counts.get(status, 0) + 1
            
            summary["by_type"][stat["_id"]] = {
                "count": stat["count"],
                "amount": stat["amount"],
                "status_breakdown": status_counts
            }
        
        # Get upcoming due bills (next 30 days)
        upcoming_due_date = datetime.now() + timedelta(days=30)
        upcoming_bills = await db["bills"].find({
            "user_id": user_id,
            "status": {"$in": ["pending"]},
            "due_date": {"$lte": upcoming_due_date}
        }).sort("due_date", 1).limit(5).to_list(length=5)
        
        summary["upcoming_due"] = upcoming_bills
        
        # Get overdue bills
        overdue_bills = await db["bills"].find({
            "user_id": user_id,
            "status": "overdue"
        }).sort("due_date", 1).limit(5).to_list(length=5)
        
        summary["overdue_bills"] = overdue_bills
        
        return summary
        
    except Exception as e:
        print(f"Error calculating bills summary: {e}")
        return {
            "total_pending": 0,
            "total_paid": 0,
            "total_overdue": 0,
            "total_bills": 0,
            "pending_bills": 0,
            "paid_bills": 0,
            "overdue_bills": 0,
            "by_type": {},
            "upcoming_due": [],
            "overdue_bills": []
        }

async def get_bill_by_id(
    bill_id: str,
    current_user: dict
) -> JSONResponse:
    """Get bill details by ID"""
    try:
        db = get_db()
        user_id = str(current_user["_id"])
        
        bill = await db["bills"].find_one({
            "bill_id": bill_id,
            "user_id": user_id
        })
        
        if not bill:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bill not found"
            )
        
        serialized_bill = serialize_document(bill)
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"bill": serialized_bill}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error fetching bill: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch bill details"
        )

async def update_bill_status(
    bill_id: str,
    update_data: BillUpdateModel,
    current_user: dict
) -> JSONResponse:
    """Update bill details"""
    try:
        db = get_db()
        user_id = str(current_user["_id"])
        
        # Prepare update fields
        update_fields = {
            "updated_at": datetime.utcnow()
        }
        
        if update_data.amount is not None:
            update_fields["amount"] = update_data.amount
        
        if update_data.due_date:
            update_fields["due_date"] = update_data.due_date
        
        if update_data.status:
            update_fields["status"] = update_data.status.value
            if update_data.status == BillStatus.PAID and update_data.paid_at:
                update_fields["paid_at"] = update_data.paid_at
        
        if update_data.description:
            update_fields["description"] = update_data.description
        
        if update_data.late_fee is not None:
            update_fields["late_fee"] = update_data.late_fee
        
        if update_data.penalty is not None:
            update_fields["penalty"] = update_data.penalty
        
        if update_data.discount is not None:
            update_fields["discount"] = update_data.discount
        
        if update_data.payment_id:
            update_fields["payment_id"] = update_data.payment_id
        
        if update_data.metadata:
            update_fields["metadata"] = update_data.metadata
        
        # Recalculate balance amount if financial fields changed
        current_bill = await db["bills"].find_one({"bill_id": bill_id, "user_id": user_id})
        if current_bill:
            amount = update_fields.get("amount", current_bill["amount"])
            late_fee = update_fields.get("late_fee", current_bill.get("late_fee", 0))
            penalty = update_fields.get("penalty", current_bill.get("penalty", 0))
            discount = update_fields.get("discount", current_bill.get("discount", 0))
            amount_paid = current_bill.get("amount_paid", 0)
            
            update_fields["balance_amount"] = amount + late_fee + penalty - discount - amount_paid
        
        # Update bill record
        bill = await db["bills"].find_one_and_update(
            {
                "bill_id": bill_id,
                "user_id": user_id
            },
            {"$set": update_fields},
            return_document=True
        )
        
        if not bill:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bill not found"
            )
        
        serialized_bill = serialize_document(bill)
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "message": "Bill updated successfully",
                "bill": serialized_bill
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error updating bill: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update bill"
        )

async def create_sample_bills(
    current_user: dict
) -> JSONResponse:
    """Create sample bills for testing"""
    try:
        db = get_db()
        user_id = str(current_user["_id"])
        
        # Sample bills data
        sample_bills = [
            {
                "bill_type": BillType.PROPERTY_TAX,
                "amount": 12000,
                "due_date": datetime(2024, 12, 31),
                "description": "Annual Property Tax 2024",
                "year": "2024",
                "property_id": "PROP123456"
            },
            {
                "bill_type": BillType.WATER_BILL,
                "amount": 2500,
                "due_date": datetime(2024, 9, 15),
                "description": "Water Bill - August 2024",
                "year": "2024",
                "period": "August 2024",
                "meter_reading": 1250,
                "previous_reading": 1200,
                "consumption": 50
            },
            {
                "bill_type": BillType.GARBAGE_FEE,
                "amount": 1000,
                "due_date": datetime(2024, 10, 31),
                "description": "Garbage Collection Fee - October 2024",
                "year": "2024",
                "period": "October 2024"
            }
        ]
        
        created_bills = []
        
        for bill_data in sample_bills:
            bill_create = BillCreateModel(**bill_data)
            result = await create_bill(bill_create, current_user)
            created_bills.append(result)
        
        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={
                "message": f"Successfully created {len(sample_bills)} sample bills",
                "bills_created": len(sample_bills)
            }
        )
        
    except Exception as e:
        print(f"Error creating sample bills: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create sample bills"
        )

async def get_user_bills_count(current_user: dict) -> int:
    """Get the count of bills for a user"""
    try:
        db = await get_db()
        user_id = ObjectId(current_user["id"])
        
        count = await db.bills.count_documents({"user_id": user_id})
        return count
        
    except Exception as e:
        print(f"Error getting user bills count: {e}")
        return 0

async def create_bill_for_user(bill_data: BillCreateModel, user_data: dict):
    """Create a bill for a specific user - used by default bill generator"""
    try:
        # Use the existing create_bill function
        result = await create_bill(bill_data, user_data)
        
        # Parse the result if it's a JSONResponse
        if hasattr(result, 'body'):
            import json
            response_data = json.loads(result.body.decode())
            return response_data.get('bill')
        else:
            return result
        
    except Exception as e:
        print(f"Error creating bill for user: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create bill: {str(e)}")
