"""Cache analytics and optimization utilities.

This module provides tools to analyze cache performance, auto-tune TTL values,
and warm up caches with commonly accessed data for faster application performance.
"""

import asyncio
from typing import Dict, List, Optional, Any, Callable, Awaitable, Tuple
import time
from datetime import datetime, timedelta
import json
import os

# Import aiofiles for async file operations
try:
    import aiofiles
    AIOFILES_AVAILABLE = True
except ImportError:
    AIOFILES_AVAILABLE = False

from utils.logger import log
from utils.cache import cache_coordinator, UnifiedCache
from utils.error_handling import handle_async_errors, ErrorBoundary, CacheError
from utils.async_runner import submit_async_task, get_loop

# Type for cache warmup functions
WarmupFunc = Callable[[List[str]], Awaitable[Dict[str, Any]]]

class CacheAnalytics:
    """Cache analytics and optimization utilities."""
    
    def __init__(self):
        self._report_interval = 3600  # Default: hourly reports
        self._warmup_interval = 86400  # Default: daily warmup
        self._last_report_time = 0
        self._last_warmup_time = 0
        self._is_running = False
        self._task = None
        # Dictionary to store warmup functions for each cache
        self._warmup_funcs: Dict[str, WarmupFunc] = {}
        self._coordinator = None  # Will be set during initialization
    
    def register_warmup_function(self, cache_name: str, func: WarmupFunc) -> None:
        """Register a function to warm up a specific cache.
        
        Args:
            cache_name: Name of the cache to warm up
            func: Async function that takes a list of keys and returns dict of values
        """
        self._warmup_funcs[cache_name] = func
        log(f"Registered warmup function for cache: {cache_name}", level="info")
    
    async def start_monitoring(
        self, 
        report_interval: int = 3600, 
        warmup_interval: int = 86400
    ):
        """Start monitoring cache performance in the background.
        
        Args:
            report_interval: Seconds between performance reports
            warmup_interval: Seconds between cache warmup operations
        """
        if self._is_running:
            log("Cache monitoring is already running", level="warning")
            return
            
        self._report_interval = report_interval
        self._warmup_interval = warmup_interval
        self._is_running = True
        
        # Use submit_async_task for monitoring loop
        self._task = submit_async_task(self._monitoring_loop())
        log("Started cache performance monitoring", level="info")
    
    @handle_async_errors
    async def stop_monitoring(self):
        """Stop cache performance monitoring."""
        if not self._is_running:
            return
            
        self._is_running = False
        if self._task:
            await asyncio.wrap_future(self._task)
            self._task = None
            
        log("Stopped cache performance monitoring", level="info")
    
    @handle_async_errors
    async def _monitoring_loop(self):
        """Background loop for cache monitoring."""
        try:
            while self._is_running:
                current_time = time.time()
                
                # Submit monitoring tasks using async_runner
                if current_time - self._last_report_time >= self._report_interval:
                    report_future = submit_async_task(self.generate_performance_report())
                    await asyncio.wrap_future(report_future)
                    self._last_report_time = current_time
                
                if current_time - self._last_warmup_time >= self._warmup_interval:
                    warmup_future = submit_async_task(self.warmup_all_caches())
                    await asyncio.wrap_future(warmup_future)
                    self._last_warmup_time = current_time
                
                await asyncio.sleep(60)  # Check every minute
                
        except asyncio.CancelledError:
            log("Cache monitoring loop cancelled", level="info")
            raise
        except Exception as e:
            log(f"Error in monitoring loop: {e}", level="error")
            self._is_running = False
    
    @handle_async_errors
    async def generate_performance_report(self):
        """Generate a comprehensive cache performance report."""
        with ErrorBoundary("generating cache performance report"):
            # Get metrics from all caches
            metrics = await cache_coordinator.get_metrics()
            
            # No caches registered or no metrics
            if not metrics:
                log("No cache metrics available for reporting", level="info")
                return
                
            # Log summary
            total_hits = sum(m.get("hits", 0) for m in metrics.values())
            total_misses = sum(m.get("misses", 0) for m in metrics.values())
            total_ops = total_hits + total_misses
            
            if total_ops > 0:
                overall_hit_rate = (total_hits / total_ops) * 100
            else:
                overall_hit_rate = 0
                
            log(f"Cache Performance Summary:\n"
                f"Overall hit rate: {overall_hit_rate:.1f}%\n"
                f"Total cache operations: {total_ops}\n"
                f"Total hits: {total_hits}, Total misses: {total_misses}",
                level="info")
            
            # Log detailed metrics for each cache
            await cache_coordinator.log_metrics()
            
            # Save metrics to file for historical analysis
            if total_ops > 0:  # Only save if we have meaningful data
                await self._save_metrics_history(metrics)
                
    @handle_async_errors
    async def _save_metrics_history(self, metrics: Dict):
        """Save metrics to a historical data file."""
        with ErrorBoundary("saving cache metrics history"):
            # Skip if aiofiles not available
            if not AIOFILES_AVAILABLE:
                log("Cannot save metrics history: aiofiles not installed", level="warning")
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
                await f.write(json.dumps(record) + "\n")
                
    @handle_async_errors
    async def warmup_all_caches(self):
        """Warm up all registered caches with their most popular keys."""
        caches = cache_coordinator._caches
        if not caches:
            return
        
        # Submit warmup tasks using async_runner
        warmup_futures = []
        for name, cache in caches.items():
            if not isinstance(cache, UnifiedCache):
                continue
                
            log(f"Auto-warming up cache: {name}", level="info")
            future = submit_async_task(self._warmup_cache_if_possible(name, cache))
            warmup_futures.append(future)
        
        # Wait for all warmup tasks to complete
        if warmup_futures:
            await asyncio.gather(*[asyncio.wrap_future(f) for f in warmup_futures], return_exceptions=True)
    
    @handle_async_errors
    async def _warmup_cache_if_possible(self, cache_name: str, cache: UnifiedCache):
        """Attempt to warm up a cache if it has a registered warmup function."""
        with ErrorBoundary(f"warming up cache {cache_name}"):
            # Check if we have a registered warmup function
            warmup_func = self._warmup_funcs.get(cache_name)
            if not warmup_func:
                log(f"No warmup function registered for cache: {cache_name}", level="debug")
                return
                
            # Get popular keys to warm up
            popular_keys = await cache._usage_tracker.get_popular_keys(limit=50)
            if not popular_keys:
                log(f"No popular keys found for cache: {cache_name}", level="debug")
                return
                
            keys = [k for k, _ in popular_keys]
            log(f"Warming up {len(keys)} popular keys for cache: {cache_name}", level="info")
            
            # Use the registered warmup function
            await cache.warmup_from_function(keys, warmup_func)
            
    @handle_async_errors
    async def warmup_cache(self, cache_name: str, keys: List[str]) -> bool:
        """
        Manually trigger cache warmup for specific keys.
        
        Args:
            cache_name: Name of the cache to warm up
            keys: List of keys to warm up
            
        Returns:
            bool: True if successful, False otherwise
        """
        if cache_name not in cache_coordinator._caches:
            log(f"Cache not found: {cache_name}", level="error")
            return False
            
        cache = cache_coordinator._caches[cache_name]
        if not isinstance(cache, UnifiedCache):
            log(f"Invalid cache type: {cache_name}", level="error")
            return False
            
        warmup_func = self._warmup_funcs.get(cache_name)
        if not warmup_func:
            log(f"No warmup function registered for cache: {cache_name}", level="error")
            return False
        
        with ErrorBoundary(f"warming up cache {cache_name}"):
            try:
                await cache.warmup_from_function(keys, warmup_func)
                log(f"Successfully warmed up {len(keys)} keys for cache: {cache_name}", level="info")
                return True
            except (ConnectionError, TimeoutError) as e:
                log(f"Network error warming up cache {cache_name}: {e}", level="error")
                return False
            except CacheError as e:
                log(f"Cache error warming up cache {cache_name}: {e}", level="error")
                return False
            except Exception as e:
                log(f"Unexpected error warming up cache {cache_name}: {e}", level="error")
                return False
    
    async def optimize_ttl_values(self):
        """Analyze cache usage patterns and suggest optimal TTL values."""
        metrics = await cache_coordinator.get_metrics()
        if not metrics:
            return
            
        for cache_name, cache_metrics in metrics.items():
            hit_rate = cache_metrics.get("hit_rate", 0) * 100
            
            # Example optimization logic:
            # - High hit rate (>90%): Increase TTL to reduce computation
            # - Low hit rate (<50%): Decrease TTL to ensure fresher data
            
            if hit_rate > 90:
                log(f"Cache '{cache_name}' has high hit rate ({hit_rate:.1f}%). "
                    f"Consider increasing TTL to reduce backend load.", 
                    level="info")
            elif hit_rate < 50:
                log(f"Cache '{cache_name}' has low hit rate ({hit_rate:.1f}%). "
                    f"Consider decreasing TTL for fresher data.", 
                    level="info")

    async def cleanup(self):
        """Clean up analytics resources."""
        try:
            await self.stop_monitoring()
            # Submit final tasks using async_runner
            report_future = submit_async_task(self.generate_performance_report())
            metrics_future = submit_async_task(self._save_metrics_history(await cache_coordinator.get_metrics()))
            await asyncio.gather(
                asyncio.wrap_future(report_future),
                asyncio.wrap_future(metrics_future)
            )
        except Exception as e:
            log(f"Error cleaning up cache analytics: {e}", level="error")

# Create global instance
cache_analytics = CacheAnalytics()

# Example warmup function for demonstration
async def example_warmup_function(keys: List[str]) -> Dict[str, Any]:
    """Example function to fetch data for cache warmup.
    
    In a real application, this would query a database or API.
    
    Args:
        keys: List of cache keys to fetch data for
        
    Returns:
        Dict mapping keys to their values
    """
    result = {}
    # Simulate fetching data
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
    """Initialize cache analytics with coordinator.
    
    Args:
        coordinator: The cache coordinator instance
        auto_start: Whether to automatically start monitoring
        report_interval: Seconds between performance reports
        warmup_interval: Seconds between cache warmup operations
    """
    # Initialize analytics with the coordinator
    cache_analytics._coordinator = coordinator
    
    if auto_start:
        await cache_analytics.start_monitoring(
            report_interval=report_interval,
            warmup_interval=warmup_interval
        )
    return cache_analytics

# Remove the old start function since it's replaced by initialize_cache_analytics
def start_cache_analytics():
    """Deprecated: Use initialize_cache_analytics instead."""
    from utils.logger import log
    log("start_cache_analytics is deprecated, use initialize_cache_analytics instead",
        level="warning") 