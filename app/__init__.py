import redis
from dotenv import load_dotenv
import os

# Load environment variables from the .env file
load_dotenv()

# Retrieve Redis host and port from environment variables, with defaults
redis_host = os.getenv("REDIS_HOST", "localhost")
redis_port = int(os.getenv("REDIS_PORT", 6379))

# Initialize the Redis client with the specified host and port
# decode_responses=True ensures that responses are returned as strings
redis_client = redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)