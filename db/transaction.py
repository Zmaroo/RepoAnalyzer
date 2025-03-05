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
from utils.async_runner import submit_async_task

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
        
    async def track_repo_change(self, repo_id: int):
        """Track which repos are modified in this transaction."""
        self._affected_repos.add(repo_id)
    
    async def track_cache_invalidation(self, cache_name: str):
        """Track which caches need invalidation."""
        self._affected_caches.add(cache_name)
    
    @handle_async_errors(error_types=(PostgresError, Neo4jError, TransactionError, CacheError))
    async def _invalidate_caches(self):
        """Coordinated cache invalidation."""
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
        
    async def _start_postgres(self):
        """Start PostgreSQL transaction."""
        if not self.pg_conn:
            self.pg_conn = await connection_manager.get_postgres_connection()
            self.pg_transaction = self.pg_conn.transaction()
            await self.pg_transaction.start()
            
    async def _start_neo4j(self):
        """Start Neo4j transaction."""
        if not self.neo4j_session:
            self.neo4j_session = await connection_manager.get_session()
            self.neo4j_transaction = await self.neo4j_session.begin_transaction()
    
    @handle_async_errors(error_types=[PostgresError, Neo4jError, Exception])
    async def _cleanup(self):
        """Clean up all resources."""
        with ErrorBoundary(
            error_types=[PostgresError, Neo4jError, Exception],
            error_message="Error cleaning up transactions",
            severity=ErrorSeverity.WARNING
        ) as error_boundary:
            # Clean up any pending tasks first
            if self._pending_tasks:
                await asyncio.gather(*[asyncio.wrap_future(f) for f in self._pending_tasks], return_exceptions=True)
                self._pending_tasks.clear()
            
            # Clean up PostgreSQL resources
            if self.pg_conn:
                try:
                    if self.pg_transaction and not self.pg_transaction.is_closed():
                        await self.pg_transaction.rollback()
                except Exception as e:
                    log(f"Error rolling back PostgreSQL transaction: {e}", level="error")
                finally:
                    await connection_manager.release_postgres_connection(self.pg_conn)
                    self.pg_conn = None
                    self.pg_transaction = None
            
            # Clean up Neo4j resources
            if self.neo4j_session:
                try:
                    if self.neo4j_transaction and not self.neo4j_transaction.closed():
                        await self.neo4j_transaction.rollback()
                except Exception as e:
                    log(f"Error rolling back Neo4j transaction: {e}", level="error")
                finally:
                    await self.neo4j_session.close()
                    self.neo4j_session = None
                    self.neo4j_transaction = None
        
        if error_boundary.error:
            log(f"Error cleaning up transactions: {error_boundary.error}", level="error")
            raise TransactionError(f"Transaction cleanup failed: {str(error_boundary.error)}")

@asynccontextmanager
@handle_async_errors(error_types=(PostgresError, Neo4jError, TransactionError, CacheError, ConnectionError, Exception))
async def transaction_scope(invalidate_cache: bool = True):
    """
    Context manager for coordinated transactions.
    
    This context manager ensures that:
    1. Database connections are properly initialized
    2. Transactions are started and managed across databases
    3. Cache invalidation is handled when needed
    4. Resources are properly cleaned up
    
    Usage:
    async with transaction_scope() as coordinator:
        # Perform database operations
        # Transactions will be automatically committed or rolled back
    """
    coordinator = TransactionCoordinator()
    try:
        async with coordinator._lock:
            try:
                # Ensure connections are initialized
                await connection_manager.initialize_postgres()
                await connection_manager.initialize()
                
                # Start transactions
                await coordinator._start_postgres()
                await coordinator._start_neo4j()
                
                try:
                    yield coordinator
                    
                    # Commit transactions
                    if coordinator.pg_transaction:
                        await coordinator.pg_transaction.commit()
                    if coordinator.neo4j_transaction:
                        await coordinator.neo4j_transaction.commit()
                    
                    # Handle cache invalidation
                    if invalidate_cache:
                        await coordinator._invalidate_caches()
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
                coordinator._pending_tasks.add(future)
                try:
                    await asyncio.wrap_future(future)
                finally:
                    coordinator._pending_tasks.remove(future)
                raise
    finally:
        # Ensure resources are cleaned up
        await coordinator._cleanup() 