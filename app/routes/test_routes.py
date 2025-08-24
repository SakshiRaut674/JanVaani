from fastapi import APIRouter
from app.controllers.authcontroller import verify_otp
import json

router = APIRouter()

@router.post("/auth/test-verify-otp")
async def test_verify_otp_bypass():
    """Test endpoint to bypass OTP verification for debugging"""
    
    # Use the real mobile number and simulate successful OTP verification
    mobile = "+918349896755"
    
    try:
        # This will create/fetch the user and return the token + user data
        # Since the user already exists, it should return complete profile
        result = await verify_otp(mobile, "000000")  # Use any OTP - we'll bypass validation
        
        return {
            "success": True,
            "message": "Test OTP verification successful",
            "token": result["token"],
            "user": result["user"]
        }
        
    except Exception as e:
        # If OTP validation fails, let's manually create the response
        from app.database.database import get_users_collection
        import jwt
        import os
        from datetime import datetime, timedelta
        
        users_collection = get_users_collection()
        user = await users_collection.find_one({"mobile": mobile})
        
        if user:
            token = jwt.encode(
                {"id": str(user["_id"]), "exp": datetime.utcnow() + timedelta(days=30)},
                os.getenv("JWT_SECRET"),
                algorithm="HS256"
            )
            
            return {
                "success": True,
                "message": "Test OTP verification successful (bypassed)",
                "token": token,
                "user": {
                    "_id": str(user["_id"]),
                    "mobile": user["mobile"],
                    "verified": user.get("verified", False),
                    "name": user.get("name"),
                    "email": user.get("email"),
                    "age": user.get("age"),
                    "gender": user.get("gender"),
                    "location": user.get("location"),
                    "city": user.get("city"),
                    "address": user.get("address")
                }
            }
        else:
            return {"error": f"User not found: {str(e)}"}
