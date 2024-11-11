# import redis.asyncio as redis
# import os
#
# redis_client = None
#
# async def init_redis_pool():
#     global redis_client
#     redis_host = os.getenv("REDIS_HOST", "localhost")
#     redis_port = int(os.getenv("REDIS_PORT", 6379))
#     redis_client = redis.Redis(
#         host=redis_host,
#         port=redis_port,
#         db=0,
#         encoding='utf-8',
#         decode_responses=True,
#     )
