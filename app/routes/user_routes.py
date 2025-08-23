from fastapi import APIRouter, Depends, Body
from app.controllers.userController import update_profile, send_user_details, upload_document_record, ProfileUpdateModel
from app.middlewares.authMiddleware import get_current_user
from typing import Dict, Any

router = APIRouter(tags=["User"])

# Update profile endpoint
@router.put("/update-profile")
async def update_user_profile(
    profile_data: Dict[str, Any] = Body(...),
    current_user: dict = Depends(get_current_user)
):
    # Convert dict to ProfileUpdateModel manually to handle validation
    try:
        profile_model = ProfileUpdateModel(**profile_data)
        return await update_profile(profile_model, current_user)
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"Invalid profile data: {str(e)}")

# Get current user endpoint
@router.get("/me")
async def get_current_user_details(current_user: dict = Depends(get_current_user)):
    return await send_user_details(current_user)

# Document upload endpoint
@router.post("/documents/upload-document")
async def upload_user_document(current_user: dict = Depends(get_current_user)):
    return await upload_document_record(current_user)