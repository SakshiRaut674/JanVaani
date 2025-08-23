# app/utils/grievance_utils.py
import uuid
import random
from datetime import datetime
from app.models.grievance_model import GrievanceCategory
from typing import Dict

def generate_grievance_id(category: GrievanceCategory) -> str:
    """Generate a unique grievance ID based on category"""
    category_codes = {
        GrievanceCategory.GARBAGE: "GRB",
        GrievanceCategory.WATER_SUPPLY: "WTR",
        GrievanceCategory.DRAINAGE: "DRN",
        GrievanceCategory.STREET_LIGHTS: "STL",
        GrievanceCategory.ROADS: "RDS",
        GrievanceCategory.SEWAGE: "SWG",
        GrievanceCategory.NOISE_POLLUTION: "NSE",
        GrievanceCategory.ILLEGAL_CONSTRUCTION: "ILC",
        GrievanceCategory.PROPERTY_TAX: "PTX",
        GrievanceCategory.OTHER: "OTH"
    }
    
    code = category_codes.get(category, "GEN")
    timestamp = datetime.now().strftime("%y%m%d")
    random_num = random.randint(1000, 9999)
    
    return f"{code}{timestamp}{random_num}"

async def send_grievance_notification(grievance_id: str, action: str):
    """Send notification for grievance actions (placeholder for future implementation)"""
    # This will be implemented later with email/SMS service
    print(f"Notification: Grievance {grievance_id} has been {action}")
    pass

def get_category_description(category: GrievanceCategory) -> str:
    """Get human-readable description for grievance category"""
    descriptions = {
        GrievanceCategory.GARBAGE: "Garbage collection, waste management issues",
        GrievanceCategory.WATER_SUPPLY: "Water supply, quality, pressure issues",
        GrievanceCategory.DRAINAGE: "Drainage blockage, waterlogging issues",
        GrievanceCategory.STREET_LIGHTS: "Street lighting, electrical issues",
        GrievanceCategory.ROADS: "Road conditions, potholes, maintenance",
        GrievanceCategory.SEWAGE: "Sewage overflow, blockage, maintenance",
        GrievanceCategory.NOISE_POLLUTION: "Excessive noise complaints",
        GrievanceCategory.ILLEGAL_CONSTRUCTION: "Unauthorized construction complaints",
        GrievanceCategory.PROPERTY_TAX: "Property tax related issues",
        GrievanceCategory.OTHER: "Other municipal service issues"
    }
    
    return descriptions.get(category, "General municipal service issue")

def get_priority_sla_hours(priority) -> int:
    """Get SLA hours based on priority"""
    sla_mapping = {
        "urgent": 4,      # 4 hours
        "high": 24,       # 1 day
        "medium": 72,     # 3 days
        "low": 168        # 7 days
    }
    return sla_mapping.get(priority.lower(), 72)

def validate_mobile_number(mobile: str) -> bool:
    """Validate Indian mobile number format"""
    import re
    pattern = r'^(\+91)?[6789]\d{9}$'
    return bool(re.match(pattern, mobile))

def format_mobile_number(mobile: str) -> str:
    """Format mobile number to standard format"""
    # Remove spaces and special characters
    mobile = re.sub(r'[^\d+]', '', mobile)
    
    # Add +91 if not present
    if not mobile.startswith('+91') and len(mobile) == 10:
        mobile = f'+91{mobile}'
    
    return mobile