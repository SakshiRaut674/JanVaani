from fastapi import APIRouter, Depends
from app.controllers.userController import update_profile, send_user_details,upload_document_record
from app.middlewares.authMiddleware import get_current_user


router = APIRouter(tags=["User"])

# ✅ Inject authenticated user
router.put("/update-profile")(update_profile)
router.get("/me", dependencies=[Depends(get_current_user)])(send_user_details)
router.get("/documents/upload-document")(upload_document_record)  # Alias for backward compatibility