import os
import json
import asyncio
import httpx  # Replace requests with httpx
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import google.generativeai as genai
from dotenv import load_dotenv
import speech_recognition as sr
import pyttsx3
from io import BytesIO
import base64
import uuid
from datetime import datetime, timedelta
from app.database.database import init_db
from app.utils.redis_client import connect_redis, redis_client
from app.routes.auth_routes import router as auth_router
from app.routes.user_routes import router as user_router
from app.routes.grievance_routes import router as grievance_router  # New import
from app.routes.grievance_admin_routes import router as grievance_admin_router  # Admin routes for AI Agent

load_dotenv()

# Configure Gemini AI
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

app = FastAPI(title="Voice-to-Voice Municipal Assistant", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(auth_router, prefix="/api/auth")
app.include_router(user_router, prefix="/api/users")
app.include_router(grievance_router, prefix="/api/grievances")  # User grievance routes
app.include_router(grievance_admin_router, prefix="/api/grievances")

# Base API URL for your municipal services
BASE_API_URL = os.getenv("BASE_API_URL", "http://localhost:8000/api")

# Create a single HTTP client instance that will be reused
http_client = httpx.AsyncClient(timeout=30.0)

# ==================== ENHANCED CHAT SESSION MANAGEMENT ====================

# In-memory storage for chat sessions (use Redis in production)
chat_sessions = {}

class ChatSession:
    def __init__(self, session_id: str, user_id: str = None):
        self.session_id = session_id
        self.user_id = user_id
        self.created_at = datetime.now()
        self.last_activity = datetime.now()
        self.chat = None  # Gemini chat instance
        self.message_history = []  # Store conversation history
        self.function_call_history = []  # Store function call results for context
        
        # Authentication state
        self.is_authenticated = False
        self.pending_mobile = None  # Store mobile during OTP flow
        self.auth_token = None
        self.user_info = None
        
        # Login flow state
        self.auth_step = "NEED_MOBILE"  # NEED_MOBILE -> NEED_OTP -> AUTHENTICATED
        
    def update_activity(self):
        self.last_activity = datetime.now()
        
    def is_expired(self, timeout_minutes: int = 30) -> bool:
        """Check if session has expired"""
        return datetime.now() - self.last_activity > timedelta(minutes=timeout_minutes)
    
    def add_message(self, role: str, content: str, function_calls: List[Dict] = None):
        """Add message to history"""
        self.message_history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "function_calls": function_calls or []
        })
        
        # Keep only last 20 messages to prevent memory issues
        if len(self.message_history) > 20:
            self.message_history = self.message_history[-20:]

    def set_authenticated(self, token: str, user_info: dict):
        """Mark session as authenticated"""
        self.is_authenticated = True
        self.auth_token = token
        self.user_info = user_info
        self.auth_step = "AUTHENTICATED"
        self.user_id = user_info.get("_id")

    def get_auth_status(self):
        """Get current authentication status"""
        return {
            "authenticated": self.is_authenticated,
            "auth_step": self.auth_step,
            "mobile": self.pending_mobile,
            "user_id": self.user_id
        }

def get_or_create_chat_session(session_id: str = None, user_id: str = None) -> ChatSession:
    """Get existing chat session or create new one"""
    
    # Clean up expired sessions
    cleanup_expired_sessions()
    
    if session_id and session_id in chat_sessions:
        session = chat_sessions[session_id]
        session.update_activity()
        return session
    
    # Create new session
    new_session_id = session_id or str(uuid.uuid4())
    session = ChatSession(new_session_id, user_id)
    
    # Create Gemini chat instance with history
    session.chat = gemini_agent.start_chat(history=[])
    
    chat_sessions[new_session_id] = session
    return session

def cleanup_expired_sessions():
    """Remove expired chat sessions"""
    expired_sessions = [
        sid for sid, session in chat_sessions.items() 
        if session.is_expired()
    ]
    
    for sid in expired_sessions:
        del chat_sessions[sid]
    
    if expired_sessions:
        print(f"🧹 Cleaned up {len(expired_sessions)} expired chat sessions")

def build_context_prompt(session: ChatSession) -> str:
    """Build context prompt from chat history"""
    if not session.message_history:
        return ""
    
    context_parts = []
    
    # Add conversation context
    if len(session.message_history) > 0:
        context_parts.append("Previous conversation context:")
        for msg in session.message_history[-5:]:  # Last 5 messages for context
            role_emoji = "👤" if msg["role"] == "user" else "🤖"
            context_parts.append(f"{role_emoji} {msg['role']}: {msg['content']}")
    
    # Add function call context if relevant
    recent_function_calls = [
        call for call in session.function_call_history[-3:]  # Last 3 function calls
        if datetime.fromisoformat(call["timestamp"]) > datetime.now() - timedelta(minutes=10)
    ]
    
    if recent_function_calls:
        context_parts.append("\nRecent actions taken:")
        for call in recent_function_calls:
            context_parts.append(f"- {call['function_name']}: {call.get('result_summary', 'Action completed')}")
    
    return "\n".join(context_parts) if context_parts else ""

# VALID API CATEGORIES - Reference for AI Agent  
VALID_API_CATEGORIES = [
    "garbage",
    "water_supply", 
    "drainage", 
    "street_lights",
    "roads",
    "sewage", 
    "noise_pollution",
    "illegal_construction",
    "property_tax",
    "other"
]

VALID_API_PRIORITIES = [
    "low",
    "medium", 
    "high", 
    "urgent"
]

# ==================== CATEGORY MAPPING ====================
category_map = {
    "authentication": {
        "keywords": ["login", "otp", "verify", "authentication", "sign in", "token"],
        "functions": ["send_otp", "verify_otp", "set_token"]
    },
    "complaints": {
        "keywords": ["complaint", "grievance", "garbage", "kooda", "pothole", "sadak", "water leakage", "bijli", "street light", "drainage", "road"],
        "functions": ["register_complaint", "get_complaint_status"]
    },
    "complaint_status": {
        "keywords": ["status", "track", "check complaint", "mera complaint", "complaint id"],
        "functions": ["get_complaint_status", "track_complaint"]
    },
    "profile": {
        "keywords": ["profile", "update", "personal details", "user info"],
        "functions": ["get_user_profile", "update_profile"]
    },
    "general_info": {
        "keywords": ["categories", "services", "help", "information", "documents required"],
        "functions": ["get_grievance_categories", "get_awareness_info"]
    }
}

# ==================== ASYNC API FUNCTION IMPLEMENTATIONS ====================

async def set_token(session: ChatSession, token: str) -> Dict[str, Any]:
    """Set JWT token for API authentication"""
    session.auth_token = token
    return {"success": True, "message": "Token set successfully"}

async def send_otp(session: ChatSession, mobile: str) -> Dict[str, Any]:
    """Send OTP to mobile number"""
    try:
        response = await http_client.post(
            f"{BASE_API_URL}/auth/send-otp",
            params={"mobile": mobile}
        )
        if response.status_code == 200:
            session.pending_mobile = mobile
            session.auth_step = "NEED_OTP"
            return {"success": True, "message": "OTP sent successfully", "mobile": mobile}
        else:
            error_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
            return {"success": False, "error": error_data.get("detail", "Failed to send OTP")}
    except Exception as e:
        return {"success": False, "error": str(e)}

async def verify_otp(session: ChatSession, mobile: str, otp: str) -> Dict[str, Any]:
    """Verify OTP and get authentication token"""
    try:
        response = await http_client.post(
            f"{BASE_API_URL}/auth/verify-otp",
            params={"mobile": mobile, "otp": otp}
        )
        if response.status_code == 200:
            data = response.json()
            session.set_authenticated(data["token"], data["user"])
            return {
                "success": True,
                "message": "OTP verified successfully",
                "token": data["token"],
                "user": data["user"]
            }
        else:
            error_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
            return {"success": False, "error": error_data.get("detail", "Invalid OTP")}
    except Exception as e:
        return {"success": False, "error": str(e)}

async def register_complaint(session: ChatSession, category: str, title: str, description: str, location: str, address: str) -> Dict[str, Any]:
    """Register a new grievance/complaint"""
    if not session.is_authenticated:
        return {"success": False, "error": "Authentication required. Please login first."}
    
    try:
        headers = {"Authorization": f"Bearer {session.auth_token}"}
        payload = {
            "title": title,
            "description": description,
            "category": category,
            "priority": "medium",
            "location": location,
            "address": address,
            "landmark": "",
            "ward_number": "1",
            "pin_code": "462001",
            "contact_person": "",
            "alternate_mobile": "",
            "anonymous": False
        }
        
        response = await http_client.post(
            f"{BASE_API_URL}/grievances/create",
            json=payload,
            headers=headers
        )
        
        if response.status_code == 201:
            data = response.json()
            return {
                "success": True,
                "message": "Complaint registered successfully",
                "grievance_id": data["grievance"]["grievance_id"],
                "status": data["grievance"]["status"]
            }
        else:
            error_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
            return {"success": False, "error": error_data.get("detail", "Failed to register complaint")}
    except Exception as e:
        return {"success": False, "error": str(e)}

async def get_complaint_status(session: ChatSession, grievance_id: str) -> Dict[str, Any]:
    """Get status of a specific complaint"""
    try:
        response = await http_client.get(f"{BASE_API_URL}/grievances/track/{grievance_id}")
        if response.status_code == 200:
            data = response.json()
            return {
                "success": True,
                "grievance": data["grievance"]
            }
        else:
            return {"success": False, "error": "Complaint not found"}
    except Exception as e:
        return {"success": False, "error": str(e)}

async def track_complaint(session: ChatSession, grievance_id: str) -> Dict[str, Any]:
    """Track complaint status (alias for get_complaint_status)"""
    return await get_complaint_status(session, grievance_id)

async def get_user_profile(session: ChatSession) -> Dict[str, Any]:
    """Get current user profile"""
    if not session.is_authenticated:
        return {"success": False, "error": "Authentication required"}
    
    try:
        headers = {"Authorization": f"Bearer {session.auth_token}"}
        response = await http_client.get(f"{BASE_API_URL}/users/me", headers=headers)
        if response.status_code == 200:
            return {"success": True, "user": response.json()["user"]}
        else:
            return {"success": False, "error": "Failed to get profile"}
    except Exception as e:
        return {"success": False, "error": str(e)}

async def update_profile(session: ChatSession, name: str = None, email: str = None, age: int = None) -> Dict[str, Any]:
    """Update user profile"""
    if not session.is_authenticated:
        return {"success": False, "error": "Authentication required"}
    
    try:
        headers = {"Authorization": f"Bearer {session.auth_token}"}
        payload = {}
        if name: payload["name"] = name
        if email: payload["email"] = email
        if age: payload["age"] = age
        
        response = await http_client.put(f"{BASE_API_URL}/users/update-profile", json=payload, headers=headers)
        if response.status_code == 200:
            return {"success": True, "message": "Profile updated successfully"}
        else:
            return {"success": False, "error": "Failed to update profile"}
    except Exception as e:
        return {"success": False, "error": str(e)}

async def get_grievance_categories(session: ChatSession) -> Dict[str, Any]:
    """Get all available grievance categories"""
    try:
        print(f"🔗 Making API call to: {BASE_API_URL}/grievances/categories")
        response = await http_client.get(f"{BASE_API_URL}/grievances/categories")
        print(f"📡 API Response Status: {response.status_code}")
        print(f"📄 API Response: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            return {
                "success": True, 
                "categories": data.get("categories", []),
                "message": "Categories retrieved successfully"
            }
        else:
            return {
                "success": False, 
                "error": f"API returned status {response.status_code}: {response.text}",
                "categories": []
            }
    except Exception as e:
        print(f"❌ Error in get_grievance_categories: {str(e)}")
        return {
            "success": False, 
            "error": f"Failed to connect to API: {str(e)}",
            "categories": []
        }

async def get_awareness_info(session: ChatSession, topic: str) -> Dict[str, Any]:
    """Get awareness information (RAG would go here)"""
    # This is where you'd implement RAG for municipal awareness content
    awareness_data = {
        "health": "Municipal health services include free vaccination drives, health checkups, and awareness programs about hygiene.",
        "vaccination": "Free vaccination drives are conducted every month at community centers. No appointment needed.",
        "cleanliness": "Swachh Bharat Mission promotes cleanliness. Report garbage issues through our complaint system.",
        "water": "Municipal water supply is available 24/7. Report leakages or quality issues immediately.",
        "default": "For more information about municipal services, you can register complaints, check status, or contact our helpline."
    }
    
    info = awareness_data.get(topic.lower(), awareness_data["default"])
    return {"success": True, "information": info, "topic": topic}

# ==================== FUNCTION MAPPING (Updated with session parameter) ====================
async def execute_function(session: ChatSession, function_name: str, **kwargs):
    """Execute function with session context"""
    function_map = {
        "set_token": lambda **args: set_token(session, **args),
        "send_otp": lambda **args: send_otp(session, **args),
        "verify_otp": lambda **args: verify_otp(session, **args),
        "register_complaint": lambda **args: register_complaint(session, **args),
        "get_complaint_status": lambda **args: get_complaint_status(session, **args),
        "track_complaint": lambda **args: track_complaint(session, **args),
        "get_user_profile": lambda **args: get_user_profile(session, **args),
        "update_profile": lambda **args: update_profile(session, **args),
        "get_grievance_categories": lambda **args: get_grievance_categories(session, **args),
        "get_awareness_info": lambda **args: get_awareness_info(session, **args)
    }
    
    if function_name not in function_map:
        raise ValueError(f"Unknown function: {function_name}")
    
    return await function_map[function_name](**kwargs)

# ==================== FUNCTION SCHEMAS FOR GEMINI ====================
functions = [
    {
        "name": "set_token",
        "description": "Set JWT authentication token for API requests",
        "parameters": {
            "type": "object",
            "properties": {
                "token": {"type": "string", "description": "JWT authentication token"}
            },
            "required": ["token"]
        }
    },
    {
        "name": "send_otp",
        "description": "Send OTP to a user's mobile number for authentication. Required as first step for new sessions.",
        "parameters": {
            "type": "object",
            "properties": {
                "mobile": {
                    "type": "string",
                    "description": "Mobile number with country code where OTP will be sent"
                }
            },
            "required": ["mobile"]
        }
    },
    {
        "name": "verify_otp",
        "description": "Verify OTP sent to the user's mobile. Returns a JWT authentication token and user info. Creates a new user if one does not exist.",
        "parameters": {
            "type": "object",
            "properties": {
                "mobile": {
                    "type": "string",
                    "description": "Mobile number where OTP was sent"
                },
                "otp": {
                    "type": "string",
                    "description": "6-digit OTP received by the user"
                }
            },
            "required": ["mobile", "otp"]
        }
    },
    {
        "name": "register_complaint",
        "description": "Register a new municipal complaint/grievance. Requires authentication.",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "Complaint category (GARBAGE, POTHOLE, WATER_LEAKAGE, STREET_LIGHT, DRAINAGE, etc.)"},
                "title": {"type": "string", "description": "Brief title of the complaint"},
                "description": {"type": "string", "description": "Detailed description of the issue"},
                "location": {"type": "string", "description": "Location/area where the issue is observed"},
                "address": {"type": "string", "description": "Complete address of the issue location"}
            },
            "required": ["category", "title", "description", "location", "address"]
        }
    },
    {
        "name": "get_complaint_status",
        "description": "Get status and details of a registered complaint using grievance ID",
        "parameters": {
            "type": "object",
            "properties": {
                "grievance_id": {"type": "string", "description": "Unique grievance ID returned when complaint was registered"}
            },
            "required": ["grievance_id"]
        }
    },
    {
        "name": "track_complaint",
        "description": "Track complaint status (same as get_complaint_status)",
        "parameters": {
            "type": "object",
            "properties": {
                "grievance_id": {"type": "string", "description": "Unique grievance ID to track"}
            },
            "required": ["grievance_id"]
        }
    },
    {
        "name": "get_user_profile",
        "description": "Get current authenticated user's profile information",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "update_profile",
        "description": "Update user profile information",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "User's full name"},
                "email": {"type": "string", "description": "User's email address"},
                "age": {"type": "integer", "description": "User's age"}
            },
            "required": []
        }
    },
    {
        "name": "get_grievance_categories",
        "description": "Get all available complaint/grievance categories",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_awareness_info",
        "description": "Get information about municipal awareness programs and FAQs",
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Topic for awareness information (health, vaccination, cleanliness, water, etc.)"}
            },
            "required": ["topic"]
        }
    }
]

# ==================== GEMINI AGENT SETUP ====================
def create_gemini_agent():
    """Create and configure Gemini model with function calling"""
    
    system_instruction = f"""
You are a Voice-to-Voice Municipal Assistant for helping citizens with municipal services. This is a VOICE-ONLY interaction system.

**CRITICAL: MANDATORY AUTHENTICATION FIRST**
Every new session MUST start with user authentication:
1. For new/unauthenticated users: IMMEDIATELY ask for mobile number for OTP login
2. Do not provide any services until user is fully authenticated
3. Authentication flow: Mobile Number → OTP → Full Access

**EXACT API CATEGORY VALUES**
When calling register_complaint function, use these EXACT category strings:
{', '.join(VALID_API_CATEGORIES)}

When calling register_complaint function, use these EXACT priority strings:
{', '.join(VALID_API_PRIORITIES)}

**VOICE-TO-VOICE INTERACTION RULES:**

1. **Authentication Check**: Always check session authentication status before any service
2. **Voice-Optimized Responses**: 
   - Keep responses conversational and natural for speech
   - Avoid long lists or complex formatting
   - Use clear, spoken language patterns
   - Spell out numbers and codes when needed

3. **Authentication Flow**:
   - Step 1: "Welcome! To get started, I need to verify your identity. Please provide your mobile number."
   - Step 2: After mobile → CALL send_otp() → "I've sent an OTP to [number]. Please tell me the 6-digit code."
   - Step 3: After OTP → CALL verify_otp() → "Great! You're now logged in. How can I help you today?"

4. **Auto-Function Calling**:
   - AUTOMATICALLY call functions when users request services
   - Never ask permission - just execute and report results
   - Handle errors gracefully with voice-friendly explanations

5. **Complaint Registration**:
   - Extract details from natural speech
   - Auto-generate professional titles and descriptions
   - Confirm details before submitting: "Let me register a complaint about [issue] at [location]. Is this correct?"

6. **Voice-Friendly Features**:
   - Repeat important information (complaint IDs, etc.)
   - Use natural speech patterns
   - Provide clear confirmation of actions taken
   - Handle follow-up questions in context

**SESSION AUTHENTICATION STATES:**
- NEED_MOBILE: Ask for mobile number
- NEED_OTP: Ask for OTP code  
- AUTHENTICATED: Provide full services

**EXAMPLE CONVERSATION FLOW:**

User: [First interaction - any message]
Assistant: "Welcome to Municipal Services! Before I can help you, I need to verify your identity. Please provide your 10-digit mobile number."

User: "My number is 9876543210"
Assistant: [CALLS send_otp()] "I've sent a 6-digit OTP to 9876543210. Please tell me the code you received."

User: "The code is 123456"
Assistant: [CALLS verify_otp()] "Perfect! You're now logged in. I'm here to help with municipal complaints and services. What can I assist you with today?"

User: "There's a garbage problem in my area"
Assistant: "I can help you register a garbage collection complaint. Please tell me the specific location where this issue is occurring."

**IMPORTANT BEHAVIOR:**
- Always authenticate first, no exceptions
- Use natural, conversational language suitable for voice
- Automatically execute appropriate functions
- Provide voice-friendly confirmations and status updates
- Support both English and Hindi phrases
- Handle authentication state throughout conversation
- Remember complaint IDs and reference them in follow-ups

You represent the municipal corporation through voice interactions - be helpful, professional, and efficient while ensuring security through proper authentication.
"""

    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash-lite",
        system_instruction=system_instruction,
        tools=[{"function_declarations": functions}]
    )
    
    return model

# Create the agent
gemini_agent = create_gemini_agent()

# ==================== ENHANCED VOICE PROCESSING ====================
def speech_to_text(audio_data: bytes) -> str:
    """Convert speech to text using speech_recognition library"""
    try:
        # Initialize recognizer
        r = sr.Recognizer()
        
        # Convert bytes to AudioFile
        audio_file = sr.AudioFile(BytesIO(audio_data))
        
        with audio_file as source:
            # Adjust for ambient noise
            r.adjust_for_ambient_noise(source, duration=0.5)
            audio = r.record(source)
        
        # Recognize speech using Google's API with Indian English
        text = r.recognize_google(audio, language='en-IN')
        return text
    except sr.UnknownValueError:
        raise HTTPException(status_code=400, detail="Could not understand audio. Please speak clearly.")
    except sr.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Speech recognition service error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Speech recognition failed: {str(e)}")

def text_to_speech(text: str) -> bytes:
    """Convert text to speech and return audio bytes"""
    try:
        # Initialize TTS engine
        engine = pyttsx3.init()
        
        # Configure voice settings for better quality
        voices = engine.getProperty('voices')
        if len(voices) > 1:
            # Try to find a female voice or Indian English voice
            for voice in voices:
                if 'female' in voice.name.lower() or 'indian' in voice.name.lower():
                    engine.setProperty('voice', voice.id)
                    break
            else:
                engine.setProperty('voice', voices[0].id)  # Use first available voice
        
        engine.setProperty('rate', 160)  # Slightly slower for clarity
        engine.setProperty('volume', 0.9)  # Higher volume
        
        # Create a unique temp file name
        temp_file = f"temp_audio_{uuid.uuid4().hex[:8]}.wav"
        
        # Save to file
        engine.save_to_file(text, temp_file)
        engine.runAndWait()
        
        # Read the file and return bytes
        with open(temp_file, 'rb') as f:
            audio_data = f.read()
        
        # Clean up temp file
        if os.path.exists(temp_file):
            os.remove(temp_file)
        
        return audio_data
    except Exception as e:
        print(f"TTS Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Text-to-speech failed: {str(e)}")

# ==================== MAIN VOICE-TO-VOICE ENDPOINT ====================

@app.post("/chat/voice")
async def voice_to_voice_chat(audio_file: UploadFile = File(...), session_id: Optional[str] = Form(None)):
    """Handle complete voice-to-voice interaction with mandatory authentication"""
    try:
        # Step 1: Convert speech to text
        audio_data = await audio_file.read()
        user_text = speech_to_text(audio_data)
        
        print(f"👤 User said: {user_text}")
        
        # Step 2: Get or create chat session
        session = get_or_create_chat_session(
            session_id=session_id, 
            user_id=None
        )
        
        print(f"💬 Session: {session.session_id}, Auth Status: {session.get_auth_status()}")
        
        # Step 3: Check authentication and guide user through login if needed
        auth_status = session.get_auth_status()
        
        # Build context from chat history
        context_prompt = build_context_prompt(session)
        
        # Add authentication context to the prompt
        auth_context = f"""
Current session authentication status:
- Authenticated: {auth_status['authenticated']}
- Auth Step: {auth_status['auth_step']}
- Pending Mobile: {auth_status.get('mobile', 'None')}
- User ID: {auth_status.get('user_id', 'None')}

Authentication Rules:
1. If auth_step is "NEED_MOBILE": Ask for mobile number first
2. If auth_step is "NEED_OTP": Ask for OTP code
3. If auth_step is "AUTHENTICATED": Provide full services
4. Do not provide any services until user is authenticated
"""
        
        # Prepare the full message with context
        full_message = user_text
        if context_prompt:
            full_message = f"{auth_context}\n{context_prompt}\n\nCurrent user message: {user_text}"
        else:
            full_message = f"{auth_context}\n\nCurrent user message: {user_text}"
        
        # Step 4: Process with Gemini
        response = session.chat.send_message(full_message)
        response_text, function_calls = await process_gemini_response_with_history(session, response)
        
        # Step 5: Add messages to history
        session.add_message("user", user_text)
        session.add_message("assistant", response_text, function_calls)
        
        print(f"🤖 Bot response: {response_text}")
        
        # Step 6: Convert response to speech
        audio_response = text_to_speech(response_text)
        
        # Step 7: Return voice response with session info
        return JSONResponse({
            "success": True,
            "user_speech": user_text,
            "bot_response": response_text,
            "audio_response": base64.b64encode(audio_response).decode(),
            "session_id": session.session_id,
            "auth_status": session.get_auth_status(),
            "message_count": len(session.message_history),
            "content_type": "audio/wav"
        })
            
    except HTTPException as he:
        # Handle HTTP exceptions (like speech recognition errors)
        error_message = str(he.detail)
        print(f"❌ HTTP Error: {error_message}")
        
        # Convert error to speech for voice response
        try:
            error_audio = text_to_speech(f"I'm sorry, {error_message} Please try again.")
            return JSONResponse({
                "success": False,
                "error": error_message,
                "audio_response": base64.b64encode(error_audio).decode(),
                "session_id": session_id,
                "content_type": "audio/wav"
            }, status_code=he.status_code)
        except:
            return JSONResponse({
                "success": False,
                "error": error_message,
                "session_id": session_id
            }, status_code=he.status_code)
            
    except Exception as e:
        error_message = f"An unexpected error occurred: {str(e)}"
        print(f"❌ Unexpected Error: {error_message}")
        
        # Try to provide voice error response
        try:
            error_audio = text_to_speech("I'm sorry, there was a technical issue. Please try again.")
            return JSONResponse({
                "success": False,
                "error": error_message,
                "audio_response": base64.b64encode(error_audio).decode(),
                "session_id": session_id,
                "content_type": "audio/wav"
            }, status_code=500)
        except:
            return JSONResponse({
                "success": False,
                "error": error_message,
                "session_id": session_id
            }, status_code=500)

# ==================== FALLBACK TEXT ENDPOINT FOR TESTING ====================

class TextQueryRequest(BaseModel):
    message: str
    language: Optional[str] = "en"
    session_id: Optional[str] = None

@app.post("/chat/text")
async def text_chat_with_auth(request: TextQueryRequest):
    """Handle text-based chat with mandatory authentication (for testing)"""
    try:
        # Get or create chat session
        session = get_or_create_chat_session(
            session_id=request.session_id, 
            user_id=None
        )
        
        print(f"💬 Text Session: {session.session_id}, Auth: {session.get_auth_status()}")
        
        # Check authentication and guide user through login if needed
        auth_status = session.get_auth_status()
        
        # Build context from chat history
        context_prompt = build_context_prompt(session)
        
        # Add authentication context to the prompt
        auth_context = f"""
Current session authentication status:
- Authenticated: {auth_status['authenticated']}
- Auth Step: {auth_status['auth_step']}
- Pending Mobile: {auth_status.get('mobile', 'None')}
- User ID: {auth_status.get('user_id', 'None')}

Authentication Rules:
1. If auth_step is "NEED_MOBILE": Ask for mobile number first
2. If auth_step is "NEED_OTP": Ask for OTP code
3. If auth_step is "AUTHENTICATED": Provide full services
4. Do not provide any services until user is authenticated
"""
        
        # Prepare the full message with context
        full_message = request.message
        if context_prompt:
            full_message = f"{auth_context}\n{context_prompt}\n\nCurrent user message: {request.message}"
        else:
            full_message = f"{auth_context}\n\nCurrent user message: {request.message}"
        
        print(f"👤 User message: {request.message}")
        
        # Send message to Gemini with context
        response = session.chat.send_message(full_message)
        
        # Process function calls and get final response
        response_text, function_calls = await process_gemini_response_with_history(session, response)
        
        # Add user message to history
        session.add_message("user", request.message)
        
        # Add assistant response to history
        session.add_message("assistant", response_text, function_calls)
        
        print(f"🤖 Bot response: {response_text}")
        
        return JSONResponse({
            "success": True,
            "response": response_text,
            "session_id": session.session_id,
            "auth_status": session.get_auth_status(),
            "message_count": len(session.message_history)
        })
        
    except Exception as e:
        print(f"❌ Error in text_chat: {str(e)}")
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)

# ==================== GEMINI RESPONSE PROCESSING WITH SESSION ====================

async def process_gemini_response_with_history(session: ChatSession, response):
    """Process Gemini response and handle function calls with session history"""
    
    function_calls_made = []
    
    # Check if Gemini wants to call functions
    if (response.candidates and 
        len(response.candidates) > 0 and 
        response.candidates[0].content and 
        response.candidates[0].content.parts):
        
        for part in response.candidates[0].content.parts:
            # Check if this part contains a function call
            if hasattr(part, 'function_call') and part.function_call:
                function_name = part.function_call.name
                function_args = dict(part.function_call.args)
                
                print(f"🤖 Gemini wants to call: {function_name} with args: {function_args}")
                
                # Execute the function with session context
                try:
                    # Call the function with session
                    result = await execute_function(session, function_name, **function_args)
                    print(f"✅ Function result: {json.dumps(result, indent=2)}")
                    
                    # Store function call in session history for context
                    function_call_record = {
                        "function_name": function_name,
                        "args": function_args,
                        "result": result,
                        "timestamp": datetime.now().isoformat(),
                        "result_summary": generate_result_summary(function_name, result)
                    }
                    session.function_call_history.append(function_call_record)
                    
                    # Keep only last 10 function calls
                    if len(session.function_call_history) > 10:
                        session.function_call_history = session.function_call_history[-10:]
                    
                    function_calls_made.append(function_call_record)
                    
                    # Handle function response
                    try:
                        # Create function response part
                        function_response_content = {
                            "result": result,
                            "success": result.get("success", True) if isinstance(result, dict) else True
                        }
                        
                        # Use the direct method to create function response
                        function_response_part = genai.protos.Part(
                            function_response=genai.protos.FunctionResponse(
                                name=function_name,
                                response=function_response_content
                            )
                        )
                        
                        # Send function result back to Gemini
                        final_response = session.chat.send_message([function_response_part])
                        
                        # Check if there's valid text response
                        if final_response and final_response.text:
                            return final_response.text, function_calls_made
                        else:
                            # Fallback response generation
                            return generate_fallback_response(function_name, result), function_calls_made
                        
                    except Exception as gemini_error:
                        print(f"❌ Gemini processing error: {str(gemini_error)}")
                        # Generate a manual response instead of failing
                        fallback_response = generate_fallback_response(function_name, result)
                        return fallback_response, function_calls_made
                    
                except Exception as e:
                    print(f"❌ Function error: {str(e)}")
                    
                    # Store error in session history
                    function_call_record = {
                        "function_name": function_name,
                        "args": function_args,
                        "error": str(e),
                        "timestamp": datetime.now().isoformat(),
                        "result_summary": f"Error: {str(e)}"
                    }
                    session.function_call_history.append(function_call_record)
                    function_calls_made.append(function_call_record)
                    
                    # Return error response without trying Gemini processing
                    return f"I encountered an error while processing your request: {str(e)}", function_calls_made
            
        # If no function calls but there's text content
        if any(hasattr(part, 'text') and part.text for part in response.candidates[0].content.parts):
            return response.text, function_calls_made
        else:
            return "I'm not sure how to help with that. Could you please rephrase your question?", function_calls_made
    
    # If no function calls, return the direct text response
    elif response.text:
        return response.text, function_calls_made
    else:
        return "I'm sorry, I didn't understand that. Could you please try again?", function_calls_made

def generate_fallback_response(function_name: str, result: Dict[str, Any]) -> str:
    """Generate manual voice-friendly responses when Gemini processing fails"""
    
    if not isinstance(result, dict):
        return "Action completed successfully."
    
    success = result.get("success", True)
    
    if function_name == "send_otp":
        if success:
            mobile = result.get("mobile", "your mobile")
            return f"I've sent a 6-digit O T P to {mobile}. Please tell me the code you received."
        else:
            return f"I couldn't send the O T P. {result.get('error', 'Please try again with a valid mobile number.')}"
    
    elif function_name == "verify_otp":
        if success:
            user_info = result.get("user", {})
            mobile = user_info.get("mobile", "your number")
            return f"Excellent! You're now logged in with {mobile}. I can help you register complaints, check complaint status, or provide information about municipal services. What would you like to do?"
        else:
            return f"The O T P verification failed. {result.get('error', 'Please make sure you entered the correct 6-digit code.')}"
    
    elif function_name == "register_complaint":
        if success:
            grievance_id = result.get("grievance_id", "N/A")
            return f"Your complaint has been registered successfully! Your complaint I D is {grievance_id}. Please note this down for future reference. You can track your complaint status anytime using this I D."
        else:
            error = result.get("error", "Unknown error")
            if "Authentication required" in error:
                return "I need you to login first before registering complaints. Please provide your mobile number to get started."
            return f"I couldn't register your complaint. {error}"
    
    elif function_name == "get_complaint_status" or function_name == "track_complaint":
        if success:
            grievance = result.get("grievance", {})
            grievance_id = grievance.get("grievance_id", "N/A")
            status = grievance.get("status", "Unknown")
            title = grievance.get("title", "N/A")
            return f"Here's your complaint status. Complaint I D {grievance_id} titled {title} is currently {status}."
        else:
            return f"I couldn't find that complaint. {result.get('error', 'Please check the complaint I D and try again.')}"
    
    elif function_name == "get_grievance_categories":
        if success:
            categories = result.get("categories", [])
            if categories:
                # Voice-friendly category list
                category_names = [cat.get("label", cat.get("value", "Unknown")) for cat in categories[:5]]  # Limit to first 5 for voice
                category_list = ", ".join(category_names)
                return f"The main complaint categories are: {category_list}. Which category best describes your issue?"
            return "I retrieved the complaint categories, but the list appears to be empty. Let me know what type of issue you're facing and I'll help categorize it."
        else:
            return f"I couldn't retrieve the categories right now. {result.get('error', 'Please describe your issue and I will help you.')}"
    
    elif function_name == "get_user_profile":
        if success:
            user = result.get("user", {})
            name = user.get("name", "Not set")
            mobile = user.get("mobile", "Not set")
            return f"Your profile shows Name: {name}, Mobile: {mobile}. Would you like to update any information?"
        else:
            return f"I couldn't retrieve your profile. {result.get('error', 'Please try again later.')}"
    
    else:
        if success:
            return "Action completed successfully."
        else:
            return f"The action failed. {result.get('error', 'Please try again.')}"

def generate_result_summary(function_name: str, result: Dict[str, Any]) -> str:
    """Generate a brief summary of function call results for context"""
    if not result.get("success"):
        return f"Failed: {result.get('error', 'Unknown error')}"
    
    if function_name == "register_complaint":
        return f"Registered complaint {result.get('grievance_id', 'N/A')}"
    elif function_name in ["get_complaint_status", "track_complaint"]:
        grievance = result.get("grievance", {})
        return f"Status: {grievance.get('status', 'N/A')}"
    elif function_name == "get_grievance_categories":
        categories = result.get("categories", [])
        return f"Retrieved {len(categories)} categories"
    elif function_name == "send_otp":
        return f"OTP sent to {result.get('mobile', 'N/A')}"
    elif function_name == "verify_otp":
        return "Login successful"
    elif function_name == "get_user_profile":
        user = result.get("user", {})
        return f"Profile: {user.get('name', 'N/A')}"
    else:
        return "Action completed"

# ==================== SESSION MANAGEMENT ENDPOINTS ====================

@app.get("/sessions")
async def get_active_sessions():
    """Get list of active chat sessions"""
    cleanup_expired_sessions()
    
    sessions_info = []
    for session_id, session in chat_sessions.items():
        sessions_info.append({
            "session_id": session_id,
            "user_id": session.user_id,
            "created_at": session.created_at.isoformat(),
            "last_activity": session.last_activity.isoformat(),
            "message_count": len(session.message_history),
            "function_calls": len(session.function_call_history),
            "auth_status": session.get_auth_status()
        })
    
    return JSONResponse({
        "active_sessions": len(sessions_info),
        "sessions": sessions_info
    })

@app.get("/sessions/{session_id}")
async def get_session_details(session_id: str):
    """Get detailed information about a specific session"""
    if session_id not in chat_sessions:
        return JSONResponse({
            "error": "Session not found"
        }, status_code=404)
    
    session = chat_sessions[session_id]
    return JSONResponse({
        "session_id": session_id,
        "auth_status": session.get_auth_status(),
        "message_history": session.message_history,
        "function_call_history": session.function_call_history,
        "created_at": session.created_at.isoformat(),
        "last_activity": session.last_activity.isoformat()
    })

@app.delete("/sessions/{session_id}")
async def clear_specific_session(session_id: str):
    """Clear/delete a specific chat session"""
    if session_id in chat_sessions:
        del chat_sessions[session_id]
        return JSONResponse({"message": f"Session {session_id} cleared successfully"})
    else:
        return JSONResponse({"error": "Session not found"}, status_code=404)

@app.post("/sessions/cleanup")
async def manual_cleanup_sessions():
    """Manually cleanup expired sessions"""
    initial_count = len(chat_sessions)
    cleanup_expired_sessions()
    final_count = len(chat_sessions)
    
    return JSONResponse({
        "message": f"Cleaned up {initial_count - final_count} expired sessions",
        "active_sessions": final_count
    })

# ==================== TESTING AND DEBUG ENDPOINTS ====================

@app.get("/test/speech")
async def test_speech_generation():
    """Test text-to-speech functionality"""
    try:
        test_message = "Welcome to the Municipal Voice Assistant! I can help you register complaints and check their status. Please provide your mobile number to get started."
        audio_data = text_to_speech(test_message)
        
        return JSONResponse({
            "success": True,
            "message": test_message,
            "audio_response": base64.b64encode(audio_data).decode(),
            "content_type": "audio/wav"
        })
    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)

@app.get("/health")
async def health_check():
    return {
        "status": "OK", 
        "service": "Voice-to-Voice Municipal Assistant",
        "version": "2.0.0",
        "features": ["Voice-to-Voice", "Mandatory Authentication", "Session Management"],
        "active_sessions": len(chat_sessions)
    }

# ==================== LIFECYCLE EVENTS ====================

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    print("🚀 Voice-to-Voice Municipal Assistant starting up...")
    print(f"📡 Will connect to municipal API at: {BASE_API_URL}")
    print("📱 Voice-to-Voice mode with mandatory authentication enabled")
    
    print("Connecting to MongoDB...")
    await init_db()

    print("Testing Redis Connection on Startup...")
    try:
        await connect_redis()
        print("Redis connection successful!")
    except Exception as err:
        print(f"Redis connection failed: {err}")

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown"""
    print("🛑 Shutting down Voice-to-Voice Municipal Assistant...")
    await http_client.aclose()
    
    # Clean up any temp audio files
    for filename in os.listdir('.'):
        if filename.startswith('temp_audio_') and filename.endswith('.wav'):
            try:
                os.remove(filename)
                print(f"🧹 Cleaned up temp file: {filename}")
            except:
                pass

@app.get("/")
async def root():
    return {
        "message": "Voice-to-Voice Municipal Assistant with Mandatory Authentication",
        "version": "2.0.0",
        "status": "running",
        "mode": "Voice-to-Voice",
        "features": [
            "Voice Input/Output",
            "Mandatory User Authentication", 
            "Session-based Conversations",
            "Context Awareness",
            "Automatic Function Calling",
            "Municipal Services Integration"
        ],
        "main_endpoint": "/chat/voice",
        "endpoints": {
            "voice_chat": "/chat/voice (Primary)",
            "text_chat": "/chat/text (Testing)",
            "session_info": "/sessions/{session_id}",
            "health": "/health",
            "speech_test": "/test/speech"
        },
        "usage": {
            "authentication": "Required for all sessions - mobile number + OTP",
            "input": "Audio file (WAV/MP3)",
            "output": "JSON with base64 encoded audio response"
        }
    }

if __name__ == "__main__":
    import uvicorn
    # Use port 8002 for voice assistant
    port = int(os.getenv("VOICE_ASSISTANT_PORT", 8002))
    print(f"🎙️ Starting Voice-to-Voice Municipal Assistant on port {port}...")
    uvicorn.run("main_with_gemini:app", host="0.0.0.0", port=port, reload=True)