"""[6.4] Multi-database transaction coordination."""

import asyncio
from contextlib import asynccontextmanager
from typing import Optional, AsyncGenerator
from utils.logger import log
from db.psql import _pool
from db.connection import driver
from utils.cache import cache_coordinator
from utils.error_handling import handle_async_errors, AsyncErrorBoundary, ErrorBoundary
from utils.error_handling import PostgresError, Neo4jError, TransactionError, CacheError
from db.retry_utils import DatabaseRetryManager, RetryConfig

# Initialize retry manager for transaction operations
_retry_manager = DatabaseRetryManager()

async def get_connection():
    """
    Get a database connection for use in transactions.
    This function is primarily used for direct connection access
    and is also a target for mocking in tests.
    
    Returns:
        A database connection from the pool.
    """
    return await _pool.acquire()

class TransactionCoordinator:
    """Coordinates transactions across different databases and caches."""
    
    def __init__(self):
        self.pg_conn = None
        self.neo4j_session = None
        self._lock = asyncio.Lock()
        self._affected_repos = set()  # Track affected repos
        self._affected_caches = set()  # Track which caches need invalidation
        
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
                        await cache_coordinator.invalidate_pattern(pattern)
        except Exception as e:
            raise CacheError(f"Cache invalidation failed: {str(e)}")
        
    async def _start_postgres(self):
        """Start PostgreSQL transaction."""
        if not self.pg_conn:
            self.pg_conn = await get_connection()
            self.pg_transaction = self.pg_conn.transaction()
            await self.pg_transaction.start()
            
    async def _start_neo4j(self):
        """Start Neo4j transaction."""
        if not self.neo4j_session:
            self.neo4j_session = driver.session()
            self.neo4j_transaction = self.neo4j_session.begin_transaction()
    
    @handle_async_errors(error_types=(PostgresError, Neo4jError, TransactionError, CacheError))
    async def _commit_all(self):
        """[6.4.4] Commit all active transactions."""
        async def _do_commit():
            if self.pg_conn:
                async with AsyncErrorBoundary("postgres commit", error_types=PostgresError):
                    await self.pg_transaction.commit()
                
            if self.neo4j_session:
                async with AsyncErrorBoundary("neo4j commit", error_types=Neo4jError):
                    await self.neo4j_transaction.commit()
        
        try:
            # Use retry manager to execute the commit with retry logic
            await _retry_manager.execute_with_retry(_do_commit)
        except (PostgresError, Neo4jError) as e:
            await self._rollback_all()
            raise TransactionError(f"Transaction commit failed: {str(e)}")
            
    @handle_async_errors(error_types=[PostgresError, Neo4jError, Exception])
    async def _rollback_all(self):
        """Rollback all active transactions."""
        async def _do_rollback():
            if self.pg_conn:
                await self.pg_transaction.rollback()
                
            if self.neo4j_session:
                await self.neo4j_transaction.rollback()
        
        with ErrorBoundary(error_types=[PostgresError, Neo4jError, Exception],
                           error_message="Error rolling back transactions") as error_boundary:
            # Use retry manager to execute the rollback with retry logic
            await _retry_manager.execute_with_retry(_do_rollback)
        
        if error_boundary.error:
            log(f"Error rolling back transactions: {error_boundary.error}", level="error")
            raise TransactionError(f"Transaction rollback failed: {str(error_boundary.error)}")
            
    @handle_async_errors(error_types=[PostgresError, Neo4jError, Exception])
    async def _cleanup(self):
        """Clean up all resources."""
        with ErrorBoundary(error_types=[PostgresError, Neo4jError, Exception],
                           error_message="Error cleaning up transactions") as error_boundary:
            if self.pg_conn:
                await _pool.release(self.pg_conn)
                self.pg_conn = None
                
            if self.neo4j_session:
                self.neo4j_session.close()
                self.neo4j_session = None
        
        if error_boundary.error:
            log(f"Error cleaning up transactions: {error_boundary.error}", level="error")
            raise TransactionError(f"Transaction cleanup failed: {str(error_boundary.error)}")

from utils.error_handling import handle_async_errors

@asynccontextmanager
@handle_async_errors(error_types=(PostgresError, Neo4jError, TransactionError, CacheError, Exception))
async def transaction_scope(invalidate_cache: bool = True):
    """
    Context manager for coordinated transactions.
    
    Usage:
    async with transaction_scope() as coordinator:
        # Perform database operations
        # Transactions will be automatically committed or rolled back
    """
    coordinator = TransactionCoordinator()
    try:
        async with coordinator._lock:
            try:
                await coordinator._start_postgres()
                await coordinator._start_neo4j()
                try:
                    yield coordinator
                    await coordinator._commit_all()
                    if invalidate_cache:
                        await coordinator._invalidate_caches()
                except Exception as e:
                    log(f"Transaction scope error: {e}", level="error")
                    await coordinator._rollback_all()
                    raise TransactionError(f"Transaction scope failed: {str(e)}")
            except (PostgresError, Neo4jError, TransactionError, CacheError, Exception) as e:
                log(f"Error in transaction_scope: {e}", level="error")
                # Record the error for audit purposes
                from utils.error_handling import ErrorAudit
                ErrorAudit.record_error(e, "transaction_scope", (PostgresError, Neo4jError, TransactionError, CacheError, Exception))
                raise
    finally:
        # Ensure resources are cleaned up
        try:
            await coordinator._cleanup()
        except Exception as e:
            log(f"Error cleaning up transaction resources: {e}", level="error") 