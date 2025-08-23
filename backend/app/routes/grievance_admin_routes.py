# app/routes/grievance_admin_routes.py
from fastapi import APIRouter, Query
from app.controllers.grievanceAdminController import (
    get_all_grievances,
    update_grievance_status,
    assign_grievance,
    get_grievance_stats,
    search_grievances,
    get_overdue_grievances
)
from app.models.grievance_model import (
    GrievanceStatus,
    GrievanceCategory,
    GrievancePriority
)
from typing import Optional

router = APIRouter(tags=["Grievances Admin - AI Agent Tools"])

@router.get("/admin/all")
async def get_all_grievances_endpoint(
    status: Optional[GrievanceStatus] = Query(None),
    category: Optional[GrievanceCategory] = Query(None),
    priority: Optional[GrievancePriority] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0)
):
    """Get all grievances with filters - Used by AI Agent"""
    return await get_all_grievances(status, category, priority, limit, skip)

@router.put("/admin/{grievance_id}/status")
async def update_grievance_status_endpoint(
    grievance_id: str,
    status: GrievanceStatus,
    admin_notes: Optional[str] = Query(None),
    estimated_resolution_date: Optional[str] = Query(None)
):
    """Update grievance status - Used by AI Agent"""
    return await update_grievance_status(grievance_id, status, admin_notes, estimated_resolution_date)

@router.put("/admin/{grievance_id}/assign")
async def assign_grievance_endpoint(
    grievance_id: str,
    assigned_to: str = Query(...)
):
    """Assign grievance to an officer - Used by AI Agent"""
    return await assign_grievance(grievance_id, assigned_to)

@router.get("/admin/stats")
async def get_grievance_stats_endpoint():
    """Get grievance statistics - Used by AI Agent"""
    return await get_grievance_stats()

@router.get("/admin/search")
async def search_grievances_endpoint(
    q: str = Query(..., min_length=2),
    limit: int = Query(20, ge=1, le=100)
):
    """Search grievances - Used by AI Agent"""
    return await search_grievances(q, limit)

@router.get("/admin/overdue")
async def get_overdue_grievances_endpoint():
    """Get overdue grievances - Used by AI Agent"""
    return await get_overdue_grievances()