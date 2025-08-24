from twilio.rest import Client
from app.config import settings  # ✅ import the Pydantic settings object

client = Client(settings.twilio_account_sid, settings.twilio_auth_token)

async def send_otp(mobile: str, otp: str) -> str:
    try:
        # Check if in development mode
        if settings.development_mode:
            print(f"🚀 DEVELOPMENT MODE: Simulating OTP send")
            print(f"📱 Mobile: {mobile}")
            print(f"🔐 OTP: {otp}")
            print(f"✅ OTP would be sent via Twilio in production")
            return "dev_message_sid_12345"  # Return fake message SID
        
        # Production mode - use real Twilio
        print(f"Sending OTP via Twilio: {otp} to {mobile}")
        message = client.messages.create(
            body=f"Your otp is:{otp}",
            from_=settings.twilio_phone_number,
            to=mobile
        )
        return message.sid
    except Exception as e:
        print(f"Err: OTP not sent {otp} to {mobile}")
        
        # If Twilio fails due to limits, check if we can use dev mode
        if "exceeded" in str(e).lower() and "limit" in str(e).lower():
            print("⚠️  Twilio daily limit exceeded!")
            if settings.development_mode:
                print("🚀 Falling back to development mode")
                return "dev_message_sid_fallback"
            else:
                print("💡 Enable DEVELOPMENT_MODE=true in .env to bypass Twilio")
        
        raise Exception(f"Failed to send OTP via Twilio: {e}") from e
