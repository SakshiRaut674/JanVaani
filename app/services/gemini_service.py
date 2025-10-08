"""
Gemini AI Service for Voice Assistant
Handles Gemini model configuration, function declarations, and AI interactions
"""

import os
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime

# Note: google-generativeai will be imported after installing dependencies
try:
    import google.generativeai as genai
except ImportError:
    print("Warning: google-generativeai not installed. Please run: pip install google-generativeai")
    genai = None

from .chat_session_service import ChatSession


# Valid API categories and priorities for municipal services
VALID_API_CATEGORIES = [
    "water_supply", "electricity", "garbage_collection", "sewage", 
    "road_maintenance", "street_lighting", "drainage", "public_transport",
    "healthcare", "education", "housing", "tax_assessment", "building_permits",
    "environmental", "public_safety", "parks_recreation", "noise_pollution",
    "illegal_construction", "traffic", "other"
]

VALID_API_PRIORITIES = ["low", "medium", "high", "urgent"]


class GeminiService:
    """Handles Gemini AI model configuration and interactions"""
    
    def __init__(self):
        self.model = None
        self.functions = []
        self.is_initialized = False
        
    async def initialize(self, api_key: str = None):
        """Initialize Gemini model with API key"""
        if not genai:
            raise RuntimeError("google-generativeai not installed. Please install it first.")
            
        api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in environment variables")
        
        # Configure Gemini AI
        genai.configure(api_key=api_key)
        
        # Create function declarations for municipal services
        self._setup_function_declarations()
        
        # Create the model with system instructions
        self.model = self._create_gemini_agent()
        self.is_initialized = True
        
        print("✅ Gemini AI Service initialized successfully")
    
    def _setup_function_declarations(self):
        """Setup function declarations for Gemini model"""
        self.functions = [
            # Authentication functions
            {
                "name": "send_otp",
                "description": "Send OTP to user's mobile number for authentication",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "mobile_number": {
                            "type": "string",
                            "description": "10-digit mobile number"
                        }
                    },
                    "required": ["mobile_number"]
                }
            },
            {
                "name": "verify_otp",
                "description": "Verify OTP code for user authentication",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "mobile_number": {
                            "type": "string",
                            "description": "10-digit mobile number"
                        },
                        "otp_code": {
                            "type": "string",
                            "description": "6-digit OTP code"
                        }
                    },
                    "required": ["mobile_number", "otp_code"]
                }
            },
            
            # Municipal service functions
            {
                "name": "register_complaint",
                "description": "Register a municipal service complaint",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Brief title of the complaint"
                        },
                        "description": {
                            "type": "string", 
                            "description": "Detailed description of the issue"
                        },
                        "category": {
                            "type": "string",
                            "enum": VALID_API_CATEGORIES,
                            "description": "Category of the complaint"
                        },
                        "priority": {
                            "type": "string",
                            "enum": VALID_API_PRIORITIES,
                            "description": "Priority level of the complaint"
                        },
                        "location": {
                            "type": "string",
                            "description": "Location where the issue is occurring"
                        }
                    },
                    "required": ["title", "description", "category", "priority", "location"]
                }
            },
            {
                "name": "get_complaint_status",
                "description": "Get status of a specific complaint by ID",
                "parameters": {
                    "type": "object", 
                    "properties": {
                        "complaint_id": {
                            "type": "string",
                            "description": "Complaint ID to check status"
                        }
                    },
                    "required": ["complaint_id"]
                }
            },
            {
                "name": "get_user_complaints",
                "description": "Get list of all complaints for the authenticated user",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            
            # Bill and payment functions
            {
                "name": "get_user_bills",
                "description": "Get pending bills for the authenticated user",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "get_payment_history",
                "description": "Get payment history for the authenticated user",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        ]
    
    def _create_gemini_agent(self):
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

You represent the municipal corporation through voice interactions - be helpful, professional, and efficient while ensuring security through proper authentication.
"""

        if not genai:
            raise RuntimeError("Gemini AI not available")

        model = genai.GenerativeModel(
            model_name="gemini-2.0-flash-lite",
            system_instruction=system_instruction,
            tools=[{"function_declarations": self.functions}]
        )
        
        return model

    def start_chat_for_session(self, session: ChatSession):
        """Initialize Gemini chat for a session"""
        if not self.is_initialized:
            raise RuntimeError("GeminiService not initialized. Call initialize() first.")
        
        # Create chat instance with history
        session.chat = self.model.start_chat(history=[])
        return session.chat

    async def process_message(self, session: ChatSession, message: str) -> Dict[str, Any]:
        """Process a message through Gemini AI"""
        if not session.chat:
            self.start_chat_for_session(session)
        
        try:
            # Add context if needed
            context_prompt = ""
            if session.message_history:
                context_prompt = f"Session context: {session.get_auth_status()}\n"
            
            # Send message to Gemini
            full_message = context_prompt + message if context_prompt else message
            response = session.chat.send_message(full_message)
            
            # Process function calls if any
            function_calls = []
            if hasattr(response, 'candidates') and response.candidates:
                for candidate in response.candidates:
                    if hasattr(candidate, 'content') and candidate.content.parts:
                        for part in candidate.content.parts:
                            if hasattr(part, 'function_call'):
                                function_calls.append({
                                    "name": part.function_call.name,
                                    "args": dict(part.function_call.args)
                                })
            
            # Add message to session history
            session.add_message("user", message)
            session.add_message("assistant", response.text, function_calls)
            
            return {
                "response": response.text,
                "function_calls": function_calls,
                "session_id": session.session_id
            }
            
        except Exception as e:
            print(f"Error processing message: {e}")
            return {
                "response": "I apologize, but I encountered an error processing your request. Please try again.",
                "function_calls": [],
                "session_id": session.session_id,
                "error": str(e)
            }


# Global Gemini service instance
gemini_service = GeminiService()