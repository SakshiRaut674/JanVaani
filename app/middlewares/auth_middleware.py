"""
Authentication middleware with optional authentication support for voice assistant
"""

from typing import Optional
from fastapi import Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from bson import ObjectId
import os
from app.database.database import get_db

security = HTTPBearer(auto_error=False)  # auto_error=False makes it optional


async def get_current_user_optional(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Optional[dict]:
    """
    Optional authentication dependency for voice routes
    Returns user if authenticated, None if not authenticated (but doesn't raise error)
    """
    if not credentials:
        return None
    
    token = credentials.credentials
    if not token:
        return None
    
    try:
        # Decode JWT token
        decoded = jwt.decode(token, os.getenv("JWT_SECRET"), algorithms=["HS256"])
        user_id = decoded.get("id")
        
        if not user_id:
            return None
        
        # Get user from database
        db = get_db()
        user = await db["users"].find_one(
            {"_id": ObjectId(user_id)},
            {"otp": 0, "otpExpiry": 0}  # Exclude sensitive fields
        )
        
        return user
        
    except JWTError:
        return None
    except Exception as e:
        print(f"Auth middleware error: {e}")
        return None


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """
    Required authentication dependency (same as existing but with proper error handling)
    """
    if not credentials:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Not authorized, token missing")
    
    token = credentials.credentials
    if not token:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Not authorized, token missing")
    
    try:
        # Decode JWT token
        decoded = jwt.decode(token, os.getenv("JWT_SECRET"), algorithms=["HS256"])
        user_id = decoded.get("id")
        
        if not user_id:
            from fastapi import HTTPException
            raise HTTPException(status_code=401, detail="Invalid token")
        
        # Get user from database
        db = get_db()
        user = await db["users"].find_one(
            {"_id": ObjectId(user_id)},
            {"otp": 0, "otpExpiry": 0}  # Exclude sensitive fields
        )
        
        if not user:
            from fastapi import HTTPException
            raise HTTPException(status_code=401, detail="User not found")
        
        return user
        
    except JWTError:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        print(f"Auth middleware error: {e}")
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="Authentication error")