import os
import json

# Try to import redis; if not available, mark it accordingly.
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

class UnifiedCache:
    def __init__(self):
        # Use a configured URL or default to localhost.
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.use_redis = False  # default to fallback.
        if REDIS_AVAILABLE:
            try:
                # Create a Redis client and set decode_responses=True so we work with strings.
                self.client = redis.Redis.from_url(redis_url, decode_responses=True)
                # Test the connection.
                self.client.ping()
                self.use_redis = True
            except Exception as e:
                print(f"Warning: Redis not available ({e}). Falling back to in-memory cache.")
                self.cache = {}
        else:
            self.cache = {}

    def get(self, key):
        if self.use_redis:
            try:
                return self.client.get(key)
            except Exception:
                return None
        else:
            return self.cache.get(key)

    def set(self, key, value, ex=None):
        if self.use_redis:
            try:
                self.client.set(key, value, ex=ex)
            except Exception:
                self.cache[key] = value
        else:
            self.cache[key] = value

# Create a module-wide instance.
cache = UnifiedCache() 