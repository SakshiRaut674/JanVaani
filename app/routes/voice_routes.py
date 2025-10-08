"""
Voice Assistant API Routes
Provides endpoints for voice input, text queries, and chat session management
"""

import base64
from typing import Optional, Dict, Any
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.services.chat_session_service import session_manager, ChatSession
from app.services.gemini_service import gemini_service
from app.services.voice_service import voice_service
from app.middlewares.auth_middleware import get_current_user_optional


# Router for voice assistant endpoints
router = APIRouter(tags=["Voice Assistant"])


# Pydantic models for request/response
class TextChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    success: bool
    user_message: str
    bot_response: str
    session_id: str
    auth_status: Dict[str, Any]
    message_count: int
    function_calls: list = []
    error: Optional[str] = None


class VoiceChatResponse(BaseModel):
    success: bool
    user_speech: str
    bot_response: str
    audio_response: Optional[str] = None  # Base64 encoded audio
    session_id: str
    auth_status: Dict[str, Any]
    message_count: int
    content_type: str = "audio/wav"
    function_calls: list = []
    error: Optional[str] = None


# ==================== VOICE ENDPOINTS ====================

@router.post("/chat/voice", response_model=VoiceChatResponse)
async def voice_to_voice_chat(
    audio_file: UploadFile = File(...),
    session_id: Optional[str] = Form(None),
    current_user: Optional[dict] = Depends(get_current_user_optional)
):
    """Handle complete voice-to-voice interaction with authentication"""
    try:
        # Validate audio file
        if not audio_file.content_type or not audio_file.content_type.startswith('audio'):
            raise HTTPException(status_code=400, detail="Invalid audio file format")
        
        # Step 1: Convert speech to text
        audio_data = await audio_file.read()
        
        # Validate audio data
        audio_info = voice_service.validate_audio_format(audio_data)
        if not audio_info["valid"]:
            raise HTTPException(status_code=400, detail=f"Invalid audio: {audio_info['message']}")
        
        user_text = await voice_service.speech_to_text(audio_data)
        print(f"👤 User said: {user_text}")
        
        # Step 2: Get or create chat session
        session = session_manager.get_or_create_session(
            session_id=session_id,
            user_id=current_user.get("_id") if current_user else None
        )
        
        print(f"💬 Session: {session.session_id}, Auth Status: {session.get_auth_status()}")
        
        # Step 3: Process message through Gemini AI
        ai_response = await gemini_service.process_message(session, user_text)
        response_text = ai_response["response"]
        function_calls = ai_response.get("function_calls", [])
        
        print(f"🤖 Bot response: {response_text}")
        
        # Step 4: Execute function calls if any
        function_results = []
        if function_calls:
            function_results = await execute_function_calls(session, function_calls, current_user)
        
        # Step 5: Convert response to speech
        try:
            audio_response = await voice_service.text_to_speech(response_text)
            audio_base64 = base64.b64encode(audio_response).decode()
        except Exception as e:
            print(f"⚠️ Text-to-speech failed: {e}")
            audio_base64 = None
        
        # Step 6: Return voice response with session info
        return VoiceChatResponse(
            success=True,
            user_speech=user_text,
            bot_response=response_text,
            audio_response=audio_base64,
            session_id=session.session_id,
            auth_status=session.get_auth_status(),
            message_count=len(session.message_history),
            function_calls=function_results
        )
        
    except HTTPException as he:
        # Handle HTTP exceptions
        error_message = str(he.detail)
        print(f"❌ HTTP Error: {error_message}")
        
        # Try to provide voice error response
        try:
            error_audio = await voice_service.text_to_speech(f"I'm sorry, {error_message} Please try again.")
            return VoiceChatResponse(
                success=False,
                user_speech="",
                bot_response=error_message,
                audio_response=base64.b64encode(error_audio).decode(),
                session_id=session_id or "unknown",
                auth_status={},
                message_count=0,
                error=error_message
            )
        except:
            raise he
            
    except Exception as e:
        error_message = f"An unexpected error occurred: {str(e)}"
        print(f"❌ Unexpected Error: {error_message}")
        
        raise HTTPException(status_code=500, detail=error_message)


@router.post("/chat/text", response_model=ChatResponse)
async def text_chat(
    request: TextChatRequest,
    current_user: Optional[dict] = Depends(get_current_user_optional)
):
    """Handle text-based chat interaction"""
    try:
        # Get or create chat session
        session = session_manager.get_or_create_session(
            session_id=request.session_id,
            user_id=current_user.get("_id") if current_user else None
        )
        
        print(f"👤 User message: {request.message}")
        print(f"💬 Session: {session.session_id}, Auth Status: {session.get_auth_status()}")
        
        # Process message through Gemini AI
        ai_response = await gemini_service.process_message(session, request.message)
        response_text = ai_response["response"]
        function_calls = ai_response.get("function_calls", [])
        
        print(f"🤖 Bot response: {response_text}")
        
        # Execute function calls if any
        function_results = []
        if function_calls:
            function_results = await execute_function_calls(session, function_calls, current_user)
        
        return ChatResponse(
            success=True,
            user_message=request.message,
            bot_response=response_text,
            session_id=session.session_id,
            auth_status=session.get_auth_status(),
            message_count=len(session.message_history),
            function_calls=function_results
        )
        
    except Exception as e:
        error_message = f"Chat processing failed: {str(e)}"
        print(f"❌ Text Chat Error: {error_message}")
        
        return ChatResponse(
            success=False,
            user_message=request.message,
            bot_response="I apologize, but I encountered an error processing your request. Please try again.",
            session_id=request.session_id or "unknown",
            auth_status={},
            message_count=0,
            error=error_message
        )


# ==================== SESSION MANAGEMENT ENDPOINTS ====================

@router.get("/sessions/{session_id}")
async def get_session_info(session_id: str):
    """Get information about a chat session"""
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {
        "session_id": session.session_id,
        "created_at": session.created_at.isoformat(),
        "last_activity": session.last_activity.isoformat(),
        "auth_status": session.get_auth_status(),
        "message_count": len(session.message_history),
        "is_expired": session.is_expired()
    }


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a chat session"""
    deleted = session_manager.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {"success": True, "message": "Session deleted successfully"}


@router.post("/sessions/cleanup")
async def cleanup_expired_sessions():
    """Clean up all expired chat sessions"""
    session_manager.cleanup_expired_sessions()
    return {
        "success": True,
        "message": "Expired sessions cleaned up",
        "active_sessions": len(session_manager.sessions)
    }


# ==================== UTILITY FUNCTIONS ====================

async def execute_function_calls(session: ChatSession, function_calls: list, current_user: Optional[dict] = None) -> list:
    """Execute function calls from Gemini AI"""
    results = []
    
    for func_call in function_calls:
        func_name = func_call["name"]
        func_args = func_call["args"]
        
        try:
            if func_name == "send_otp":
                result = await send_otp_function(session, func_args.get("mobile_number"))
            elif func_name == "verify_otp":
                result = await verify_otp_function(session, func_args.get("mobile_number"), func_args.get("otp_code"))
            elif func_name == "register_complaint":
                result = await register_complaint_function(session, func_args, current_user)
            elif func_name == "get_complaint_status":
                result = await get_complaint_status_function(session, func_args.get("complaint_id"), current_user)
            elif func_name == "get_user_complaints":
                result = await get_user_complaints_function(session, current_user)
            elif func_name == "get_user_bills":
                result = await get_user_bills_function(session, current_user)
            elif func_name == "get_payment_history":
                result = await get_payment_history_function(session, current_user)
            else:
                result = {"success": False, "error": f"Unknown function: {func_name}"}
            
            results.append({
                "function": func_name,
                "args": func_args,
                "result": result
            })
            
        except Exception as e:
            results.append({
                "function": func_name,
                "args": func_args,
                "result": {"success": False, "error": str(e)}
            })
    
    return results


# ==================== FUNCTION IMPLEMENTATIONS ====================
# Note: These will need to be implemented to call actual backend services

async def send_otp_function(session: ChatSession, mobile: str) -> Dict[str, Any]:
    """Send OTP to mobile number"""
    # TODO: Implement actual OTP sending via existing auth routes
    session.pending_mobile = mobile
    session.auth_step = "NEED_OTP"
    return {"success": True, "message": "OTP sent successfully", "mobile": mobile}


async def verify_otp_function(session: ChatSession, mobile: str, otp: str) -> Dict[str, Any]:
    """Verify OTP and authenticate session"""
    # TODO: Implement actual OTP verification via existing auth routes
    # For now, mock authentication
    session.set_authenticated("mock_token", {"_id": "mock_user", "mobile": mobile})
    return {"success": True, "message": "Authentication successful", "user_id": session.user_id}


async def register_complaint_function(session: ChatSession, args: dict, current_user: Optional[dict]) -> Dict[str, Any]:
    """Register a municipal complaint"""
    # TODO: Implement actual complaint registration via existing grievance routes
    return {"success": True, "complaint_id": "COMP123", "message": "Complaint registered successfully"}


async def get_complaint_status_function(session: ChatSession, complaint_id: str, current_user: Optional[dict]) -> Dict[str, Any]:
    """Get complaint status"""
    # TODO: Implement actual complaint status retrieval
    return {"success": True, "complaint_id": complaint_id, "status": "In Progress"}


async def get_user_complaints_function(session: ChatSession, current_user: Optional[dict]) -> Dict[str, Any]:
    """Get user's complaints"""
    # TODO: Implement actual user complaints retrieval
    return {"success": True, "complaints": [], "count": 0}


async def get_user_bills_function(session: ChatSession, current_user: Optional[dict]) -> Dict[str, Any]:
    """Get user's pending bills"""
    # TODO: Implement actual bills retrieval
    return {"success": True, "bills": [], "total_amount": 0}


async def get_payment_history_function(session: ChatSession, current_user: Optional[dict]) -> Dict[str, Any]:
    """Get user's payment history"""
    # TODO: Implement actual payment history retrieval
    return {"success": True, "payments": [], "count": 0}