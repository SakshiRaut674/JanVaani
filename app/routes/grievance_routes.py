# app/routes/grievance_routes.py
from fastapi import APIRouter, Depends, UploadFile, File, Query
from app.controllers.grievanceController import (
    create_grievance,
    get_user_grievances,
    get_grievance_by_id,
    update_grievance,
    upload_grievance_attachment,
    delete_grievance,
    get_grievance_categories,
    track_grievance_public
)
from app.models.grievance_model import (
    GrievanceCreateModel,
    GrievanceUpdateModel,
    GrievanceStatus,
    GrievanceCategory
)
from app.middlewares.authMiddleware import get_current_user
from typing import Optional

router = APIRouter(tags=["Grievances"])

# Public routes
@router.get("/categories")
async def get_categories():
    """Get all available grievance categories"""
    return await get_grievance_categories()

@router.get("/track/{grievance_id}")
async def track_grievance_status(grievance_id: str):
    """Public endpoint to track grievance status"""
    return await track_grievance_public(grievance_id)

# Protected routes (require authentication)
@router.post("/create")
async def create_new_grievance(
    grievance_data: GrievanceCreateModel,
    current_user: dict = Depends(get_current_user)
):
    """Create a new grievance"""
    return await create_grievance(grievance_data, current_user)

@router.get("/my-grievances")
async def get_my_grievances(
    status: Optional[GrievanceStatus] = Query(None),
    category: Optional[GrievanceCategory] = Query(None),
    limit: int = Query(10, ge=1, le=100),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user)
):
    """Get user's grievances with optional filters"""
    return await get_user_grievances(status, category, limit, skip, current_user)

@router.get("/{grievance_id}")
async def get_grievance_details(
    grievance_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get specific grievance details"""
    return await get_grievance_by_id(grievance_id, current_user)

@router.put("/{grievance_id}")
async def update_existing_grievance(
    grievance_id: str,
    grievance_data: GrievanceUpdateModel,
    current_user: dict = Depends(get_current_user)
):
    """Update an existing grievance"""
    return await update_grievance(grievance_id, grievance_data, current_user)

@router.post("/{grievance_id}/upload-attachment")
async def upload_attachment(
    grievance_id: str,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Upload attachment for a grievance"""
    return await upload_grievance_attachment(grievance_id, file, current_user)

@router.delete("/{grievance_id}")
async def delete_existing_grievance(
    grievance_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete a grievance (only if status is SUBMITTED)"""
    return await delete_grievance(grievance_id, current_user)