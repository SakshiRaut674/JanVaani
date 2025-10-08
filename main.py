import os
import signal
import sys

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.database.database import init_db
from app.utils.redis_client import connect_redis, redis_client
from app.services.gemini_service import gemini_service
from app.services.voice_service import voice_service
from app.routes.auth_routes import router as auth_router
from app.routes.user_routes import router as user_router
from app.routes.grievance_routes import router as grievance_router  # New import
from app.routes.grievance_admin_routes import router as grievance_admin_router  # Admin routes for AI Agent
from app.routes.debug_routes import router as debug_router  # Debug routes
from app.routes.revenue_routes import router as revenue_router  # Revenue management
from app.routes.payment_routes import router as payment_router  # Payment processing
from app.routes.certificate_routes import router as certificate_router  # Certificate management
from app.routes.voice_routes import router as voice_router  # Voice assistant routes
load_dotenv()

app = FastAPI(
    title="Municipal Services API with Voice Assistant",
    description="API for Municipal Services including Authentication, User Management, Grievance System, and AI-Powered Voice Assistant",
    version="1.1.0"
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
    
    # Initialize AI and Voice Services
    print("Initializing AI and Voice Services...")
    try:
        await gemini_service.initialize()
        await voice_service.initialize()
        print("✅ AI and Voice Services initialized successfully")
    except Exception as e:
        print(f"⚠️ Warning: AI/Voice services initialization failed: {e}")
        print("Voice assistant features will be limited")

# Graceful shutdown
@app.on_event("shutdown")
async def shutdown():
    try:
        if redis_client:
            print("Closing Redis connection...")
            await redis_client.close()
    except Exception as e:
        print("Error closing Redis:", e)

# Register routes with /api prefix (for compatibility)
app.include_router(auth_router, prefix="/api/auth")
app.include_router(user_router, prefix="/api/users")
app.include_router(grievance_router, prefix="/api/grievances")  # User grievance routes
app.include_router(grievance_admin_router, prefix="/api/grievances")  # Admin grievance routes for AI Agent
app.include_router(debug_router, prefix="/api/debug")  # Debug routes
app.include_router(revenue_router, prefix="/api/revenue")  # Revenue with /api prefix
app.include_router(payment_router, prefix="/api/payments")  # Payments with /api prefix
app.include_router(certificate_router, prefix="/api/certificates")  # Certificates with /api prefix
app.include_router(voice_router, prefix="/api/voice", tags=["Voice Assistant"])  # Voice assistant routes

# Register routes without /api prefix (for frontend compatibility)
app.include_router(user_router, prefix="/users", tags=["Users (Direct)"])
app.include_router(grievance_router, prefix="/grievances", tags=["Grievances (Direct)"])
app.include_router(revenue_router, prefix="/revenue", tags=["Revenue (Direct)"])
app.include_router(payment_router, prefix="/payments", tags=["Payments (Direct)"])
app.include_router(certificate_router, prefix="/certificates", tags=["Certificates (Direct)"])
app.include_router(voice_router, prefix="/voice", tags=["Voice Assistant (Direct)"])  # Direct voice routes

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