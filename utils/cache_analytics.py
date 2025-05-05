"""Cache analytics and optimization utilities.

This module provides tools to analyze cache performance, auto-tune TTL values,
and warm up caches with commonly accessed data for faster application performance.
"""

import asyncio
from typing import Dict, List, Optional, Any, Callable, Awaitable, Tuple, Set
import time
from utils.error_handling import AsyncErrorBoundary, CacheError, ErrorSeverity
from datetime import datetime, timedelta
import json
import os

# Import aiofiles for async file operations
try:
    import aiofiles
    AIOFILES_AVAILABLE = True
except ImportError:
    AIOFILES_AVAILABLE = False

from utils.logger import log, ErrorSeverity
from utils.cache import cache_coordinator, UnifiedCache
from utils.error_handling import handle_async_errors, AsyncErrorBoundary, CacheError
from utils.shutdown import register_shutdown_handler

# Type for cache warmup functions
WarmupFunc = Callable[[List[str]], Awaitable[Dict[str, Any]]]

class CacheAnalytics:
    """Cache analytics and optimization utilities."""
    
    def __init__(self):
        """Private constructor - use create() instead."""
        self._initialized = False
        self._pending_tasks: Set[asyncio.Task] = set()
        self._lock = asyncio.Lock()
        self._report_interval = 3600  # Default: hourly reports
        self._warmup_interval = 86400  # Default: daily warmup
        self._last_report_time = 0
        self._last_warmup_time = 0
        self._is_running = False
        self._task = None
        self._warmup_funcs: Dict[str, WarmupFunc] = {}
        self._coordinator = None
    
    async def ensure_initialized(self):
        """Ensure the instance is properly initialized before use."""
        if not self._initialized:
            raise CacheError("CacheAnalytics not initialized. Use create() to initialize.")
        if not self._coordinator:
            raise CacheError("Cache coordinator not initialized")
        return True
    
    @classmethod
    async def create(cls, coordinator, auto_start: bool = True, report_interval: int = 3600, warmup_interval: int = 86400) -> 'CacheAnalytics':
        """Async factory method to create and initialize a CacheAnalytics instance."""
        instance = cls()
        try:
            async with AsyncErrorBoundary(
                operation_name="cache analytics initialization",
                error_types=CacheError,
                severity=ErrorSeverity.CRITICAL
            ):
                # Set coordinator and intervals
                instance._coordinator = coordinator
                instance._report_interval = report_interval
                instance._warmup_interval = warmup_interval
                
                # Register shutdown handler
                register_shutdown_handler(instance.cleanup)
                
                # Initialize health monitoring
                from utils.health_monitor import global_health_monitor
                global_health_monitor.register_component("cache_analytics")
                
                instance._initialized = True
                await log("Cache analytics initialized", level="info")
                
                # Start monitoring if requested
                if auto_start:
                    await instance.start_monitoring(
                        report_interval=report_interval,
                        warmup_interval=warmup_interval
                    )
                
                return instance
        except Exception as e:
            await log(f"Error initializing cache analytics: {e}", level="error")
            # Cleanup on initialization failure
            await instance.cleanup()
            raise CacheError(f"Failed to initialize cache analytics: {e}")
    
    def register_warmup_function(self, cache_name: str, func: WarmupFunc) -> None:
        """Register a function to warm up a specific cache."""
        self._warmup_funcs[cache_name] = func
        log(f"Registered warmup function for cache: {cache_name}", level="info")
    
    async def start_monitoring(self, report_interval: int = 3600, warmup_interval: int = 86400):
        """Start monitoring cache performance in the background."""
        if not self._initialized:
            await self.ensure_initialized()
            
        if self._is_running:
            await log("Cache monitoring is already running", level="warning")
            return
            
        self._report_interval = report_interval
        self._warmup_interval = warmup_interval
        self._is_running = True
        
        # Start the monitoring loop
        self._task = asyncio.create_task(self._monitoring_loop())
        self._pending_tasks.add(self._task)
        await log("Started cache performance monitoring", level="info")
    
    async def stop_monitoring(self):
        """Stop cache performance monitoring."""
        if not self._initialized:
            await self.ensure_initialized()
            
        if not self._is_running:
            return
            
        self._is_running = False
        if self._task:
            if not self._task.done():
                self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._pending_tasks.remove(self._task)
            self._task = None
            
        await log("Stopped cache performance monitoring", level="info")
    
    async def _monitoring_loop(self):
        """Background loop for cache monitoring."""
        if not self._initialized:
            await self.ensure_initialized()
            
        try:
            while self._is_running:
                current_time = time.time()
                
                # Generate performance report if needed
                if current_time - self._last_report_time >= self._report_interval:
                    task = asyncio.create_task(self.generate_performance_report())
                    self._pending_tasks.add(task)
                    try:
                        await task
                        self._last_report_time = current_time
                    finally:
                        self._pending_tasks.remove(task)
                
                # Warm up caches if needed
                if current_time - self._last_warmup_time >= self._warmup_interval:
                    task = asyncio.create_task(self.warmup_all_caches())
                    self._pending_tasks.add(task)
                    try:
                        await task
                        self._last_warmup_time = current_time
                    finally:
                        self._pending_tasks.remove(task)
                
                await asyncio.sleep(60)  # Check every minute
                
        except asyncio.CancelledError:
            await log("Cache monitoring loop cancelled", level="info")
            raise
        except Exception as e:
            await log(f"Error in monitoring loop: {e}", level="error")
            self._is_running = False
    
    async def _save_metrics_history(self, metrics: Dict):
        """Save metrics to a historical data file."""
        if not self._initialized:
            await self.ensure_initialized()
            
        async with AsyncErrorBoundary("saving cache metrics history"):
            # Skip if aiofiles not available
            if not AIOFILES_AVAILABLE:
                await log("Cannot save metrics history: aiofiles not installed", level="warning")
                return
                
            # Create directory if it doesn't exist
            history_dir = "logs/cache_metrics"
            if not os.path.exists(history_dir):
                os.makedirs(history_dir)
            
            # Create a timestamped record
            timestamp = datetime.now().isoformat()
            record = {
                "timestamp": timestamp,
                "metrics": metrics
            }
            
            # Save to daily log file
            date_str = datetime.now().strftime("%Y%m%d")
            file_path = f"{history_dir}/cache_metrics_{date_str}.jsonl"
            
            # Append to file in JSON Lines format
            async with aiofiles.open(file_path, "a") as f:
                task = asyncio.create_task(f.write(json.dumps(record) + "\n"))
                self._pending_tasks.add(task)
                try:
                    await task
                finally:
                    self._pending_tasks.remove(task)
    
    async def warmup_all_caches(self):
        """Warm up all registered caches with their most popular keys."""
        if not self._initialized:
            await self.ensure_initialized()
            
        caches = self._coordinator._caches
        if not caches:
            return
        
        # Create tasks for each cache warmup
        warmup_tasks = []
        for name, cache in caches.items():
            if not isinstance(cache, UnifiedCache):
                continue
                
            await log(f"Auto-warming up cache: {name}", level="info")
            task = asyncio.create_task(self._warmup_cache_if_possible(name, cache))
            self._pending_tasks.add(task)
            warmup_tasks.append(task)
        
        # Wait for all warmup tasks to complete
        try:
            await asyncio.gather(*warmup_tasks)
        finally:
            for task in warmup_tasks:
                self._pending_tasks.remove(task)
    
    async def optimize_ttl_values(self):
        """Analyze cache usage patterns and suggest optimal TTL values."""
        if not self._initialized:
            await self.ensure_initialized()
            
        task = asyncio.create_task(self._coordinator.get_metrics())
        self._pending_tasks.add(task)
        try:
            metrics = await task
            if not metrics:
                return
                
            for cache_name, cache_metrics in metrics.items():
                hit_rate = cache_metrics.get("hit_rate", 0) * 100
                
                if hit_rate > 90:
                    await log(
                        f"Cache '{cache_name}' has high hit rate ({hit_rate:.1f}%). "
                        f"Consider increasing TTL to reduce backend load.", 
                        level="info"
                    )
                elif hit_rate < 50:
                    await log(
                        f"Cache '{cache_name}' has low hit rate ({hit_rate:.1f}%). "
                        f"Consider decreasing TTL for fresher data.", 
                        level="info"
                    )
        finally:
            self._pending_tasks.remove(task)
    
    async def cleanup(self):
        """Clean up analytics resources."""
        try:
            if not self._initialized:
                return
                
            # Stop monitoring
            await self.stop_monitoring()
            
            # Cancel all pending tasks
            if self._pending_tasks:
                for task in self._pending_tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                self._pending_tasks.clear()
            
            # Generate final report and save metrics
            task = asyncio.create_task(self.generate_performance_report())
            self._pending_tasks.add(task)
            try:
                await task
            finally:
                self._pending_tasks.remove(task)
            
            task = asyncio.create_task(self._save_metrics_history(await self._coordinator.get_metrics()))
            self._pending_tasks.add(task)
            try:
                await task
            finally:
                self._pending_tasks.remove(task)
            
            # Unregister from health monitoring
            from utils.health_monitor import global_health_monitor
            global_health_monitor.unregister_component("cache_analytics")
            
            self._initialized = False
            await log("Cache analytics cleaned up", level="info")
        except Exception as e:
            await log(f"Error cleaning up cache analytics: {e}", level="error")
            raise CacheError(f"Failed to cleanup cache analytics: {e}")

# Global instance
cache_analytics = None

async def get_cache_analytics() -> CacheAnalytics:
    """Get the global cache analytics instance."""
    global cache_analytics
    if not cache_analytics:
        cache_analytics = await CacheAnalytics.create(
            coordinator=cache_coordinator,
            auto_start=True
        )
    return cache_analytics

# Example warmup function for demonstration
async def example_warmup_function(keys: List[str]) -> Dict[str, Any]:
    """Example function to fetch data for cache warmup."""
    result = {}
    await asyncio.sleep(0.1)
    for key in keys:
        result[key] = f"Warmed up value for {key}"
    return result

# Register example warmup function (for demonstration)
# cache_analytics.register_warmup_function("query", example_warmup_function)

# Update the initialization function
async def initialize_cache_analytics(
    coordinator,
    auto_start: bool = True,
    report_interval: int = 3600,
    warmup_interval: int = 86400
):
    """Initialize cache analytics with the given coordinator."""
    global cache_analytics
    
    # Create analytics instance
    cache_analytics = await CacheAnalytics.create(
        coordinator=coordinator,
        auto_start=auto_start,
        report_interval=report_interval,
        warmup_interval=warmup_interval
    )
    
    return cache_analytics

def start_cache_analytics():
    """Start cache analytics monitoring."""
    if not cache_analytics:
        log("Cache analytics not initialized", level="error")
        return
    
    # Create a task for starting monitoring
    loop = asyncio.get_event_loop()
    loop.create_task(cache_analytics.start_monitoring()) 