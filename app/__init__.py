import aioredis
import os

redis = None

async def init_redis_pool():
    global redis
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = int(os.getenv("REDIS_PORT", 6379))
    redis = await aioredis.create_redis_pool(
        f"redis://{redis_host}:{redis_port}",
        encoding='utf-8',
    )