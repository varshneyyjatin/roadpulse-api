import redis.asyncio as redis
import logging
from config import REDIS_HOST, REDIS_PORT, REDIS_USER, REDIS_PASS, KEY_PREFIX

logger = logging.getLogger(__name__)

redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    username=REDIS_USER,
    password=REDIS_PASS,
    decode_responses=True,
)

def make_key(key: str) -> str:
    return f"{KEY_PREFIX}:{key}"

async def redis_set(key: str, value, expire: int = None):
    try:
        full_key = make_key(key)
        await redis_client.set(full_key, value, ex=expire)
        logger.info(f"Redis SET: {full_key} (expire: {expire}s)")
        return True
    except Exception as e:
        logger.error(f"Redis SET error for key {key}: {str(e)}")
        raise

async def redis_get(key: str):
    try:
        full_key = make_key(key)
        value = await redis_client.get(full_key)
        logger.info(f"Redis GET: {full_key} (found: {value is not None})")
        return value
    except Exception as e:
        logger.error(f"Redis GET error for key {key}: {str(e)}")
        raise

async def redis_delete(key: str):
    try:
        full_key = make_key(key)
        await redis_client.delete(full_key)
        logger.info(f"Redis DELETE: {full_key}")
        return True
    except Exception as e:
        logger.error(f"Redis DELETE error for key {key}: {str(e)}")
        raise
