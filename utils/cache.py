"""Unified caching system with coordination."""

import os
import json
import asyncio
import time
import random
from typing import Any, Optional, Set, Dict, List, Tuple, Callable, Awaitable, TypedDict
from datetime import datetime, timedelta
from utils.logger import log
from utils.error_handling import handle_errors, handle_async_errors, ErrorBoundary, CacheError
from config import RedisConfig  # If we add Redis config later
from parsers.models import FileClassification

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
        
    @handle_async_errors
    async def get_async(self, key: str) -> Optional[Any]:
        """Async get operation with metrics tracking."""
        value = self._get_local(key)
        hit = value is not None
        
        # Track metrics
        if hit:
            await cache_metrics.increment(self.name, "hits")
        else:
            await cache_metrics.increment(self.name, "misses")
            
        return value
    
    @handle_async_errors
    async def set_async(self, key: str, value: Any, ttl: Optional[int] = None):
        """Async set operation with metrics tracking."""
        # Track metrics
        await cache_metrics.increment(self.name, "sets")
        
        effective_ttl = ttl or self.default_ttl
        self._set_local(key, value, effective_ttl)
    
    @handle_async_errors
    async def clear_async(self):
        """Async cache clear with metrics tracking."""
        evicted = len(self._local_cache)
        self._local_cache.clear()
        self._local_timestamps.clear()
        
        # Track metrics
        await cache_metrics.increment(self.name, "evictions", evicted)
    
    @handle_async_errors
    async def clear_pattern_async(self, pattern: str):
        """Async pattern-based cache clear with metrics tracking."""
        # Clear matching local cache entries
        local_keys = [k for k in self._local_cache if pattern in k]
        evicted = len(local_keys)
        for k in local_keys:
            del self._local_cache[k]
            del self._local_timestamps[k]
        
        # Track metrics
        await cache_metrics.increment(self.name, "evictions", evicted)
    
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

def create_cache(name: str, ttl: int = 3600, adaptive_ttl: bool = True) -> UnifiedCache:
    """Create and register a new cache instance."""
    cache = UnifiedCache(name, ttl, adaptive_ttl=adaptive_ttl)
    cache_coordinator.register_cache(name, cache)
    return cache

class CacheCoordinator:
    """Coordinates caching across different subsystems."""
    
    def __init__(self):
        self._caches: Dict[str, 'UnifiedCache'] = {}
        self._lock = asyncio.Lock()
        self._initialized = False
        
        # Cache instances
        self._repository_cache: Optional[UnifiedCache] = None
        self._search_cache: Optional[UnifiedCache] = None
        self._embedding_cache: Optional[UnifiedCache] = None
        self._pattern_cache: Optional[UnifiedCache] = None
        self._parser_cache: Optional[UnifiedCache] = None
        self._graph_cache: Optional[UnifiedCache] = None
        self._ast_cache: Optional[UnifiedCache] = None
        self._general_cache: Optional[UnifiedCache] = None
        
    def register_cache(self, name: str, cache: 'UnifiedCache'):
        """Register a cache instance."""
        self._caches[name] = cache
        cache_metrics.register_cache(name)
        
    def initialize(self):
        """Initialize all cache instances."""
        if self._initialized:
            return
            
        # Create cache instances
        self._repository_cache = UnifiedCache("repositories", ttl=3600)  # 1 hour
        self._search_cache = UnifiedCache("search", ttl=300)  # 5 minutes
        self._embedding_cache = UnifiedCache("embeddings", ttl=86400)  # 24 hours
        self._pattern_cache = UnifiedCache("patterns", ttl=3600)  # 1 hour 
        self._parser_cache = UnifiedCache("parsers", ttl=1800)  # 30 minutes
        self._graph_cache = UnifiedCache("graph", ttl=3600)  # 1 hour
        self._ast_cache = UnifiedCache("ast", ttl=7200)  # 2 hours
        self._general_cache = UnifiedCache("general", ttl=3600)  # 1 hour
        
        # Register caches
        self.register_cache("repositories", self._repository_cache)
        self.register_cache("search", self._search_cache)
        self.register_cache("embeddings", self._embedding_cache)
        self.register_cache("patterns", self._pattern_cache)
        self.register_cache("parsers", self._parser_cache)
        self.register_cache("graph", self._graph_cache)
        self.register_cache("ast", self._ast_cache)
        self.register_cache("general", self._general_cache)
        
        self._initialized = True
        
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
        
    # Cache instance properties
    @property
    def repository_cache(self) -> UnifiedCache:
        """Get repository cache instance."""
        if not self._initialized:
            raise RuntimeError("Cache coordinator not initialized")
        return self._repository_cache
    
    @property
    def search_cache(self) -> UnifiedCache:
        """Get search cache instance."""
        if not self._initialized:
            raise RuntimeError("Cache coordinator not initialized")
        return self._search_cache
    
    @property
    def embedding_cache(self) -> UnifiedCache:
        """Get embedding cache instance."""
        if not self._initialized:
            raise RuntimeError("Cache coordinator not initialized")
        return self._embedding_cache
    
    @property
    def pattern_cache(self) -> UnifiedCache:
        """Get pattern cache instance."""
        if not self._initialized:
            raise RuntimeError("Cache coordinator not initialized")
        return self._pattern_cache
    
    @property
    def parser_cache(self) -> UnifiedCache:
        """Get parser cache instance."""
        if not self._initialized:
            raise RuntimeError("Cache coordinator not initialized")
        return self._parser_cache
    
    @property
    def graph_cache(self) -> UnifiedCache:
        """Get graph cache instance."""
        if not self._initialized:
            raise RuntimeError("Cache coordinator not initialized")
        return self._graph_cache
    
    @property
    def ast_cache(self) -> UnifiedCache:
        """Get AST cache instance."""
        if not self._initialized:
            raise RuntimeError("Cache coordinator not initialized")
        return self._ast_cache
    
    @property
    def cache(self) -> UnifiedCache:
        """Get general cache instance."""
        if not self._initialized:
            raise RuntimeError("Cache coordinator not initialized")
        return self._general_cache

# Global coordinator instance
cache_coordinator = CacheCoordinator()

def initialize_caches():
    """Initialize all cache instances."""
    cache_coordinator.initialize()
    return cache_coordinator

async def cleanup_caches():
    """Cleanup all caches."""
    try:
        await cache_coordinator.invalidate_all()
    except Exception as e:
        log(f"Error cleaning up caches: {e}", level="error")

@handle_async_errors
async def warm_common_patterns(limit: int = 50) -> bool:
    """Warm the pattern cache with commonly used patterns."""
    from parsers.pattern_processor import pattern_processor
    
    with ErrorBoundary("warming common patterns"):
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

@handle_async_errors
async def warm_language_specific_patterns(language: str) -> bool:
    """Warm the pattern cache with patterns specific to a programming language."""
    from parsers.pattern_processor import pattern_processor
    
    with ErrorBoundary(f"warming patterns for language {language}"):
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