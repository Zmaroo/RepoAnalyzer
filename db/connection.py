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
from db.retry_utils import DatabaseRetryManager, RetryConfig
from utils.shutdown import register_shutdown_handler
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
    
    @handle_async_errors(error_types=DatabaseError)
    async def get_connection(self) -> Connection:
        """Get a database connection optimized for AI operations."""
        if not self._initialized:
            await self.initialize()
        
        try:
            conn = await self._pool.acquire()
            # Set session parameters for AI operations
            await conn.execute("""
                SET SESSION statement_timeout = '300s';  -- 5 minutes for complex AI queries
                SET SESSION idle_in_transaction_session_timeout = '60s';
                SET SESSION application_name = 'ai_pattern_processor';
            """)
            return conn
        except Exception as e:
            error_msg = f"Failed to get database connection: {str(e)}"
            log(error_msg, level="error")
            raise ConnectionError(error_msg)
    
    @handle_async_errors(error_types=DatabaseError)
    async def get_session(self) -> Session:
        """Get a Neo4j session optimized for AI operations."""
        if not self._initialized:
            await self.initialize()
        
        try:
            session = self._neo4j_driver.session(
                default_access_mode="WRITE",
                fetch_size=1000,  # Optimize for large pattern operations
                database="neo4j"
            )
            return session
        except Exception as e:
            error_msg = f"Failed to get Neo4j session: {str(e)}"
            log(error_msg, level="error")
            raise ConnectionError(error_msg)
    
    async def cache_ai_result(self, key: str, value: Any) -> None:
        """Cache AI operation result with TTL."""
        self._ai_cache[key] = (value, time.time())
    
    async def get_cached_ai_result(self, key: str) -> Optional[Any]:
        """Get cached AI operation result if not expired."""
        if key in self._ai_cache:
            value, timestamp = self._ai_cache[key]
            if time.time() - timestamp <= self._cache_ttl:
                return value
            del self._ai_cache[key]
        return None
    
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
            
            # Clear AI cache
            self._ai_cache.clear()
            
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

# Create global connection manager instance
connection_manager = None

async def get_connection_manager() -> 'ConnectionManager':
    """Get the global connection manager instance."""
    global connection_manager
    if not connection_manager:
        connection_manager = await ConnectionManager.create()
    return connection_manager

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

# Export the connection manager only, not the driver
__all__ = ['connection_manager'] 