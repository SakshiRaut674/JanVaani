from app.config import settings

print("🔍 CHECKING DEVELOPMENT MODE CONFIGURATION")
print("=" * 50)
print(f"Development Mode: {settings.development_mode}")
print(f"Dev OTP: {settings.dev_otp}")
print(f"Twilio Account SID: {settings.twilio_account_sid}")

if settings.development_mode:
    print("✅ Development mode is ENABLED")
else:
    print("❌ Development mode is DISABLED")
    print("💡 Make sure DEVELOPMENT_MODE=true is in your .env file")
