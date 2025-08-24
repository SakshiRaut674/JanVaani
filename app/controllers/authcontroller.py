
import os
import jwt
import random
from datetime import datetime, timedelta
from fastapi import HTTPException
from app.utils.redis_client import redis_client
from app.utils.send_otp import send_otp as send_otp_twilio
from app.database.database import get_users_collection





def generate_otp():
    return str(random.randint(100000, 999999))


async def send_otp_controller(mobile: str):
    otp = generate_otp()
    redis_key = f"otp:{mobile}"
    await redis_client.set(redis_key, otp, ex=300)

    await send_otp_twilio(mobile, otp)

    return {"message": "OTP sent successfully"}

async def resend_otp(mobile: str):
    redis_key = f"otp:{mobile}"
    otp = await redis_client.get(redis_key)

    if otp is None:
        otp = generate_otp()
        await redis_client.set(redis_key, otp, ex=300)
    else:
        otp = otp.decode()

    await send_otp_twilio(mobile, otp)

    return {"message": "OTP resent successfully"}



async def verify_otp(mobile: str, otp: str):
    from app.config import settings
    
    users_collection = get_users_collection()
    redis_key = f"otp:{mobile}"
    stored_otp = await redis_client.get(redis_key)  # ✅ await the coroutine
    print(f"Stored OTP: {stored_otp}, Provided OTP: {otp}")

    # Development mode OTP bypass
    if settings.development_mode and otp == settings.dev_otp:
        print(f"🚀 DEVELOPMENT MODE: Using dev OTP {settings.dev_otp}")
        # Don't delete the Redis key in dev mode so it can be reused
    elif stored_otp is None or stored_otp != otp:
        raise HTTPException(status_code=401, detail="Invalid or expired OTP")
    else:
        # Valid OTP in production mode
        await redis_client.delete(redis_key)  # ✅ await the delete too

    user = await users_collection.find_one({"mobile": mobile})
    if user:
        if not user.get("verified", False):
            await users_collection.update_one(
                {"_id": user["_id"]}, {"$set": {"verified": True}}
            )
    else:
        new_user = {
            "mobile": mobile,
            "verified": True,
            "created_at": datetime.utcnow(),
        }
        insert_result = await users_collection.insert_one(new_user)
        user = await users_collection.find_one({"_id": insert_result.inserted_id})

    token = jwt.encode(
        {"id": str(user["_id"]), "exp": datetime.utcnow() + timedelta(days=30)},
        os.getenv("JWT_SECRET"),
        algorithm="HS256"
    )

    return {
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
            "address": user.get("address"),
            "isEmailVerified": user.get("isEmailVerified", False)
        }
    }
