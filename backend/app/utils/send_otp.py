from twilio.rest import Client
from app.config import settings  # ✅ import the Pydantic settings object

client = Client(settings.twilio_account_sid, settings.twilio_auth_token)

async def send_otp(mobile: str, otp: str) -> str:
    try:
        print(f"Sending OTP via Twilio: {otp} to {mobile}")
        message = client.messages.create(
            body=f"Your otp is:{otp}",
            from_=settings.twilio_phone_number,
            to=mobile
        )
        return message.sid
    except Exception as e:
        print(f"Err: OTP not sent {otp} to {mobile}")
        raise Exception(f"Failed to send OTP via Twilio: {e}") from e
