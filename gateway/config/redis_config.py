import os
import redis.asyncio as redis
from logger import logger

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")

# Create connection pool & client with auto-decoding of responses to string
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

async def check_redis_connection():
    try:
        await redis_client.ping()
        logger.info("Connected to Redis successfully.")
    except Exception as e:
        logger.error(f"Redis Connection Error: {str(e)}")
