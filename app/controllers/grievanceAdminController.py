# app/controllers/grievanceAdminController.py
from fastapi import HTTPException, status, Query
from fastapi.responses import JSONResponse
from app.models.grievance_model import (
    GrievanceStatus,
    GrievanceCategory,
    GrievancePriority,
    GrievanceStatusUpdateModel
)
from typing import Optional, List, Dict
from pymongo import ReturnDocument
from bson import ObjectId
from app.database.database import get_db
from datetime import datetime, timedelta
import asyncio

# Helper function to serialize MongoDB documents
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

async def get_all_grievances(
    status_filter: Optional[GrievanceStatus] = None,
    category_filter: Optional[GrievanceCategory] = None,
    priority_filter: Optional[GrievancePriority] = None,
    limit: int = 50,
    skip: int = 0
):
    """Get all grievances with filters - Used by AI Agent"""
    db = get_db()
    
    # Build query
    query = {}
    if status_filter:
        query["status"] = status_filter
    if category_filter:
        query["category"] = category_filter
    if priority_filter:
        query["priority"] = priority_filter
    
    try:
        # Get total count
        total_count = await db["grievances"].count_documents(query)
        
        # Get grievances with pagination
        cursor = db["grievances"].find(query).sort("created_at", -1).skip(skip).limit(limit)
        grievances = await cursor.to_list(length=limit)
        
        # Serialize documents
        serialized_grievances = [serialize_document(grievance) for grievance in grievances]
        
        return {
            "success": True,
            "grievances": serialized_grievances,
            "total_count": total_count,
            "page": skip // limit + 1,
            "per_page": limit
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to retrieve grievances: {str(e)}"
        }

async def update_grievance_status(
    grievance_id: str,
    status: GrievanceStatus,
    admin_notes: Optional[str] = None,
    estimated_resolution_date: Optional[str] = None
):
    """Update grievance status - Used by AI Agent"""
    db = get_db()
    
    try:
        # Check if grievance exists
        existing_grievance = await db["grievances"].find_one({"grievance_id": grievance_id})
        
        if not existing_grievance:
            return {
                "success": False,
                "error": "Grievance not found"
            }
        
        # Prepare update data
        update_data = {
            "status": status,
            "updated_at": datetime.utcnow()
        }
        
        if admin_notes:
            update_data["admin_notes"] = admin_notes
            
        if estimated_resolution_date:
            try:
                est_date = datetime.fromisoformat(estimated_resolution_date.replace('Z', '+00:00'))
                update_data["estimated_resolution_date"] = est_date
            except:
                pass
        
        if status == GrievanceStatus.RESOLVED:
            update_data["actual_resolution_date"] = datetime.utcnow()
        
        # Add to status history
        status_entry = {
            "status": status,
            "timestamp": datetime.utcnow(),
            "notes": admin_notes or f"Status updated to {status}",
            "updated_by": "ai_agent"
        }
        
        # Update grievance
        updated_grievance = await db["grievances"].find_one_and_update(
            {"grievance_id": grievance_id},
            {
                "$set": update_data,
                "$push": {"status_history": status_entry}
            },
            return_document=ReturnDocument.AFTER
        )
        
        serialized_grievance = serialize_document(updated_grievance)
        
        return {
            "success": True,
            "message": "Grievance status updated successfully",
            "grievance": serialized_grievance
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to update grievance status: {str(e)}"
        }

async def assign_grievance(
    grievance_id: str,
    assigned_to: str
):
    """Assign grievance to an officer - Used by AI Agent"""
    db = get_db()
    
    try:
        # Check if grievance exists
        existing_grievance = await db["grievances"].find_one({"grievance_id": grievance_id})
        
        if not existing_grievance:
            return {
                "success": False,
                "error": "Grievance not found"
            }
        
        # Update assignment
        update_data = {
            "assigned_to": assigned_to,
            "updated_at": datetime.utcnow()
        }
        
        # Add to status history
        status_entry = {
            "status": existing_grievance["status"],
            "timestamp": datetime.utcnow(),
            "notes": f"Assigned to {assigned_to}",
            "updated_by": "ai_agent"
        }
        
        # Update grievance
        updated_grievance = await db["grievances"].find_one_and_update(
            {"grievance_id": grievance_id},
            {
                "$set": update_data,
                "$push": {"status_history": status_entry}
            },
            return_document=ReturnDocument.AFTER
        )
        
        serialized_grievance = serialize_document(updated_grievance)
        
        return {
            "success": True,
            "message": "Grievance assigned successfully",
            "grievance": serialized_grievance
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to assign grievance: {str(e)}"
        }

async def get_grievance_stats():
    """Get grievance statistics - Used by AI Agent"""
    db = get_db()
    
    try:
        # Aggregate statistics
        pipeline = [
            {
                "$group": {
                    "_id": {
                        "status": "$status",
                        "category": "$category"
                    },
                    "count": {"$sum": 1}
                }
            },
            {
                "$group": {
                    "_id": None,
                    "stats": {
                        "$push": {
                            "status": "$_id.status",
                            "category": "$_id.category",
                            "count": "$count"
                        }
                    }
                }
            }
        ]
        
        result = await db["grievances"].aggregate(pipeline).to_list(length=1)
        
        if result:
            stats = result[0]["stats"]
        else:
            stats = []
        
        # Calculate totals
        total_grievances = await db["grievances"].count_documents({})
        pending_grievances = await db["grievances"].count_documents({
            "status": {"$in": [GrievanceStatus.SUBMITTED, GrievanceStatus.UNDER_REVIEW, GrievanceStatus.IN_PROGRESS]}
        })
        resolved_grievances = await db["grievances"].count_documents({"status": GrievanceStatus.RESOLVED})
        
        # Get recent grievances (last 7 days)
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_grievances = await db["grievances"].count_documents({"created_at": {"$gte": week_ago}})
        
        return {
            "success": True,
            "stats": {
                "total_grievances": total_grievances,
                "pending_grievances": pending_grievances,
                "resolved_grievances": resolved_grievances,
                "recent_grievances": recent_grievances,
                "detailed_stats": stats
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to get grievance statistics: {str(e)}"
        }

async def search_grievances(
    search_term: str,
    limit: int = 20
):
    """Search grievances by title, description, or grievance ID - Used by AI Agent"""
    db = get_db()
    
    try:
        # Create text search query
        query = {
            "$or": [
                {"title": {"$regex": search_term, "$options": "i"}},
                {"description": {"$regex": search_term, "$options": "i"}},
                {"grievance_id": {"$regex": search_term, "$options": "i"}},
                {"location": {"$regex": search_term, "$options": "i"}}
            ]
        }
        
        cursor = db["grievances"].find(query).sort("created_at", -1).limit(limit)
        grievances = await cursor.to_list(length=limit)
        
        # Serialize documents
        serialized_grievances = [serialize_document(grievance) for grievance in grievances]
        
        return {
            "success": True,
            "grievances": serialized_grievances,
            "count": len(serialized_grievances)
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to search grievances: {str(e)}"
        }

async def get_overdue_grievances():
    """Get overdue grievances based on SLA - Used by AI Agent"""
    db = get_db()
    
    try:
        # Define SLA hours for each priority
        sla_hours = {
            GrievancePriority.URGENT: 4,
            GrievancePriority.HIGH: 24,
            GrievancePriority.MEDIUM: 72,
            GrievancePriority.LOW: 168
        }
        
        overdue_grievances = []
        
        for priority, hours in sla_hours.items():
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            
            query = {
                "priority": priority,
                "status": {"$in": [GrievanceStatus.SUBMITTED, GrievanceStatus.UNDER_REVIEW, GrievanceStatus.IN_PROGRESS]},
                "created_at": {"$lt": cutoff_time}
            }
            
            cursor = db["grievances"].find(query)
            grievances = await cursor.to_list(length=None)
            overdue_grievances.extend(grievances)
        
        # Serialize documents
        serialized_grievances = [serialize_document(grievance) for grievance in overdue_grievances]
        
        return {
            "success": True,
            "overdue_grievances": serialized_grievances,
            "count": len(serialized_grievances)
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to get overdue grievances: {str(e)}"
        }