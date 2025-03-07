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
            "connection_times": []
        }
    
    async def _check_health(self) -> Dict[str, Any]:
        """Health check for connection manager."""
        # Calculate average connection time
        avg_conn_time = sum(self._metrics["connection_times"]) / len(self._metrics["connection_times"]) if self._metrics["connection_times"] else 0
        
        # Calculate health status
        status = ComponentStatus.HEALTHY
        details = {
            "metrics": {
                "total_connections": self._metrics["total_connections"],
                "active_connections": self._metrics["active_connections"],
                "error_rate": self._metrics["connection_errors"] / self._metrics["total_connections"] if self._metrics["total_connections"] > 0 else 0,
                "cache_hit_rate": self._metrics["cache_hits"] / (self._metrics["cache_hits"] + self._metrics["cache_misses"]) if (self._metrics["cache_hits"] + self._metrics["cache_misses"]) > 0 else 0,
                "avg_connection_time": avg_conn_time
            }
        }
        
        # Check for degraded conditions
        if details["metrics"]["error_rate"] > 0.1:
            status = ComponentStatus.DEGRADED
            details["reason"] = "High connection error rate"
        elif avg_conn_time > 1.0:
            status = ComponentStatus.DEGRADED
            details["reason"] = "High connection times"
        elif self._metrics["active_connections"] > PostgresConfig.max_pool_size * 0.8:
            status = ComponentStatus.DEGRADED
            details["reason"] = "Connection pool near capacity"
        
        return {
            "status": status,
            "details": details
        }
    
    async def initialize(self):
        """Initialize database connections and AI caching."""
        if self._initialized:
            return
        
        try:
            # Initialize PostgreSQL pool
            self._pool = await asyncpg.create_pool(
                user=PostgresConfig.user,
                password=PostgresConfig.password,
                database=PostgresConfig.database,
                host=PostgresConfig.host,
                port=PostgresConfig.port,
                min_size=PostgresConfig.min_pool_size,
                max_size=PostgresConfig.max_pool_size,
                timeout=PostgresConfig.connection_timeout
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
            
            # Start cache cleanup task
            self._cleanup_task = asyncio.create_task(self._cleanup_ai_cache())
            
            self._initialized = True
            log("Connection manager initialized with AI support", level="info")
        except Exception as e:
            error_msg = f"Failed to initialize connection manager: {str(e)}"
            log(error_msg, level="error")
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
            conn = await self._pool.acquire()
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
                error=False
            )
            
            return conn
        except Exception as e:
            self._metrics["connection_errors"] += 1
            error_msg = f"Failed to get database connection: {str(e)}"
            log(error_msg, level="error")
            
            # Update health status
            await global_health_monitor.update_component_status(
                "connection_manager",
                ComponentStatus.DEGRADED,
                error=True,
                details={"error": error_msg}
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
            
            self._initialized = False
            log("Connection manager cleaned up", level="info")
        except Exception as e:
            log(f"Error cleaning up connection manager: {str(e)}", level="error")

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