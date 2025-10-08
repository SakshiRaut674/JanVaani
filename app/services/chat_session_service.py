"""
Chat Session Management Service for Voice Assistant
Handles session state, authentication, and conversation history
"""

import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import google.generativeai as genai


class ChatSession:
    """Manages individual chat sessions with authentication and conversation history"""
    
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
        """Update last activity timestamp"""
        self.last_activity = datetime.now()
        
    def is_expired(self, timeout_minutes: int = 30) -> bool:
        """Check if session has expired"""
        return datetime.now() - self.last_activity > timedelta(minutes=timeout_minutes)
    
    def add_message(self, role: str, content: str, function_calls: List[Dict] = None):
        """Add message to conversation history"""
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


class ChatSessionManager:
    """Manages all chat sessions"""
    
    def __init__(self):
        self.sessions: Dict[str, ChatSession] = {}
    
    def get_or_create_session(self, session_id: str = None, user_id: str = None) -> ChatSession:
        """Get existing chat session or create new one"""
        
        # Clean up expired sessions
        self.cleanup_expired_sessions()
        
        if session_id and session_id in self.sessions:
            session = self.sessions[session_id]
            session.update_activity()
            return session
        
        # Create new session
        new_session_id = session_id or str(uuid.uuid4())
        session = ChatSession(new_session_id, user_id)
        
        self.sessions[new_session_id] = session
        return session

    def cleanup_expired_sessions(self):
        """Remove expired chat sessions"""
        expired_sessions = [
            sid for sid, session in self.sessions.items() 
            if session.is_expired()
        ]
        
        for sid in expired_sessions:
            del self.sessions[sid]
        
        if expired_sessions:
            print(f"🧹 Cleaned up {len(expired_sessions)} expired chat sessions")

    def build_context_prompt(self, session: ChatSession) -> str:
        """Build context prompt from chat history"""
        if not session.message_history:
            return ""
        
        context_parts = []
        
        # Add conversation context
        if len(session.message_history) > 0:
            context_parts.append("Previous conversation context:")
            
            for msg in session.message_history[-5:]:  # Last 5 messages
                role = msg["role"]
                content = msg["content"][:200]  # Limit content length
                context_parts.append(f"{role}: {content}")
        
        return "\n".join(context_parts)

    def get_session(self, session_id: str) -> Optional[ChatSession]:
        """Get session by ID"""
        return self.sessions.get(session_id)

    def delete_session(self, session_id: str) -> bool:
        """Delete session by ID"""
        if session_id in self.sessions:
            del self.sessions[session_id]
            return True
        return False


# Global session manager instance
session_manager = ChatSessionManager()