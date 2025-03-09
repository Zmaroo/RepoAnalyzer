"""Database connection management.

This module provides centralized database connection management for all databases:
1. Connection pooling and lifecycle management
2. Health checks and monitoring
3. Proper async handling and cleanup
4. Error recovery and reconnection
"""

import asyncio
import asyncpg
from asyncpg import Connection
from typing import Optional, Set, Dict, Any
from neo4j import AsyncGraphDatabase, Session
from config import Neo4jConfig, PostgresConfig
from utils.logger import log
from utils.error_handling import (
    handle_async_errors,
    DatabaseError,
    Neo4jError,
    ConnectionError,
    AsyncErrorBoundary,
    ErrorSeverity,
    PostgresError
)
from utils.async_runner import submit_async_task, get_loop
from db.retry_utils import RetryManager, RetryConfig
from utils.shutdown import register_shutdown_handler
from utils.cache import UnifiedCache, cache_coordinator
from utils.health_monitor import global_health_monitor, ComponentStatus
from utils.request_cache import cached_in_request, request_cache_context
import time

class ConnectionManager:
    """Manages database connections with AI operation support."""
    
    def __init__(self):
        self._pool = None
        self._neo4j_driver = None
        self._initialized = False
        self._ai_cache = {}  # Cache for AI operation results
        self._cache_ttl = 3600  # 1 hour TTL for AI results
        self._pending_tasks = set()
        self._cleanup_task = None
        self._connection_cache = UnifiedCache("connection_pool")
        self._metrics = {
            "total_connections": 0,
            "active_connections": 0,
            "connection_errors": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "connection_times": [],
            "pool_size": 0,
            "pool_usage": 0.0,
            "connection_wait_time": []
        }
        self._pool_monitor_task = None
        self._pool_scaling_task = None
        self._lock = asyncio.Lock()
        self._usage_history = []
        self._usage_window = 300  # 5 minutes
        self._prediction_enabled = True
        self._last_prediction = 0
        self._prediction_interval = 60  # Predict every minute
    
    async def _predict_pool_usage(self) -> float:
        """Predict future pool usage based on recent history."""
        if not self._usage_history:
            return 0.0
        
        # Clean old history
        current_time = time.time()
        self._usage_history = [
            (t, u) for t, u in self._usage_history 
            if current_time - t <= self._usage_window
        ]
        
        if not self._usage_history:
            return 0.0
        
        # Calculate trend
        times, usages = zip(*self._usage_history)
        time_diffs = [t - times[0] for t in times]
        
        # Simple linear regression
        n = len(time_diffs)
        sum_x = sum(time_diffs)
        sum_y = sum(usages)
        sum_xy = sum(x * y for x, y in zip(time_diffs, usages))
        sum_xx = sum(x * x for x in time_diffs)
        
        try:
            slope = (n * sum_xy - sum_x * sum_y) / (n * sum_xx - sum_x * sum_x)
            intercept = (sum_y - slope * sum_x) / n
            
            # Predict usage in next interval
            future_time = self._prediction_interval
            predicted_usage = slope * future_time + intercept
            
            # Bound prediction
            return max(0.0, min(1.0, predicted_usage))
        except ZeroDivisionError:
            return self._metrics["pool_usage"]
    
    async def _monitor_pool(self):
        """Monitor connection pool health and metrics."""
        while True:
            try:
                if not self._pool:
                    await asyncio.sleep(5)
                    continue
                
                # Get pool metrics
                async with self._lock:
                    pool_size = self._pool.get_size()
                    active_connections = self._pool.get_active_size()
                    
                    self._metrics["pool_size"] = pool_size
                    current_usage = active_connections / pool_size if pool_size > 0 else 0
                    self._metrics["pool_usage"] = current_usage
                    
                    # Record usage for prediction
                    current_time = time.time()
                    self._usage_history.append((current_time, current_usage))
                    
                    # Check if it's time for prediction
                    if self._prediction_enabled and current_time - self._last_prediction >= self._prediction_interval:
                        predicted_usage = await self._predict_pool_usage()
                        self._last_prediction = current_time
                        
                        # Pre-emptively scale based on prediction
                        if predicted_usage > 0.7:  # Predicted high usage
                            await self._scale_pool_up()
                        elif predicted_usage < 0.3:  # Predicted low usage
                            await self._scale_pool_down()
                    else:
                        # Regular scaling based on current usage
                        if self._metrics["pool_usage"] > 0.8:
                            await self._scale_pool_up()
                        elif self._metrics["pool_usage"] < 0.3:
                            await self._scale_pool_down()
                    
                    # Update health status with prediction info
                    await global_health_monitor.update_component_status(
                        "connection_manager",
                        ComponentStatus.HEALTHY if self._metrics["pool_usage"] < 0.9 else ComponentStatus.DEGRADED,
                        details={
                            "pool_size": pool_size,
                            "active_connections": active_connections,
                            "pool_usage": self._metrics["pool_usage"],
                            "predicted_usage": predicted_usage if self._prediction_enabled else None,
                            "avg_wait_time": sum(self._metrics["connection_wait_time"]) / len(self._metrics["connection_wait_time"]) if self._metrics["connection_wait_time"] else 0
                        }
                    )
                
                await asyncio.sleep(5)  # Check every 5 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                await log(f"Error monitoring connection pool: {e}", level="error")
                await asyncio.sleep(10)  # Back off on error
    
    async def _scale_pool_up(self):
        """Scale up the connection pool."""
        async with self._lock:
            current_size = self._pool.get_size()
            max_size = PostgresConfig.max_pool_size
            
            if current_size < max_size:
                # Calculate new size based on prediction if enabled
                if self._prediction_enabled:
                    predicted_usage = await self._predict_pool_usage()
                    needed_size = int(current_size * (predicted_usage + 0.5))  # Add 50% buffer
                    new_size = min(max(needed_size, current_size * 2), max_size)
                else:
                    new_size = min(current_size * 2, max_size)
                
                try:
                    await self._pool.set_size(new_size)
                    await log(
                        f"Scaled connection pool up from {current_size} to {new_size}",
                        level="info",
                        context={
                            "predicted_usage": predicted_usage if self._prediction_enabled else None,
                            "current_usage": self._metrics["pool_usage"]
                        }
                    )
                except Exception as e:
                    await log(f"Error scaling connection pool up: {e}", level="error")
    
    async def _scale_pool_down(self):
        """Scale down the connection pool."""
        async with self._lock:
            current_size = self._pool.get_size()
            min_size = PostgresConfig.min_pool_size
            
            if current_size > min_size:
                # Calculate new size based on prediction if enabled
                if self._prediction_enabled:
                    predicted_usage = await self._predict_pool_usage()
                    needed_size = int(current_size * (predicted_usage + 0.3))  # Add 30% buffer
                    new_size = max(min(needed_size, current_size // 2), min_size)
                else:
                    new_size = max(current_size // 2, min_size)
                
                try:
                    await self._pool.set_size(new_size)
                    await log(
                        f"Scaled connection pool down from {current_size} to {new_size}",
                        level="info",
                        context={
                            "predicted_usage": predicted_usage if self._prediction_enabled else None,
                            "current_usage": self._metrics["pool_usage"]
                        }
                    )
                except Exception as e:
                    await log(f"Error scaling connection pool down: {e}", level="error")
    
    async def initialize(self):
        """Initialize database connections and AI caching."""
        if self._initialized:
            return
        
        try:
            # Initialize PostgreSQL pool with monitoring
            self._pool = await asyncpg.create_pool(
                user=PostgresConfig.user,
                password=PostgresConfig.password,
                database=PostgresConfig.database,
                host=PostgresConfig.host,
                port=PostgresConfig.port,
                min_size=PostgresConfig.min_pool_size,
                max_size=PostgresConfig.max_pool_size,
                timeout=PostgresConfig.connection_timeout,
                command_timeout=PostgresConfig.command_timeout,
                setup=["SET application_name = 'repo_analyzer'"]
            )
            
            # Initialize Neo4j driver with AI operation configs
            self._neo4j_driver = AsyncGraphDatabase.driver(
                Neo4jConfig.uri,
                auth=(Neo4jConfig.user, Neo4jConfig.password),
                max_connection_lifetime=Neo4jConfig.max_connection_lifetime,
                max_connection_pool_size=Neo4jConfig.max_connection_pool_size,
                connection_acquisition_timeout=Neo4jConfig.connection_timeout
            )
            
            # Register cache with coordinator
            await cache_coordinator.register_cache("connection_pool", self._connection_cache)
            
            # Register with health monitor
            global_health_monitor.register_component(
                "connection_manager",
                health_check=self._check_health
            )
            
            # Start monitoring tasks
            self._pool_monitor_task = asyncio.create_task(self._monitor_pool())
            self._pending_tasks.add(self._pool_monitor_task)
            
            # Start cache cleanup task
            self._cleanup_task = asyncio.create_task(self._cleanup_ai_cache())
            self._pending_tasks.add(self._cleanup_task)
            
            self._initialized = True
            await log("Connection manager initialized with AI support", level="info")
        except Exception as e:
            error_msg = f"Failed to initialize connection manager: {str(e)}"
            await log(error_msg, level="error")
            raise ConnectionError(error_msg)
    
    async def _cleanup_ai_cache(self):
        """Periodically clean up expired AI cache entries."""
        while True:
            try:
                current_time = time.time()
                expired_keys = [
                    key for key, (value, timestamp) in self._ai_cache.items()
                    if current_time - timestamp > self._cache_ttl
                ]
                
                for key in expired_keys:
                    del self._ai_cache[key]
                
                await asyncio.sleep(300)  # Clean up every 5 minutes
            except asyncio.CancelledError:
                break
            except Exception as e:
                log(f"Error in AI cache cleanup: {str(e)}", level="error")
                await asyncio.sleep(60)  # Retry after 1 minute on error
    
    @cached_in_request
    async def get_connection(self) -> Connection:
        """Get a database connection optimized for AI operations."""
        if not self._initialized:
            await self.initialize()
        
        start_time = time.time()
        self._metrics["total_connections"] += 1
        
        # Check connection cache first
        cache_key = f"connection:{asyncio.current_task().get_name()}"
        cached_conn = await self._connection_cache.get_async(cache_key)
        if cached_conn:
            self._metrics["cache_hits"] += 1
            return cached_conn
        
        self._metrics["cache_misses"] += 1
        
        try:
            # Record wait time start
            wait_start = time.time()
            
            conn = await self._pool.acquire()
            
            # Record wait time
            wait_time = time.time() - wait_start
            self._metrics["connection_wait_time"].append(wait_time)
            
            self._metrics["active_connections"] += 1
            
            # Set session parameters for AI operations
            await conn.execute("""
                SET SESSION statement_timeout = '300s';  -- 5 minutes for complex AI queries
                SET SESSION idle_in_transaction_session_timeout = '60s';
                SET SESSION application_name = 'ai_pattern_processor';
            """)
            
            # Cache the connection
            await self._connection_cache.set_async(cache_key, conn)
            
            # Update metrics
            conn_time = time.time() - start_time
            self._metrics["connection_times"].append(conn_time)
            
            # Update health status
            await global_health_monitor.update_component_status(
                "connection_manager",
                ComponentStatus.HEALTHY,
                response_time=conn_time * 1000,  # Convert to ms
                error=False,
                details={
                    "wait_time": wait_time * 1000,  # Convert to ms
                    "pool_usage": self._metrics["pool_usage"]
                }
            )
            
            return conn
        except Exception as e:
            self._metrics["connection_errors"] += 1
            error_msg = f"Failed to get database connection: {str(e)}"
            await log(error_msg, level="error")
            
            # Update health status
            await global_health_monitor.update_component_status(
                "connection_manager",
                ComponentStatus.DEGRADED,
                error=True,
                details={
                    "error": error_msg,
                    "pool_usage": self._metrics["pool_usage"]
                }
            )
            
            raise ConnectionError(error_msg)
    
    async def release_connection(self, conn: Connection) -> None:
        """Release a database connection back to the pool."""
        if not self._initialized:
            return
        
        try:
            await self._pool.release(conn)
            self._metrics["active_connections"] -= 1
            
            # Remove from cache
            cache_key = f"connection:{asyncio.current_task().get_name()}"
            await self._connection_cache.clear_pattern_async(cache_key)
        except Exception as e:
            log(f"Error releasing connection: {e}", level="error")
    
    async def cleanup(self):
        """Clean up all resources."""
        try:
            # Cancel monitoring tasks
            if self._pool_monitor_task and not self._pool_monitor_task.done():
                self._pool_monitor_task.cancel()
                try:
                    await self._pool_monitor_task
                except asyncio.CancelledError:
                    pass
            
            # Cancel cache cleanup task
            if self._cleanup_task and not self._cleanup_task.done():
                self._cleanup_task.cancel()
                try:
                    await self._cleanup_task
                except asyncio.CancelledError:
                    pass
            
            # Close all connections
            if self._pool:
                await self._pool.close()
            
            if self._neo4j_driver:
                await self._neo4j_driver.close()
            
            # Clear caches
            self._ai_cache.clear()
            await self._connection_cache.clear_async()
            await cache_coordinator.unregister_cache("connection_pool")
            
            # Unregister from health monitoring
            global_health_monitor.unregister_component("connection_manager")
            
            # Cancel any remaining tasks
            if self._pending_tasks:
                for task in self._pending_tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                self._pending_tasks.clear()
            
            self._initialized = False
            await log("Connection manager cleaned up", level="info")
        except Exception as e:
            await log(f"Error cleaning up connection manager: {str(e)}", level="error")

# Create singleton instance
connection_manager = ConnectionManager()

# Register cleanup handler
register_shutdown_handler(connection_manager.cleanup)

# Export with proper async handling
async def get_connection_manager() -> ConnectionManager:
    """Get the connection manager instance.
    
    Returns:
        ConnectionManager: The singleton connection manager instance
    """
    if not connection_manager._initialized:
        await connection_manager.initialize()
    return connection_manager

# Export the connection manager and getter
__all__ = ['connection_manager', 'get_connection_manager']

async def initialize_postgres():
    """Initialize PostgreSQL connection pool."""
    manager = await get_connection_manager()
    await manager.initialize_postgres()

async def initialize():
    """Initialize Neo4j connection."""
    manager = await get_connection_manager()
    await manager.initialize()

async def cleanup():
    """Clean up all database connections."""
    manager = await get_connection_manager()
    await manager.cleanup() 