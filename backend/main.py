import os
import signal
import sys

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.database.database import init_db
from app.utils.redis_client import connect_redis, redis_client
from app.routes.auth_routes import router as auth_router
from app.routes.user_routes import router as user_router
from app.routes.grievance_routes import router as grievance_router  # New import
from app.routes.grievance_admin_routes import router as grievance_admin_router  # Admin routes for AI Agent
load_dotenv()

app = FastAPI(
    title="Municipal Services API",
    description="API for Municipal Services including Authentication, User Management, and Grievance System",
    version="1.0.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check route for Railway
@app.get("/healthz")
async def health_check():
    return {"status": "OK"}

# Hello world root
@app.get("/")
async def root():
    print("Hello, World")
    return {"message": "Municipal Services API - Ready to serve!"}

# Connect MongoDB
@app.on_event("startup")
async def startup():
    print("Connecting to MongoDB...")

    await init_db()

    print("Testing Redis Connection on Startup...")
    try:
        await connect_redis()
        print("Redis connection successful !")
    except Exception as err:
        print("Redis connection failed", err)

# Graceful shutdown
@app.on_event("shutdown")
async def shutdown():
    try:
        if redis_client:
            print("Closing Redis connection...")
            await redis_client.close()
    except Exception as e:
        print("Error closing Redis:", e)

# Register routes
app.include_router(auth_router, prefix="/api/auth")
app.include_router(user_router, prefix="/api/users")
app.include_router(grievance_router, prefix="/api/grievances")  # User grievance routes
app.include_router(grievance_admin_router, prefix="/api/grievances")  # Admin grievance routes for AI Agent

# Error handler
@app.middleware("http")
async def custom_error_handler(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 3000))
    print(f"Starting server on port {port}...")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True, access_log=True)