from pydantic_settings import BaseSettings

class Settings(BaseSettings):
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

    class Config:
        env_file = ".env"

settings = Settings()
