import redis
from dotenv import load_dotenv
import os

load_dotenv()

redis_host = os.getenv("REDIS_HOST", "localhost")
redis_port = os.getenv("REDIS_PORT", 6379)

redis_client = redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)