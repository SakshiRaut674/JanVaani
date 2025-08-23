from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from bson import ObjectId
import os
from app.database.database import get_db
from app.database.database import db  # Adjust path if needed (this is your MongoDB instance)

security = HTTPBearer()

# Middleware-style: attaches user to request.state
async def protect(request: Request, credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    db = get_db()  # ✅ Grab db here safely

    if not token:
        raise HTTPException(status_code=401, detail="Not authorized, token missing")

    try:
        decoded = jwt.decode(token, os.getenv("JWT_SECRET"), algorithms=["HS256"])
        user_id = decoded.get("id")

        user = await db["users"].find_one(
            {"_id": ObjectId(user_id)},
            {"otp": 0, "otpExpiry": 0}
        )

        if not user:
            raise HTTPException(status_code=401, detail="User not found")

        request.state.user = user

    except JWTError as err:
        print("Token verification error:", str(err))
        raise HTTPException(status_code=401, detail="Not authorized, invalid token")


# Optional injection-style: directly returns user from token
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials

    if not token:
        raise HTTPException(status_code=401, detail="Not authorized, token missing")

    try:
        decoded = jwt.decode(token, os.getenv("JWT_SECRET"), algorithms=["HS256"])
        user_id = decoded.get("id")
        db = get_db()  # ✅ Grab db here safely

        user = await db["users"].find_one(
            {"_id": ObjectId(user_id)},
            {"otp": 0, "otpExpiry": 0}
        )

        if not user:
            raise HTTPException(status_code=401, detail="User not found")

        return user
    except JWTError as err:
        print("Token verification error:", str(err))
        raise HTTPException(status_code=401, detail="Not authorized, invalid token")
    


# Admin-only check (based on user stored in request.state)
async def admin_only(request: Request):
    user = getattr(request.state, "user", None)

    if user and user.get("isAdmin", False):
        return

    raise HTTPException(status_code=403, detail="Admin access required")
