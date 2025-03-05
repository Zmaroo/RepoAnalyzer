"""[6.4] Multi-database transaction coordination.

This module provides centralized transaction management across multiple databases:
1. Transaction lifecycle management
2. Cache invalidation coordination
3. Error handling and recovery
4. Resource cleanup
"""

import asyncio
from contextlib import asynccontextmanager
from typing import Optional, Set, Dict, Any
from utils.logger import log
from db.connection import connection_manager
from utils.cache import cache_coordinator
from utils.error_handling import (
    handle_async_errors, 
    AsyncErrorBoundary, 
    ErrorBoundary, 
    ErrorSeverity,
    PostgresError, 
    Neo4jError, 
    TransactionError, 
    CacheError,
    ConnectionError
)
from db.retry_utils import DatabaseRetryManager, RetryConfig
from utils.async_runner import submit_async_task, get_loop
from utils.app_init import register_shutdown_handler

class TransactionCoordinator:
    """Coordinates transactions across different databases and caches."""
    
    def __init__(self):
        self.pg_conn = None
        self.pg_transaction = None
        self.neo4j_session = None
        self.neo4j_transaction = None
        self._lock = asyncio.Lock()
        self._affected_repos = set()  # Track affected repos
        self._affected_caches = set()  # Track which caches need invalidation
        self._pending_tasks: Set[asyncio.Future] = set()  # Track pending async tasks
        self._retry_manager = DatabaseRetryManager(
            RetryConfig(max_retries=3, base_delay=1.0, max_delay=10.0)
        )
        self._initialized = False
        register_shutdown_handler(self.cleanup)
    
    async def initialize(self):
        """Initialize the transaction coordinator."""
        if not self._initialized:
            try:
                # Any coordinator-specific initialization can go here
                self._initialized = True
                log("Transaction coordinator initialized", level="info")
            except Exception as e:
                log(f"Error initializing transaction coordinator: {e}", level="error")
                raise
    
    async def track_repo_change(self, repo_id: int):
        """Track which repos are modified in this transaction."""
        if not self._initialized:
            await self.initialize()
        self._affected_repos.add(repo_id)
    
    async def track_cache_invalidation(self, cache_name: str):
        """Track which caches need invalidation."""
        if not self._initialized:
            await self.initialize()
        self._affected_caches.add(cache_name)
    
    @handle_async_errors(error_types=(PostgresError, Neo4jError, TransactionError, CacheError))
    async def _invalidate_caches(self):
        """Coordinated cache invalidation."""
        if not self._initialized:
            await self.initialize()
            
        try:
            for repo_id in self._affected_repos:
                async with AsyncErrorBoundary("cache invalidation", error_types=CacheError):
                    patterns = [f"repo:{repo_id}:*", f"graph:{repo_id}:*"]
                    for pattern in patterns:
                        future = submit_async_task(cache_coordinator.invalidate_pattern(pattern))
                        self._pending_tasks.add(future)
                        try:
                            await asyncio.wrap_future(future)
                        finally:
                            self._pending_tasks.remove(future)
        except Exception as e:
            raise CacheError(f"Cache invalidation failed: {str(e)}")
    
    async def cleanup(self):
        """Clean up all resources."""
        try:
            # Clean up any pending tasks
            if self._pending_tasks:
                for task in self._pending_tasks:
                    task.cancel()
                await asyncio.gather(*[asyncio.wrap_future(f) for f in self._pending_tasks], return_exceptions=True)
                self._pending_tasks.clear()
            
            # Clean up retry manager
            await self._retry_manager.cleanup()
            
            # Clean up any active transactions
            if self.pg_transaction and not self.pg_transaction.is_closed():
                await self.pg_transaction.rollback()
            if self.neo4j_transaction and not self.neo4j_transaction.closed():
                await self.neo4j_transaction.rollback()
            
            # Clean up connections
            if self.pg_conn:
                await connection_manager.release_postgres_connection(self.pg_conn)
            if self.neo4j_session:
                await self.neo4j_session.close()
            
            self._initialized = False
            log("Transaction coordinator cleaned up", level="info")
        except Exception as e:
            log(f"Error cleaning up transaction coordinator: {e}", level="error")

# Create global transaction coordinator instance
_transaction_coordinator = TransactionCoordinator()

@asynccontextmanager
@handle_async_errors(error_types=(PostgresError, Neo4jError, TransactionError, CacheError, ConnectionError, Exception))
async def transaction_scope(invalidate_cache: bool = True):
    """Context manager for coordinated transactions."""
    if not _transaction_coordinator._initialized:
        await _transaction_coordinator.initialize()
        
    try:
        async with _transaction_coordinator._lock:
            try:
                # Ensure connections are initialized
                await connection_manager.initialize_postgres()
                await connection_manager.initialize()
                
                # Start transactions
                await _transaction_coordinator._start_postgres()
                await _transaction_coordinator._start_neo4j()
                
                try:
                    yield _transaction_coordinator
                    
                    # Commit transactions
                    if _transaction_coordinator.pg_transaction:
                        await _transaction_coordinator.pg_transaction.commit()
                    if _transaction_coordinator.neo4j_transaction:
                        await _transaction_coordinator.neo4j_transaction.commit()
                    
                    # Handle cache invalidation
                    if invalidate_cache:
                        await _transaction_coordinator._invalidate_caches()
                except Exception as e:
                    log(f"Transaction scope error: {e}", level="error")
                    # Rollback will happen in cleanup
                    raise TransactionError(f"Transaction scope failed: {str(e)}")
            except (PostgresError, Neo4jError, TransactionError, CacheError, ConnectionError, Exception) as e:
                log(f"Error in transaction_scope: {e}", level="error")
                # Record the error for audit purposes
                from utils.error_handling import ErrorAudit
                future = submit_async_task(ErrorAudit.record_error(
                    e, 
                    "transaction_scope", 
                    (PostgresError, Neo4jError, TransactionError, CacheError, ConnectionError, Exception),
                    severity=ErrorSeverity.ERROR
                ))
                _transaction_coordinator._pending_tasks.add(future)
                try:
                    await asyncio.wrap_future(future)
                finally:
                    _transaction_coordinator._pending_tasks.remove(future)
                raise
    finally:
        # Ensure resources are cleaned up
        await _transaction_coordinator.cleanup()

# Register cleanup handler
async def cleanup_transaction():
    """Cleanup transaction coordinator resources."""
    try:
        await _transaction_coordinator.cleanup()
        log("Transaction coordinator resources cleaned up", level="info")
    except Exception as e:
        log(f"Error cleaning up transaction coordinator resources: {e}", level="error")

register_shutdown_handler(cleanup_transaction) 