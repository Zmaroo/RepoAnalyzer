"""Database connection management.

This module provides centralized database connection management for all databases:
1. Connection pooling and lifecycle management
2. Health checks and monitoring
3. Proper async handling and cleanup
4. Error recovery and reconnection
"""

import asyncio
import asyncpg
from typing import Optional, Set, Dict, Any
from neo4j import AsyncGraphDatabase
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

class ConnectionManager:
    """Manages all database connections and their lifecycle."""
    
    def __init__(self):
        """Private constructor - use create() instead."""
        # Neo4j
        self._driver = None
        self._lock = asyncio.Lock()
        self._pending_tasks: Set[asyncio.Task] = set()
        self._health_check_interval = 60  # seconds
        self._health_check_task = None
        self._retry_manager = None
        self._initialized = False
        
        # PostgreSQL
        self._pool = None
        self._pg_initialized = False
    
    async def ensure_initialized(self):
        """Ensure the instance is properly initialized before use."""
        if not self._initialized:
            raise ConnectionError("ConnectionManager not initialized. Use create() to initialize.")
        if not self._pg_initialized:
            raise ConnectionError("PostgreSQL not initialized. Use create() to initialize.")
        if not self._driver:
            raise ConnectionError("Neo4j driver not initialized")
        return True
    
    @classmethod
    async def create(cls) -> 'ConnectionManager':
        """Async factory method to create and initialize a ConnectionManager instance."""
        instance = cls()
        try:
            async with AsyncErrorBoundary(
                operation_name="connection manager initialization",
                error_types=(ConnectionError, DatabaseError),
                severity=ErrorSeverity.CRITICAL
            ):
                # Initialize retry manager
                from db.retry_utils import DatabaseRetryManager, RetryConfig
                instance._retry_manager = await DatabaseRetryManager.create(
                    RetryConfig(max_retries=5, base_delay=1.0, max_delay=30.0)
                )
                
                # Initialize Neo4j
                await instance.initialize()
                
                # Initialize PostgreSQL
                await instance.initialize_postgres()
                
                # Register shutdown handler
                register_shutdown_handler(instance.cleanup)
                
                # Initialize health monitoring
                from utils.health_monitor import global_health_monitor
                global_health_monitor.register_component("connection_manager")
                
                instance._initialized = True
                await log("Connection manager initialized", level="info")
                return instance
        except Exception as e:
            await log(f"Error initializing connection manager: {e}", level="error")
            # Cleanup on initialization failure
            await instance.cleanup()
            raise ConnectionError(f"Failed to initialize connection manager: {e}")
    
    @property
    def driver(self):
        """Get the Neo4j driver instance."""
        if not self._initialized:
            raise ConnectionError("Neo4j driver not initialized. Call initialize() first.")
        if not self._driver:
            raise ConnectionError("Neo4j driver not available")
        return self._driver
    
    @property
    def pool(self):
        """Get the PostgreSQL connection pool."""
        if not self._pg_initialized:
            raise ConnectionError("PostgreSQL pool not initialized. Call initialize_postgres() first.")
        if not self._pool:
            raise ConnectionError("PostgreSQL pool not available")
        return self._pool
    
    @handle_async_errors(error_types=(Neo4jError, ConnectionError))
    async def initialize(self) -> None:
        """Initialize the Neo4j database connection."""
        async with self._lock:
            if self._initialized:
                return
            
            try:
                # Create driver instance
                self._driver = AsyncGraphDatabase.driver(
                    Neo4jConfig.uri,
                    auth=(Neo4jConfig.user, Neo4jConfig.password),
                    database=Neo4jConfig.database,
                    max_connection_lifetime=Neo4jConfig.max_connection_lifetime,
                    max_connection_pool_size=Neo4jConfig.max_connection_pool_size,
                    connection_timeout=Neo4jConfig.connection_timeout
                )
                
                # Verify connection
                await self._verify_connectivity()
                
                # Start health check
                self._start_health_check()
                
                self._initialized = True
                
                log("Neo4j connection initialized", level="info", context={
                    "uri": Neo4jConfig.uri,
                    "database": Neo4jConfig.database
                })
            except Exception as e:
                self._driver = None
                self._initialized = False
                log("Failed to initialize Neo4j connection", level="error", context={
                    "error": str(e)
                })
                raise ConnectionError(f"Failed to initialize Neo4j connection: {str(e)}")
    
    @handle_async_errors(error_types=(PostgresError, ConnectionError))
    async def initialize_postgres(self) -> None:
        """Initialize the PostgreSQL connection pool."""
        async with self._lock:
            if self._pg_initialized:
                return
            
            try:
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
                
                # Test connection
                async with self._pool.acquire() as conn:
                    await conn.execute('SELECT 1')
                
                self._pg_initialized = True
                
                log("PostgreSQL pool initialized", level="info", context={
                    "host": PostgresConfig.host,
                    "database": PostgresConfig.database,
                    "pool_size": self._pool.get_size()
                })
            except Exception as e:
                self._pool = None
                self._pg_initialized = False
                log("Failed to initialize PostgreSQL pool", level="error", context={
                    "error": str(e)
                })
                raise ConnectionError(f"Failed to initialize PostgreSQL pool: {str(e)}")
    
    async def _verify_connectivity(self) -> None:
        """Verify database connectivity with a test query."""
        async with self.driver.session() as session:
            await session.run("RETURN 1")
    
    def _start_health_check(self) -> None:
        """Start periodic health check."""
        if not self._health_check_task or self._health_check_task.done():
            self._health_check_task = asyncio.create_task(self._health_check_loop())
    
    async def _health_check_loop(self) -> None:
        """Periodic health check loop."""
        try:
            while True:
                try:
                    # Check Neo4j
                    await self._verify_connectivity()
                    log("Neo4j health check passed", level="debug")
                except Exception as e:
                    log("Neo4j health check failed", level="error", context={
                        "error": str(e)
                    })
                    # Try to reconnect
                    await self._handle_connection_failure()
                
                try:
                    # Check PostgreSQL if initialized
                    if self._pg_initialized:
                        async with self._pool.acquire() as conn:
                            await conn.execute('SELECT 1')
                            log("PostgreSQL health check passed", level="debug")
                except Exception as e:
                    log("PostgreSQL health check failed", level="error", context={
                        "error": str(e)
                    })
                    # Try to reconnect
                    await self._handle_postgres_failure()
                
                # Wait for next check
                await asyncio.sleep(self._health_check_interval)
        finally:
            if self._health_check_task in self._pending_tasks:
                self._pending_tasks.remove(self._health_check_task)
    
    async def _handle_connection_failure(self) -> None:
        """Handle Neo4j connection failure with retry logic."""
        async with self._lock:
            try:
                # Close existing connection
                if self._driver:
                    await self._driver.close()
                    self._driver = None
                    self._initialized = False
                
                # Try to reconnect
                await self._retry_manager.execute_with_retry(self.initialize)
            except Exception as e:
                log(f"Failed to recover Neo4j connection: {e}", level="error")
    
    async def _handle_postgres_failure(self) -> None:
        """Handle PostgreSQL connection failure with retry logic."""
        async with self._lock:
            try:
                # Close existing pool
                if self._pool:
                    await self._pool.close()
                    self._pool = None
                    self._pg_initialized = False
                
                # Try to reconnect
                await self._retry_manager.execute_with_retry(self.initialize_postgres)
            except Exception as e:
                log(f"Failed to recover PostgreSQL connection: {e}", level="error")
    
    @handle_async_errors(error_types=(Neo4jError, ConnectionError))
    async def get_session(self):
        """Get a Neo4j database session."""
        if not self._initialized:
            await self.initialize()
        return await self.driver.session()
    
    @handle_async_errors(error_types=(PostgresError, ConnectionError))
    async def get_postgres_connection(self):
        """Get a PostgreSQL connection from the pool."""
        if not self._pg_initialized:
            await self.initialize_postgres()
        return await self.pool.acquire()
    
    @handle_async_errors(error_types=(PostgresError, ConnectionError))
    async def release_postgres_connection(self, conn):
        """Release a PostgreSQL connection back to the pool."""
        await self.pool.release(conn)
    
    async def cleanup(self) -> None:
        """Close all database connections and cleanup resources."""
        async with self._lock:
            try:
                if not self._initialized:
                    return
                    
                # Stop health check
                if self._health_check_task and not self._health_check_task.done():
                    self._health_check_task.cancel()
                    try:
                        await self._health_check_task
                    except asyncio.CancelledError:
                        pass
                
                # Cancel all pending tasks
                if self._pending_tasks:
                    for task in self._pending_tasks:
                        if not task.done():
                            task.cancel()
                    await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                    self._pending_tasks.clear()
                
                # Close Neo4j driver
                if self._driver:
                    await self._driver.close()
                    self._driver = None
                    self._initialized = False
                
                # Close PostgreSQL pool
                if self._pool:
                    await self._pool.close()
                    self._pool = None
                    self._pg_initialized = False
                
                # Clean up retry manager
                if self._retry_manager:
                    await self._retry_manager.cleanup()
                
                # Unregister from health monitoring
                from utils.health_monitor import global_health_monitor
                global_health_monitor.unregister_component("connection_manager")
                
                await log("All database connections closed", level="info")
            except Exception as e:
                await log(f"Error cleaning up connection manager: {e}", level="error")
                raise ConnectionError(f"Failed to cleanup connection manager: {e}")

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