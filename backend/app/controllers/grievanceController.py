# app/controllers/grievanceController.py
from fastapi import HTTPException, status, Depends, UploadFile, File, Form, Query
from fastapi.responses import JSONResponse
from app.models.grievance_model import (
    GrievanceCreateModel, 
    GrievanceUpdateModel, 
    GrievanceStatusUpdateModel,
    GrievanceStatus,
    GrievanceCategory,
    GrievancePriority
)
from app.middlewares.authMiddleware import get_current_user
from typing import Optional, List, Dict
from pymongo import ReturnDocument
from bson import ObjectId
from app.database.database import get_db
from datetime import datetime
import uuid
import cloudinary.uploader
from app.utils.grievance_utils import generate_grievance_id, send_grievance_notification

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

async def create_grievance(
    grievance_data: GrievanceCreateModel,
    current_user: dict = Depends(get_current_user)
):
    """Create a new grievance"""
    db = get_db()
    user_id = str(current_user["_id"])
    
    # Generate unique grievance ID
    grievance_id = generate_grievance_id(grievance_data.category)
    
    # Create grievance document
    grievance_doc = {
        "grievance_id": grievance_id,
        "title": grievance_data.title,
        "description": grievance_data.description,
        "category": grievance_data.category,
        "status": GrievanceStatus.SUBMITTED,
        "priority": grievance_data.priority,
        "location": grievance_data.location,
        "address": grievance_data.address,
        "landmark": grievance_data.landmark,
        "ward_number": grievance_data.ward_number,
        "pin_code": grievance_data.pin_code,
        "contact_person": grievance_data.contact_person,
        "alternate_mobile": grievance_data.alternate_mobile,
        "user_id": user_id,
        "user_mobile": current_user["mobile"],
        "anonymous": grievance_data.anonymous,
        "attachments": [],
        "admin_notes": None,
        "assigned_to": None,
        "estimated_resolution_date": None,
        "actual_resolution_date": None,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "status_history": [{
            "status": GrievanceStatus.SUBMITTED,
            "timestamp": datetime.utcnow(),
            "notes": "Grievance submitted by user",
            "updated_by": "system"
        }]
    }
    
    try:
        # Insert grievance
        result = await db["grievances"].insert_one(grievance_doc)
        
        # Get the inserted grievance
        inserted_grievance = await db["grievances"].find_one({"_id": result.inserted_id})
        serialized_grievance = serialize_document(inserted_grievance)
        
        # Send notification (async task)
        # await send_grievance_notification(grievance_id, "created")
        
        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={
                "message": "Grievance created successfully",
                "grievance": serialized_grievance
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create grievance: {str(e)}"
        )

async def get_user_grievances(
    status_filter: Optional[GrievanceStatus] = Query(None),
    category_filter: Optional[GrievanceCategory] = Query(None),
    limit: int = Query(10, ge=1, le=100),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user)
):
    """Get user's grievances with filters"""
    db = get_db()
    user_id = str(current_user["_id"])
    
    # Build query
    query = {"user_id": user_id}
    if status_filter:
        query["status"] = status_filter
    if category_filter:
        query["category"] = category_filter
    
    try:
        # Get total count
        total_count = await db["grievances"].count_documents(query)
        
        # Get grievances with pagination
        cursor = db["grievances"].find(query).sort("created_at", -1).skip(skip).limit(limit)
        grievances = await cursor.to_list(length=limit)
        
        # Serialize documents
        serialized_grievances = [serialize_document(grievance) for grievance in grievances]
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "message": "Grievances retrieved successfully",
                "grievances": serialized_grievances,
                "total_count": total_count,
                "page": skip // limit + 1,
                "per_page": limit
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve grievances: {str(e)}"
        )

async def get_grievance_by_id(
    grievance_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a specific grievance by ID"""
    db = get_db()
    user_id = str(current_user["_id"])
    
    try:
        grievance = await db["grievances"].find_one({
            "grievance_id": grievance_id,
            "user_id": user_id
        })
        
        if not grievance:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Grievance not found"
            )
        
        serialized_grievance = serialize_document(grievance)
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "message": "Grievance retrieved successfully",
                "grievance": serialized_grievance
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve grievance: {str(e)}"
        )

async def update_grievance(
    grievance_id: str,
    grievance_data: GrievanceUpdateModel,
    current_user: dict = Depends(get_current_user)
):
    """Update a grievance (only if status is SUBMITTED or UNDER_REVIEW)"""
    db = get_db()
    user_id = str(current_user["_id"])
    
    # Create update dictionary
    update_data = {k: v for k, v in grievance_data.dict(exclude_unset=True).items() if v is not None}
    
    if not update_data:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"message": "No fields to update"}
        )
    
    # Add updated_at timestamp
    update_data["updated_at"] = datetime.utcnow()
    
    try:
        # Check if grievance exists and can be updated
        existing_grievance = await db["grievances"].find_one({
            "grievance_id": grievance_id,
            "user_id": user_id
        })
        
        if not existing_grievance:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Grievance not found"
            )
        
        # Check if grievance can be updated
        if existing_grievance["status"] not in [GrievanceStatus.SUBMITTED, GrievanceStatus.UNDER_REVIEW]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Grievance cannot be updated in current status"
            )
        
        # Update grievance
        updated_grievance = await db["grievances"].find_one_and_update(
            {"grievance_id": grievance_id, "user_id": user_id},
            {"$set": update_data},
            return_document=ReturnDocument.AFTER
        )
        
        serialized_grievance = serialize_document(updated_grievance)
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "message": "Grievance updated successfully",
                "grievance": serialized_grievance
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update grievance: {str(e)}"
        )

async def upload_grievance_attachment(
    grievance_id: str,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Upload attachment for a grievance"""
    db = get_db()
    user_id = str(current_user["_id"])
    
    try:
        # Check if grievance exists
        grievance = await db["grievances"].find_one({
            "grievance_id": grievance_id,
            "user_id": user_id
        })
        
        if not grievance:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Grievance not found"
            )
        
        # Upload to Cloudinary
        upload_result = cloudinary.uploader.upload(
            file.file, 
            resource_type="auto",
            folder=f"grievances/{grievance_id}"
        )
        
        attachment_url = upload_result["secure_url"]
        
        # Add attachment to grievance
        await db["grievances"].update_one(
            {"grievance_id": grievance_id, "user_id": user_id},
            {
                "$push": {"attachments": attachment_url},
                "$set": {"updated_at": datetime.utcnow()}
            }
        )
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "message": "Attachment uploaded successfully",
                "attachment_url": attachment_url
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload attachment: {str(e)}"
        )

async def delete_grievance(
    grievance_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete a grievance (only if status is SUBMITTED)"""
    db = get_db()
    user_id = str(current_user["_id"])
    
    try:
        # Check if grievance exists and can be deleted
        grievance = await db["grievances"].find_one({
            "grievance_id": grievance_id,
            "user_id": user_id
        })
        
        if not grievance:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Grievance not found"
            )
        
        if grievance["status"] != GrievanceStatus.SUBMITTED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only submitted grievances can be deleted"
            )
        
        # Delete grievance
        await db["grievances"].delete_one({
            "grievance_id": grievance_id,
            "user_id": user_id
        })
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"message": "Grievance deleted successfully"}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete grievance: {str(e)}"
        )

async def get_grievance_categories():
    """Get all available grievance categories"""
    categories = [
        {"value": category.value, "label": category.value.replace("_", " ").title()}
        for category in GrievanceCategory
    ]
    
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "message": "Categories retrieved successfully",
            "categories": categories
        }
    )

async def track_grievance_public(grievance_id: str):
    """Public endpoint to track grievance status by ID"""
    db = get_db()
    
    try:
        grievance = await db["grievances"].find_one(
            {"grievance_id": grievance_id},
            {
                "grievance_id": 1,
                "title": 1,
                "category": 1,
                "status": 1,
                "priority": 1,
                "created_at": 1,
                "updated_at": 1,
                "status_history": 1,
                "estimated_resolution_date": 1
            }
        )
        
        if not grievance:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Grievance not found"
            )
        
        serialized_grievance = serialize_document(grievance)
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "message": "Grievance status retrieved successfully",
                "grievance": serialized_grievance
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to track grievance: {str(e)}"
        )