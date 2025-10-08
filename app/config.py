try:
    from pydantic_settings import BaseSettings
except ImportError:
    # Fallback for older pydantic versions
    from pydantic import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Core Application Settings
    port: int = 3000
    mongo_uri: str
    redis_password: str
    redis_host: str
    redis_port: int
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_phone_number: str
    jwt_secret: str
    otp_expiry: int
    cloudinary_cloud_name: str
    cloudinary_api_key: str
    cloudinary_api_secret: str
    
    # Development mode settings
    development_mode: bool = False
    dev_otp: str = "123456"
    
    # AI and Voice Assistant Settings
    gemini_api_key: Optional[str] = None
    voice_processing_enabled: bool = False
    default_voice_language: str = "en-IN"
    
    # Debug and API Configuration
    debug_mode: bool = False
    base_api_url: str = "http://localhost:3000"
    cors_origins: str = "http://localhost:3001,http://localhost:3000"
    
    # Voice Assistant Session Settings
    chat_session_timeout: int = 30
    max_message_history: int = 20
    max_audio_duration: int = 300
    supported_audio_formats: str = "wav,mp3,ogg,webm"
    
    # Payment Gateway (optional)
    razorpay_key_id: Optional[str] = None
    razorpay_key_secret: Optional[str] = None

    class Config:
        env_file = ".env"

settings = Settings()
