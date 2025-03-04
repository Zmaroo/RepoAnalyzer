"""Shared types and interfaces for the caching system."""

from typing import TypedDict, Dict, Any, Optional, List, Tuple, Callable, Awaitable
from datetime import datetime

class MetricData(TypedDict, total=False):
    hits: int
    misses: int
    sets: int
    evictions: int
    hit_rate: float

# Type for cache warmup functions
WarmupFunc = Callable[[List[str]], Awaitable[Dict[str, Any]]]

class CacheInterface:
    """Interface that both UnifiedCache and CacheAnalytics implement."""
    async def get_async(self, key: str) -> Any:
        raise NotImplementedError
        
    async def set_async(self, key: str, value: Any, ttl: Optional[int] = None):
        raise NotImplementedError
        
    async def clear_async(self):
        raise NotImplementedError
        
    async def clear_pattern_async(self, pattern: str):
        raise NotImplementedError

class CacheMetricsInterface:
    """Interface for cache metrics and analytics."""
    async def increment(self, cache_name: str, metric: str, value: int = 1):
        raise NotImplementedError
        
    async def get_metrics(self) -> Dict[str, MetricData]:
        raise NotImplementedError
        
    async def generate_performance_report(self):
        raise NotImplementedError 