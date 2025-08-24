# app/routes/grievance_admin_routes.py
from fastapi import APIRouter, Query, HTTPException
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
from app.database.database import get_db
from typing import Optional

router = APIRouter(tags=["Grievances Admin - AI Agent Tools"])

@router.get("/admin/grievances/categories")
async def get_grievance_categories():
    """Get all available grievance categories"""
    categories = [
        {"id": cat.value, "name": cat.value.replace("_", " ").title(), "value": cat.value}
        for cat in GrievanceCategory
    ]
    return {"categories": categories}

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

@router.get("/admin/map-data")
async def get_grievances_map_data():
    """Get grievances with location data for map visualization"""
    try:
        db = get_db()
        
        # Get grievances with location data
        cursor = db["grievances"].find(
            {"$or": [
                {"ward_number": {"$exists": True, "$ne": None}},
                {"address": {"$exists": True, "$ne": None}},
                {"location": {"$exists": True, "$ne": None}}
            ]},
            {
                "_id": 1,
                "grievance_id": 1,
                "title": 1,
                "category": 1,
                "status": 1,
                "priority": 1,
                "location": 1,
                "address": 1,
                "ward_number": 1,
                "created_at": 1,
                "user_mobile": 1
            }
        ).limit(100)
        
        grievances = []
        async for doc in cursor:
            # Convert MongoDB document to dict
            grievance = {
                "id": str(doc["_id"]),
                "grievance_id": doc.get("grievance_id"),
                "title": doc.get("title"),
                "category": doc.get("category"),
                "status": doc.get("status"),
                "priority": doc.get("priority"),
                "location": doc.get("location"),
                "address": doc.get("address"),
                "ward_number": doc.get("ward_number"),
                "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else None,
                "user_mobile": doc.get("user_mobile")
            }
            
            # Add mock coordinates based on ward number or location
            # In a real implementation, you would geocode the addresses
            coordinates = get_mock_coordinates(grievance.get("ward_number"), grievance.get("location"))
            if coordinates:
                grievance["coordinates"] = coordinates
                
            grievances.append(grievance)
        
        return {
            "success": True,
            "grievances": grievances,
            "total": len(grievances)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching map data: {str(e)}")

def get_mock_coordinates(ward_number, location):
    """Generate mock coordinates based on ward number or location - Bhopal area"""
    base_lat = 23.2599  # Bhopal latitude
    base_lng = 77.4126  # Bhopal longitude
    
    if ward_number:
        try:
            ward_num = int(ward_number)
            # Distribute wards around Bhopal
            lat_offset = (ward_num % 10) * 0.01 - 0.05  # -0.05 to 0.04
            lng_offset = (ward_num % 8) * 0.01 - 0.04   # -0.04 to 0.03
            return [base_lat + lat_offset, base_lng + lng_offset]
        except:
            pass
    
    if location:
        # Simple hash-based coordinate generation
        location_hash = sum(ord(c) for c in location.lower())
        lat_offset = (location_hash % 100) * 0.001 - 0.05
        lng_offset = (location_hash % 80) * 0.001 - 0.04
        return [base_lat + lat_offset, base_lng + lng_offset]
    
    return None