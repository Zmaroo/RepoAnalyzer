"""Unified caching system with coordination."""

import os
import json
import asyncio
from typing import Any, Optional, Set, Dict
from datetime import datetime, timedelta
from utils.logger import log
from config import redis_config  # If we add Redis config later

# Try to import redis; if not available, mark it accordingly
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

class CacheCoordinator:
    """Coordinates caching across different subsystems."""
    
    def __init__(self):
        self._caches: Dict[str, 'UnifiedCache'] = {}
        self._lock = asyncio.Lock()
        
    def register_cache(self, name: str, cache: 'UnifiedCache'):
        """Register a cache instance."""
        self._caches[name] = cache
        
    async def invalidate_all(self):
        """Invalidate all registered caches."""
        async with self._lock:
            for cache in self._caches.values():
                await cache.clear_async()
                
    async def invalidate_pattern(self, pattern: str):
        """Invalidate keys matching pattern across all caches."""
        async with self._lock:
            for cache in self._caches.values():
                await cache.clear_pattern_async(pattern)

class UnifiedCache:
    """Enhanced caching implementation with better coordination."""
    
    def __init__(self, name: str, ttl: int = 3600):
        self.name = name
        self.default_ttl = ttl
        self._local_cache: Dict[str, Any] = {}
        self._local_timestamps: Dict[str, datetime] = {}
        
        # Redis configuration
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.use_redis = False
        
        if REDIS_AVAILABLE:
            try:
                self.client = redis.Redis.from_url(
                    redis_url,
                    decode_responses=True,
                    socket_timeout=1
                )
                self.client.ping()
                self.use_redis = True
                log(f"Redis cache enabled for {name}")
            except Exception as e:
                log(f"Redis not available for {name}, using local cache: {e}", level="warning")
        
    async def get_async(self, key: str) -> Optional[Any]:
        """Async get operation."""
        if self.use_redis:
            try:
                value = await asyncio.to_thread(self.client.get, f"{self.name}:{key}")
                return json.loads(value) if value else None
            except Exception:
                return self._get_local(key)
        return self._get_local(key)
    
    async def set_async(self, key: str, value: Any, ttl: Optional[int] = None):
        """Async set operation."""
        if self.use_redis:
            try:
                await asyncio.to_thread(
                    self.client.set,
                    f"{self.name}:{key}",
                    json.dumps(value),
                    ex=(ttl or self.default_ttl)
                )
            except Exception:
                self._set_local(key, value, ttl)
        else:
            self._set_local(key, value, ttl)
    
    async def clear_async(self):
        """Async cache clear."""
        if self.use_redis:
            try:
                pattern = f"{self.name}:*"
                keys = await asyncio.to_thread(self.client.keys, pattern)
                if keys:
                    await asyncio.to_thread(self.client.delete, *keys)
            except Exception as e:
                log(f"Error clearing Redis cache: {e}", level="error")
        
        self._local_cache.clear()
        self._local_timestamps.clear()
    
    async def clear_pattern_async(self, pattern: str):
        """Async pattern-based cache clear."""
        if self.use_redis:
            try:
                full_pattern = f"{self.name}:{pattern}"
                keys = await asyncio.to_thread(self.client.keys, full_pattern)
                if keys:
                    await asyncio.to_thread(self.client.delete, *keys)
            except Exception as e:
                log(f"Error clearing Redis cache pattern: {e}", level="error")
        
        # Clear matching local cache entries
        local_keys = [k for k in self._local_cache if pattern in k]
        for k in local_keys:
            del self._local_cache[k]
            del self._local_timestamps[k]
    
    def _get_local(self, key: str) -> Optional[Any]:
        """Get from local cache with TTL check."""
        if key in self._local_cache:
            timestamp = self._local_timestamps.get(key)
            if timestamp and datetime.now() - timestamp < timedelta(seconds=self.default_ttl):
                return self._local_cache[key]
            else:
                del self._local_cache[key]
                del self._local_timestamps[key]
        return None
    
    def _set_local(self, key: str, value: Any, ttl: Optional[int] = None):
        """Set in local cache with timestamp."""
        self._local_cache[key] = value
        self._local_timestamps[key] = datetime.now()

# Global instances
cache_coordinator = CacheCoordinator()

def create_cache(name: str, ttl: int = 3600) -> UnifiedCache:
    """Create and register a new cache instance."""
    cache = UnifiedCache(name, ttl)
    cache_coordinator.register_cache(name, cache)
    return cache

# Create default caches
parser_cache = create_cache("parser", ttl=3600)
embedding_cache = create_cache("embedding", ttl=7200)
query_cache = create_cache("query", ttl=1800) 