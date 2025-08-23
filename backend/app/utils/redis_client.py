import redis.asyncio as redis
import logging
from app.config import settings  # ✅ import your settings

logger = logging.getLogger(__name__)

# ✅ Use settings values instead of os.getenv
redis_client = redis.Redis(
    host=settings.redis_host,
    port=settings.redis_port,
    password=settings.redis_password,
    decode_responses=True,
    retry_on_timeout=True,
)

async def connect_redis():
   
    try:
        await redis_client.ping()
        logger.info("✅ Connected to Redis")
    except Exception as e:
        logger.error(f"🚨 Redis connection failed: {e}")
