from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import os

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")

client = None
db = None
users_collection = None
grievances_collection = None  # New collection

async def init_db():
    global client, db, users_collection, grievances_collection
    try:
        client = AsyncIOMotorClient(MONGO_URI)
        db = client["myapp"]  # ✅ Explicitly select your DB
        users_collection = db["users"]
        grievances_collection = db["grievances"]  # New collection

        # Create indexes for better performance
        await create_indexes()

        print("MongoDB Connected")
    except Exception as e:
        print("MongoDB Connection Error:", e)
        raise e

async def create_indexes():
    """Create database indexes for better performance"""
    try:
        # Users collection indexes
        await users_collection.create_index("mobile", unique=True)
        await users_collection.create_index("email")
        
        # Grievances collection indexes
        await grievances_collection.create_index("grievance_id", unique=True)
        await grievances_collection.create_index("user_id")
        await grievances_collection.create_index("status")
        await grievances_collection.create_index("category")
        await grievances_collection.create_index("created_at")
        await grievances_collection.create_index([("user_id", 1), ("status", 1)])
        await grievances_collection.create_index([("category", 1), ("status", 1)])
        
        print("Database indexes created")
    except Exception as e:
        print(f"Error creating indexes: {e}")

def get_users_collection():
    if users_collection is None:
        raise RuntimeError("MongoDB not initialized. Call init_db() first.")
    return users_collection

def get_grievances_collection():
    if grievances_collection is None:
        raise RuntimeError("MongoDB not initialized. Call init_db() first.")
    return grievances_collection

def get_db():
    global db
    if db is None:
        raise RuntimeError("MongoDB not initialized. Call init_db() first.")
    return db

async def close_db():
    global client
    if client:
        client.close()
        print("MongoDB Connection Closed")