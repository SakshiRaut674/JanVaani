from fastapi import APIRouter, Body
from app.controllers.userController import ProfileUpdateModel
from app.database.database import get_db
from fastapi.responses import JSONResponse
from fastapi import status
from bson import ObjectId
from datetime import datetime
from typing import Dict, Any

router = APIRouter(tags=["Debug"])

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

@router.put("/debug-update-profile")
async def debug_update_profile(
    profile_data: Dict[str, Any] = Body(...),
    mobile: str = "8349896755"  # Default mobile for testing
):
    try:
        db = get_db()
        
        # First, create a test user if they don't exist
        user = await db["users"].find_one({"mobile": mobile})
        if not user:
            new_user = {
                "mobile": mobile,
                "verified": True,
                "created_at": datetime.utcnow(),
            }
            insert_result = await db["users"].insert_one(new_user)
            user_id = insert_result.inserted_id
        else:
            user_id = user["_id"]
        
        # Validate and prepare update data
        profile_model = ProfileUpdateModel(**profile_data)
        update_data = {k: v for k, v in profile_model.model_dump(exclude_unset=True).items() if v is not None}
        
        if not update_data:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"message": "No fields to update"}
            )
        
        # Update user in database
        from pymongo import ReturnDocument
        updated_user = await db["users"].find_one_and_update(
            {"_id": user_id},
            {"$set": update_data},
            return_document=ReturnDocument.AFTER
        )
        
        if not updated_user:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"message": "User not found after update"}
            )
        
        # Convert document to JSON serializable format
        serialized_user = serialize_document(updated_user)
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "message": "Profile updated successfully",
                "user": serialized_user
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": f"Failed to update profile: {str(e)}"}
        )
