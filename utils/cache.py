"""Unified caching system with coordination."""

import os
import json
import asyncio
import time
import random
from typing import Any, Optional, Set, Dict, List, Tuple, Callable, Awaitable, TypedDict
from datetime import datetime, timedelta
from utils.logger import log
from config import RedisConfig  # If we add Redis config later

# Try to import redis; if not available, mark it accordingly
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

# Define TypedDict for metric data
class MetricData(TypedDict, total=False):
    hits: int
    misses: int
    sets: int
    evictions: int
    hit_rate: float

# Cache metrics collector for the entire application
class CacheMetrics:
    """Global cache metrics collector for monitoring cache performance."""
    
    def __init__(self):
        self._metrics: Dict[str, Dict[str, int]] = {}
        self._lock = asyncio.Lock()
        self._log_interval = 3600  # Log stats every hour by default
        self._last_log_time = time.time()
    
    def register_cache(self, cache_name: str):
        """Register a new cache instance for metrics tracking."""
        if cache_name not in self._metrics:
            self._metrics[cache_name] = {
                "hits": 0,
                "misses": 0,
                "sets": 0,
                "evictions": 0
            }
    
    async def increment(self, cache_name: str, metric: str, amount: int = 1):
        """Increment a metric for the specified cache."""
        async with self._lock:
            if cache_name not in self._metrics:
                self.register_cache(cache_name)
            
            if metric in self._metrics[cache_name]:
                self._metrics[cache_name][metric] += amount
            
            # Periodically log stats
            current_time = time.time()
            if current_time - self._last_log_time > self._log_interval:
                await self.log_stats()
                self._last_log_time = current_time
    
    def get_hit_rate(self, cache_name: str) -> float:
        """Calculate the hit rate for a specific cache."""
        if cache_name not in self._metrics:
            return 0.0
        
        hits = self._metrics[cache_name]["hits"]
        misses = self._metrics[cache_name]["misses"]
        total = hits + misses
        
        if total == 0:
            return 0.0
        
        return hits / total
    
    def get_metrics(self, cache_name: Optional[str] = None) -> Dict[str, MetricData]:
        """Get metrics for a specific cache or all caches."""
        if cache_name:
            metrics = self._metrics.get(cache_name, {}).copy()
            # Add derived metrics
            total_ops = metrics.get("hits", 0) + metrics.get("misses", 0)
            if total_ops > 0:
                metrics["hit_rate"] = metrics.get("hits", 0) / total_ops
            else:
                metrics["hit_rate"] = 0.0
            return metrics
        
        # Return all metrics with hit rates
        result: Dict[str, MetricData] = {}
        for name, data in self._metrics.items():
            result[name] = data.copy()
            total_ops = data.get("hits", 0) + data.get("misses", 0)
            if total_ops > 0:
                result[name]["hit_rate"] = data.get("hits", 0) / total_ops
            else:
                result[name]["hit_rate"] = 0.0
        
        return result
    
    async def log_stats(self):
        """Log current cache statistics."""
        all_metrics = self.get_metrics()
        for cache_name, metrics in all_metrics.items():
            hit_rate = metrics.get("hit_rate", 0) * 100  # Convert to percentage
            log(
                f"Cache metrics for {cache_name}: "
                f"Hit rate: {hit_rate:.1f}%, "
                f"Hits: {metrics.get('hits', 0)}, "
                f"Misses: {metrics.get('misses', 0)}, "
                f"Sets: {metrics.get('sets', 0)}, "
                f"Evictions: {metrics.get('evictions', 0)}",
                level="info"
            )
    
    async def reset(self, cache_name: Optional[str] = None):
        """Reset metrics for a specific cache or all caches."""
        async with self._lock:
            if cache_name:
                if cache_name in self._metrics:
                    self._metrics[cache_name] = {
                        "hits": 0, "misses": 0, "sets": 0, "evictions": 0
                    }
            else:
                for name in self._metrics:
                    self._metrics[name] = {
                        "hits": 0, "misses": 0, "sets": 0, "evictions": 0
                    }

# Global metrics instance
cache_metrics = CacheMetrics()

class CacheCoordinator:
    """Coordinates caching across different subsystems."""
    
    def __init__(self):
        self._caches: Dict[str, 'UnifiedCache'] = {}
        self._lock = asyncio.Lock()
        
    def register_cache(self, name: str, cache: 'UnifiedCache'):
        """Register a cache instance."""
        self._caches[name] = cache
        cache_metrics.register_cache(name)
        
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
    
    async def get_metrics(self) -> Dict:
        """Get metrics for all registered caches."""
        return cache_metrics.get_metrics()
    
    async def log_metrics(self):
        """Log metrics for all registered caches."""
        await cache_metrics.log_stats()

# Cache key usage tracking for adaptive TTL
class KeyUsageTracker:
    """Tracks usage patterns of cache keys for adaptive TTL."""
    
    def __init__(self, sample_rate: float = 0.1, max_tracked_keys: int = 10000):
        self._access_counts: Dict[str, int] = {}
        self._last_accessed: Dict[str, float] = {}
        self._sample_rate = sample_rate  # Only track a percentage of accesses to reduce overhead
        self._max_tracked_keys = max_tracked_keys
        self._lock = asyncio.Lock()
    
    async def record_access(self, key: str):
        """Record a key access, sampling to reduce performance impact."""
        # Only track a percentage of accesses to reduce overhead
        if random.random() > self._sample_rate:
            return
            
        async with self._lock:
            # If we're tracking too many keys, remove the least recently used
            if len(self._access_counts) >= self._max_tracked_keys:
                self._prune_least_used()
                
            # Update access count and timestamp
            self._access_counts[key] = self._access_counts.get(key, 0) + 1
            self._last_accessed[key] = time.time()
    
    def _prune_least_used(self):
        """Remove the least recently used keys to keep memory usage controlled."""
        if not self._last_accessed:
            return
            
        # Sort by last access time and remove oldest 10%
        sorted_keys = sorted(self._last_accessed.items(), key=lambda x: x[1])
        keys_to_remove = sorted_keys[:max(int(len(sorted_keys) * 0.1), 1)]
        
        for key, _ in keys_to_remove:
            if key in self._access_counts:
                del self._access_counts[key]
            if key in self._last_accessed:
                del self._last_accessed[key]
    
    async def get_popular_keys(self, limit: int = 100) -> List[Tuple[str, int]]:
        """Get the most frequently accessed keys for cache warming."""
        async with self._lock:
            # Sort by access count (descending)
            sorted_keys = sorted(
                self._access_counts.items(), 
                key=lambda x: x[1], 
                reverse=True
            )[:limit]
            return sorted_keys
    
    def get_adaptive_ttl(self, key: str, default_ttl: int, min_ttl: int, max_ttl: int) -> int:
        """
        Calculate an adaptive TTL based on key usage pattern.
        
        More frequently accessed keys get longer TTLs, up to max_ttl.
        """
        access_count = self._access_counts.get(key, 0)
        
        if access_count == 0:
            return default_ttl
            
        # Simple adaptive algorithm: scale TTL based on access frequency
        # More sophisticated algorithms could be implemented
        if access_count <= 5:
            return default_ttl
        elif access_count <= 20:
            return min(default_ttl * 2, max_ttl)
        else:
            return max_ttl

class UnifiedCache:
    """Enhanced caching implementation with better coordination."""
    
    def __init__(
        self, 
        name: str, 
        ttl: int = 3600,
        min_ttl: int = 300,
        max_ttl: int = 86400,  # 24 hours
        adaptive_ttl: bool = True
    ):
        self.name = name
        self.default_ttl = ttl
        self.min_ttl = min_ttl
        self.max_ttl = max_ttl
        self.adaptive_ttl = adaptive_ttl
        self._local_cache: Dict[str, Any] = {}
        self._local_timestamps: Dict[str, datetime] = {}
        self._usage_tracker = KeyUsageTracker()
        
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
        """Async get operation with metrics tracking."""
        value = None
        hit = False
        
        if self.use_redis:
            try:
                value = await asyncio.to_thread(self.client.get, f"{self.name}:{key}")
                if value:
                    value = json.loads(value)
                    hit = True
            except Exception:
                # Fall back to local cache
                value = self._get_local(key)
                hit = value is not None
        else:
            value = self._get_local(key)
            hit = value is not None
        
        # Track metrics
        if hit:
            await cache_metrics.increment(self.name, "hits")
        else:
            await cache_metrics.increment(self.name, "misses")
        
        # Record access for adaptive TTL
        if self.adaptive_ttl and hit:
            await self._usage_tracker.record_access(key)
            
        return value
    
    async def set_async(self, key: str, value: Any, ttl: Optional[int] = None):
        """Async set operation with metrics tracking."""
        # Track metrics
        await cache_metrics.increment(self.name, "sets")
        
        # Calculate adaptive TTL if enabled
        if self.adaptive_ttl and ttl is None:
            effective_ttl = self._usage_tracker.get_adaptive_ttl(
                key, self.default_ttl, self.min_ttl, self.max_ttl
            )
        else:
            effective_ttl = ttl or self.default_ttl
            
        if self.use_redis:
            try:
                await asyncio.to_thread(
                    self.client.set,
                    f"{self.name}:{key}",
                    json.dumps(value),
                    ex=effective_ttl
                )
            except Exception:
                self._set_local(key, value, effective_ttl)
        else:
            self._set_local(key, value, effective_ttl)
    
    async def clear_async(self):
        """Async cache clear with metrics tracking."""
        evicted = 0
        
        if self.use_redis:
            try:
                pattern = f"{self.name}:*"
                keys = await asyncio.to_thread(self.client.keys, pattern)
                if keys:
                    evicted = len(keys)
                    await asyncio.to_thread(self.client.delete, *keys)
            except Exception as e:
                log(f"Error clearing Redis cache: {e}", level="error")
        
        # Clear local cache
        evicted += len(self._local_cache)
        self._local_cache.clear()
        self._local_timestamps.clear()
        
        # Track metrics
        await cache_metrics.increment(self.name, "evictions", evicted)
    
    async def clear_pattern_async(self, pattern: str):
        """Async pattern-based cache clear with metrics tracking."""
        evicted = 0
        
        if self.use_redis:
            try:
                full_pattern = f"{self.name}:{pattern}"
                keys = await asyncio.to_thread(self.client.keys, full_pattern)
                if keys:
                    evicted = len(keys)
                    await asyncio.to_thread(self.client.delete, *keys)
            except Exception as e:
                log(f"Error clearing Redis cache pattern: {e}", level="error")
        
        # Clear matching local cache entries
        local_keys = [k for k in self._local_cache if pattern in k]
        evicted += len(local_keys)
        for k in local_keys:
            del self._local_cache[k]
            del self._local_timestamps[k]
        
        # Track metrics
        await cache_metrics.increment(self.name, "evictions", evicted)
    
    async def warmup(self, keys_values: Dict[str, Any], ttl: Optional[int] = None):
        """
        Pre-populate the cache with key-value pairs.
        
        Args:
            keys_values: Dictionary of key-value pairs to cache
            ttl: Optional TTL override for these values
        """
        for key, value in keys_values.items():
            await self.set_async(key, value, ttl)
        
        log(f"Warmed up cache '{self.name}' with {len(keys_values)} entries", level="info")
    
    async def warmup_from_function(
        self,
        keys: List[str],
        fetch_func: Callable[[List[str]], Awaitable[Dict[str, Any]]],
        ttl: Optional[int] = None
    ):
        """
        Pre-populate the cache by fetching values for the specified keys.
        
        Args:
            keys: List of keys to warm up
            fetch_func: Async function that takes a list of keys and returns a dict of results
            ttl: Optional TTL override for these values
        """
        if not keys:
            return
            
        try:
            # Fetch values for the given keys
            values = await fetch_func(keys)
            
            # Only cache values that were successfully retrieved
            await self.warmup(values, ttl)
            
        except Exception as e:
            log(f"Error warming up cache '{self.name}': {e}", level="error")
    
    async def auto_warmup(
        self,
        fetch_func: Callable[[List[str]], Awaitable[Dict[str, Any]]],
        limit: int = 50
    ):
        """
        Automatically warm up cache with the most popular keys.
        
        Args:
            fetch_func: Async function that takes a list of keys and returns a dict of results
            limit: Maximum number of keys to warm up
        """
        try:
            # Get most popular keys
            popular_keys = await self._usage_tracker.get_popular_keys(limit)
            
            if popular_keys:
                keys = [k for k, _ in popular_keys]
                await self.warmup_from_function(keys, fetch_func)
                log(f"Auto-warmed up {len(keys)} popular keys for cache '{self.name}'", level="info")
                
        except Exception as e:
            log(f"Error in auto-warmup for cache '{self.name}': {e}", level="error")
    
    def _get_local(self, key: str) -> Optional[Any]:
        """Get from local cache with TTL check."""
        if key in self._local_cache:
            timestamp = self._local_timestamps.get(key)
            if timestamp and datetime.now() - timestamp < timedelta(seconds=self.default_ttl):
                return self._local_cache[key]
            else:
                del self._local_cache[key]
                del self._local_timestamps[key]
                # Track eviction
                asyncio.create_task(cache_metrics.increment(self.name, "evictions"))
        return None
    
    def _set_local(self, key: str, value: Any, ttl: int):
        """Set in local cache with timestamp."""
        self._local_cache[key] = value
        self._local_timestamps[key] = datetime.now()

# Global instances
cache_coordinator = CacheCoordinator()

def create_cache(name: str, ttl: int = 3600, adaptive_ttl: bool = True) -> UnifiedCache:
    """Create and register a new cache instance."""
    cache = UnifiedCache(name, ttl, adaptive_ttl=adaptive_ttl)
    cache_coordinator.register_cache(name, cache)
    return cache

# Create default caches
parser_cache = create_cache("parser", ttl=3600)
embedding_cache = create_cache("embedding", ttl=7200)
query_cache = create_cache("query", ttl=1800)
# Add a general cache instance for modules that need a default cache
cache = create_cache("general", ttl=3600)

# Global cache instances with appropriate TTLs
repository_cache = UnifiedCache("repositories", ttl=3600)  # 1 hour
search_cache = UnifiedCache("search", ttl=300)  # 5 minutes
embedding_cache = UnifiedCache("embeddings", ttl=86400)  # 24 hours
pattern_cache = UnifiedCache("patterns", ttl=3600)  # 1 hour 
parser_cache = UnifiedCache("parsers", ttl=1800)  # 30 minutes
graph_cache = UnifiedCache("graph", ttl=3600)  # 1 hour
ast_cache = UnifiedCache("ast", ttl=7200)  # 2 hours

# Register caches with coordinator
cache_coordinator = CacheCoordinator()
cache_coordinator.register_cache("repositories", repository_cache)
cache_coordinator.register_cache("search", search_cache)
cache_coordinator.register_cache("embeddings", embedding_cache)
cache_coordinator.register_cache("patterns", pattern_cache)
cache_coordinator.register_cache("parsers", parser_cache)
cache_coordinator.register_cache("graph", graph_cache)
cache_coordinator.register_cache("ast", ast_cache) 