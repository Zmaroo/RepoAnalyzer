"""Base cache functionality to break circular dependencies."""

from typing import Dict, Any, Optional, List, Tuple, Callable, Awaitable, TYPE_CHECKING
from datetime import datetime, timedelta
import asyncio
import json
import time
import hashlib
import threading
import psutil
import gc

from utils.logger import log
from utils.error_handling import handle_async_errors, ErrorBoundary, CacheError
from utils.cache_types import MetricData, CacheInterface, WarmupFunc, CacheMetricsInterface
from utils.async_runner import get_loop, submit_async_task, cleanup_tasks

if TYPE_CHECKING:
    from utils.cache import UnifiedCache

class CacheCoordinator:
    """Coordinates caching across different subsystems."""
    
    def __init__(self):
        self._caches: Dict[str, 'UnifiedCache'] = {}
        self._metrics_handler: Optional[CacheMetricsInterface] = None
        self._lock = asyncio.Lock()
        self._cleanup_task = None
    
    def register_cache(self, name: str, cache: 'UnifiedCache'):
        """Register a cache with the coordinator."""
        self._caches[name] = cache
    
    def set_metrics_handler(self, handler: CacheMetricsInterface):
        """Set the metrics handler for cache analytics."""
        self._metrics_handler = handler
    
    async def invalidate_all(self):
        """Invalidate all registered caches."""
        async with self._lock:
            for cache in self._caches.values():
                await cache.clear_async()
    
    async def invalidate_pattern(self, pattern: str):
        """Invalidate all caches matching a pattern."""
        async with self._lock:
            for cache in self._caches.values():
                await cache.clear_pattern_async(pattern)
    
    async def get_metrics(self) -> Dict[str, MetricData]:
        """Get metrics from all registered caches."""
        async with self._lock:
            metrics = {}
            for name, cache in self._caches.items():
                metrics[name] = await cache.get_metrics()
            return metrics
    
    async def log_metrics(self):
        """Log metrics for all registered caches."""
        if self._metrics_handler:
            metrics = await self.get_metrics()
            await self._metrics_handler.log_metrics(metrics)

    async def cleanup(self):
        """Clean up all caches and tasks."""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
        
        await self.invalidate_all()
        cleanup_tasks()

# Global cache coordinator
cache_coordinator = CacheCoordinator()

class CacheKeyPattern:
    """Provides standardized methods for generating cache keys."""
    
    @staticmethod
    def file_content(repo_id: int, file_path: str) -> str:
        """Generate cache key for file content."""
        return f"file_content:{repo_id}:{file_path}"
    
    @staticmethod
    def file_metadata(repo_id: int, file_path: str) -> str:
        """Generate cache key for file metadata."""
        return f"file_metadata:{repo_id}:{file_path}"
    
    @staticmethod
    def processing_stats(component_id: str) -> str:
        """Generate cache key for processing stats."""
        return f"processing_stats:{component_id}"
    
    @staticmethod
    def search_results(query_hash: str) -> str:
        """Generate cache key for search results."""
        return f"search_results:{query_hash}"
    
    @staticmethod
    def embeddings(file_hash: str) -> str:
        """Generate cache key for embeddings."""
        return f"embeddings:{file_hash}"
    
    @staticmethod
    def patterns(language: str) -> str:
        """Generate cache key for patterns."""
        return f"patterns:{language}"
    
    @staticmethod
    def doc_clusters(repo_id: int) -> str:
        """Generate cache key for document clusters."""
        return f"doc_clusters:{repo_id}"
    
    @staticmethod
    def health_status(component_id: str) -> str:
        """Generate cache key for health status."""
        return f"health_status:{component_id}"
    
    @staticmethod
    def hash_data(data: Any) -> str:
        """Hash data for cache key generation."""
        if isinstance(data, str):
            return data
        return hashlib.sha256(json.dumps(data).encode()).hexdigest()

def get_cache_patterns() -> CacheKeyPattern:
    """Get the cache key pattern generator."""
    return CacheKeyPattern() 