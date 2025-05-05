"""Unified caching system with coordination."""

import os
import json
import asyncio
import time
import random
from typing import Any, Optional, Set, Dict, List, Tuple, Callable, Awaitable, TypedDict, Protocol, Literal
from datetime import datetime, timedelta
from utils.logger import log
from utils.error_handling import handle_errors, handle_async_errors, AsyncErrorBoundary, CacheError
from config import RedisConfig  # If we add Redis config later
from parsers.models import FileClassification
from utils.shutdown import register_shutdown_handler
from collections import OrderedDict

# Try to import redis; if not available, mark it accordingly
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

# Maximum number of items in cache by default
MAX_CACHE_SIZE = 1000

class CacheInterface(Protocol):
    """Protocol defining the required interface for cache implementations."""
    async def get_async(self, key: str) -> Optional[Any]: ...
    async def set_async(self, key: str, value: Any, expire: Optional[int] = None) -> None: ...
    async def clear_async(self) -> None: ...
    async def cleanup(self) -> None: ...

class UnifiedCache(CacheInterface):
    """Enhanced unified cache implementation with optional LRU eviction."""
    
    def __init__(self, name: str, eviction_policy: Literal["lru", "none"] = "none", max_size: int = MAX_CACHE_SIZE):
        """Initialize cache with optional LRU eviction.
        
        Args:
            name: Cache instance name
            eviction_policy: "lru" for LRU eviction, "none" for no automatic eviction
            max_size: Maximum number of items for LRU eviction (ignored if eviction_policy is "none")
        """
        self.name = name
        self._cache = OrderedDict() if eviction_policy == "lru" else {}
        self._max_size = max_size if eviction_policy == "lru" else None
        self._eviction_policy = eviction_policy
        self._lock = asyncio.Lock()
        self._pending_tasks: Set[asyncio.Task] = set()
        self._metrics = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "sets": 0
        }
        register_shutdown_handler(self.cleanup)
    
    @handle_async_errors()
    async def get_async(self, key: str) -> Optional[Any]:
        """Get item from cache."""
        async with self._lock:
            if key in self._cache:
                value = self._cache[key]
                # Move to end if using LRU
                if self._eviction_policy == "lru":
                    del self._cache[key]
                    self._cache[key] = value
                self._metrics["hits"] += 1
                return value
            self._metrics["misses"] += 1
            return None
    
    @handle_async_errors()
    async def set_async(self, key: str, value: Any, expire: Optional[int] = None) -> None:
        """Set item in cache."""
        async with self._lock:
            if self._eviction_policy == "lru":
                # Handle LRU eviction
                if key in self._cache:
                    del self._cache[key]
                elif len(self._cache) >= self._max_size:
                    self._cache.popitem(last=False)
                    self._metrics["evictions"] += 1
            self._cache[key] = value
            self._metrics["sets"] += 1
    
    @handle_async_errors()
    async def clear_async(self) -> None:
        """Clear the cache."""
        async with self._lock:
            evicted = len(self._cache)
            self._cache.clear()
            if evicted > 0:
                self._metrics["evictions"] += evicted
    
    @handle_async_errors()
    async def clear_pattern_async(self, pattern: str) -> None:
        """Clear keys matching pattern."""
        async with self._lock:
            keys = [k for k in self._cache if pattern in k]
            evicted = len(keys)
            for k in keys:
                del self._cache[k]
            if evicted > 0:
                self._metrics["evictions"] += evicted
    
    async def cleanup(self) -> None:
        """Clean up cache resources."""
        try:
            await self.clear_async()
            if self._pending_tasks:
                for task in self._pending_tasks:
                    task.cancel()
                await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                self._pending_tasks.clear()
        except Exception as e:
            await log(f"Error cleaning up cache {self.name}: {e}", level="error")
    
    def get_metrics(self) -> Dict[str, int]:
        """Get cache metrics."""
        return self._metrics.copy()

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
    
    @handle_async_errors()
    async def register_cache(self, cache_name: str):
        """Register a new cache instance for metrics tracking."""
        async with self._lock:
            if cache_name not in self._metrics:
                self._metrics[cache_name] = {
                    "hits": 0,
                    "misses": 0,
                    "sets": 0,
                    "evictions": 0
                }
                log(f"Registered cache metrics for {cache_name}", level="debug")
    
    async def increment(self, cache_name: str, metric: str, amount: int = 1):
        """Increment a metric for the specified cache."""
        async with self._lock:
            if cache_name not in self._metrics:
                await self.register_cache(cache_name)
            
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
        self._caches: Dict[str, UnifiedCache] = {}
        self._lock = asyncio.Lock()
        self._initialized = False
        self._pending_tasks: Set[asyncio.Task] = set()
        
        # Cache instances
        self._repository_cache: Optional[UnifiedCache] = None
        self._search_cache: Optional[UnifiedCache] = None
        self._embedding_cache: Optional[UnifiedCache] = None
        self._pattern_cache: Optional[UnifiedCache] = None
        self._parser_cache: Optional[UnifiedCache] = None
        self._graph_cache: Optional[UnifiedCache] = None
        self._ast_cache: Optional[UnifiedCache] = None
        self._general_cache: Optional[UnifiedCache] = None
        register_shutdown_handler(self.cleanup)
    
    async def register_cache(self, name: str, cache: UnifiedCache) -> None:
        """Register a cache instance."""
        async with self._lock:
            self._caches[name] = cache
            # Register with metrics asynchronously
            await cache_metrics.register_cache(name)
    
    async def initialize(self) -> None:
        """Initialize the cache coordinator."""
        if not self._initialized:
            self._initialized = True
            log("Cache coordinator initialized", level="info")
    
    async def invalidate_all(self) -> None:
        """Invalidate all registered caches."""
        async with self._lock:
            tasks = []
            for cache in self._caches.values():
                task = asyncio.create_task(cache.clear_async())
                tasks.append(task)
                self._pending_tasks.add(task)
            
            try:
                await asyncio.gather(*tasks, return_exceptions=True)
            finally:
                for task in tasks:
                    if task in self._pending_tasks:
                        self._pending_tasks.remove(task)
    
    async def invalidate_pattern(self, pattern: str) -> None:
        """Invalidate keys matching pattern across all caches."""
        async with self._lock:
            tasks = []
            for cache in self._caches.values():
                task = asyncio.create_task(cache.clear_pattern_async(pattern))
                tasks.append(task)
                self._pending_tasks.add(task)
            
            try:
                await asyncio.gather(*tasks, return_exceptions=True)
            finally:
                for task in tasks:
                    if task in self._pending_tasks:
                        self._pending_tasks.remove(task)
    
    async def cleanup(self) -> None:
        """Clean up all cache resources."""
        # Clean up individual caches
        tasks = []
        for cache in self._caches.values():
            task = asyncio.create_task(cache.cleanup())
            tasks.append(task)
            self._pending_tasks.add(task)
        
        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        finally:
            # Clean up coordinator's pending tasks
            if self._pending_tasks:
                await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                self._pending_tasks.clear()

# Global coordinator instance
cache_coordinator = CacheCoordinator()

async def initialize_caches():
    """Initialize the caching system."""
    await cache_coordinator.initialize()

async def cleanup_caches():
    """Cleanup all caches."""
    try:
        await cache_coordinator.cleanup()
    except Exception as e:
        log(f"Error cleaning up caches: {e}", level="error")

@handle_async_errors()
async def warm_common_patterns(limit: int = 50) -> bool:
    """Warm the pattern cache with commonly used patterns."""
    from parsers.pattern_processor import pattern_processor
    
    async with AsyncErrorBoundary("warming common patterns"):
        # Get common patterns from pattern processor
        patterns = pattern_processor.COMMON_PATTERNS
        if not patterns:
            log("No common patterns found for warming", level="warning")
            return False
        
        # Convert patterns to cache format
        cache_patterns = {
            name: {'pattern': pattern.pattern if hasattr(pattern, 'pattern') else str(pattern)}
            for name, pattern in patterns.items()
        }
        
        await cache_coordinator.pattern_cache.warmup(cache_patterns)
        log(f"Warmed pattern cache with {len(patterns)} common patterns", level="info")
        return True

@handle_async_errors()
async def warm_language_specific_patterns(language: str) -> bool:
    """Warm the pattern cache with patterns specific to a programming language."""
    from parsers.pattern_processor import pattern_processor
    
    async with AsyncErrorBoundary(f"warming patterns for language {language}"):
        # Get language-specific patterns
        patterns = pattern_processor.get_patterns_for_file(
            FileClassification(language_id=language)
        )
        if not patterns:
            log(f"No patterns found for language '{language}'", level="warning")
            return False
        
        # Convert patterns to cache format
        cache_patterns = {
            name: {'pattern': pattern.pattern if hasattr(pattern, 'pattern') else str(pattern)}
            for name, pattern in patterns.items()
        }
        
        await cache_coordinator.pattern_cache.warmup(cache_patterns)
        log(f"Warmed pattern cache with {len(patterns)} patterns for language '{language}'", level="info")
        return True 