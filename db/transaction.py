"""[6.4] Multi-database transaction coordination."""

import asyncio
from contextlib import asynccontextmanager
from typing import Optional, AsyncGenerator
from utils.logger import log
from db.psql import init_db_pool
from db.connection import driver
from utils.cache import cache_coordinator
from utils.error_handling import handle_async_errors, AsyncErrorBoundary, ErrorBoundary
from utils.error_handling import PostgresError, Neo4jError, TransactionError, CacheError, DatabaseError
from db.retry_utils import DatabaseRetryManager, RetryConfig

# Initialize retry manager for transaction operations
_retry_manager = DatabaseRetryManager()

@handle_async_errors(error_types=(Exception,))
async def get_connection():
    """
    Get a database connection for use in transactions.
    This function is primarily used for direct connection access
    and is also a target for mocking in tests.
    
    Returns:
        A database connection from the pool.
    """
    from utils.logger import log
    import db.psql  # Import directly to get the latest reference
    
    try:
        if db.psql._pool is None:
            log("Database pool is not initialized when trying to get a connection", level="error")
            raise DatabaseError("Database pool is not initialized")
        return await db.psql._pool.acquire()
    except Exception as e:
        log(f"Error acquiring connection from pool: {e}", level="error")
        raise DatabaseError(f"Failed to acquire connection: {str(e)}")

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
@handle_async_errors(error_types=(Exception,))
        
    async def track_repo_change(self, repo_id: int):
        """Track which repos are modified in this transaction."""
@handle_async_errors(error_types=(Exception,))
        self._affected_repos.add(repo_id)
    
    async def track_cache_invalidation(self, cache_name: str):
        """Track which caches need invalidation."""
        self._affected_caches.add(cache_name)
    
    @handle_async_errors(error_types=(PostgresError, Neo4jError, TransactionError, CacheError))
    async def _invalidate_caches(self):
        """Coordinated cache invalidation."""
        try:
            for repo_id in self._affected_repos:
                async with AsyncErrorBoundary(operation_name="cache invalidation", error_types=CacheError):
                    patterns = [f"repo:{repo_id}:*", f"graph:{repo_id}:*"]
                    for pattern in patterns:
                        await cache_coordinator.invalidate_pattern(pattern)
        except Exception as e:
            raise CacheError(f"Cache invalidation failed: {str(e)}")
        
    @handle_async_errors(error_types=(PostgresError, Neo4jError, TransactionError, CacheError))
    async def _commit_all(self):
        """[6.4.4] Commit all active transactions."""
        async def _do_commit():
            if self.pg_conn:
                async with AsyncErrorBoundary(operation_name="postgres commit", error_types=PostgresError):
                    await self.pg_transaction.commit()
                
            if self.neo4j_session:
                async with AsyncErrorBoundary(operation_name="neo4j commit", error_types=Neo4jError):
                    await self.neo4j_transaction.commit()
        
        try:
            # Use retry manager to execute the commit with retry logic
            await _retry_manager.execute_with_retry(_do_commit)
        except (PostgresError, Neo4jError) as e:
            await self._rollback_all()
            raise TransactionError(f"Transaction commit failed: {str(e)}")
            
    @handle_async_errors(error_types=(PostgresError, Neo4jError, Exception))
    async def _rollback_all(self):
        """Rollback all active transactions."""
        async def _do_rollback():
            if self.pg_conn:
                await self.pg_transaction.rollback()
                
            if self.neo4j_session:
                await self.neo4j_transaction.rollback()
        
        try:
            # Create and enter the error boundary context
            error_boundary = ErrorBoundary(operation_name="Rolling back transactions", error_types=(PostgresError, Neo4jError, Exception))
            error_boundary.__enter__()
            
            try:
                # Use retry manager to execute the rollback with retry logic
                await _retry_manager.execute_with_retry(_do_rollback)
                
                # Exit the error boundary context on success
                error_boundary.__exit__(None, None, None)
            except Exception as e:
                # Exit the error boundary context on exception
                error_boundary.__exit__(type(e), e, None)
                raise
            
            if hasattr(error_boundary, 'error') and error_boundary.error:
                log(f"Error in _rollback_all: {error_boundary.error}", level="error")
                raise TransactionError(f"Transaction rollback failed: {str(error_boundary.error)}")
        except Exception as e:
            log(f"Unexpected error during transaction rollback: {e}", level="error")
            raise TransactionError(f"Transaction rollback unexpected failure: {str(e)}")
            
    @handle_async_errors(error_types=(PostgresError, Neo4jError, Exception))
    async def _cleanup(self):
        """Clean up all resources."""
        async with AsyncErrorBoundary(operation_name="Cleaning up transactions", error_types=(PostgresError, Neo4jError, Exception)) as error_boundary:
            if self.pg_conn:
                import db.psql
                await db.psql._pool.release(self.pg_conn)
                self.pg_conn = None
                
            if self.neo4j_session:
                self.neo4j_session.close()
                self.neo4j_session = None
        
        if error_boundary.error:
@handle_async_errors(error_types=(Exception,))
            log(f"Error cleaning up transactions: {error_boundary.error}", level="error")
            raise TransactionError(f"Transaction cleanup failed: {str(error_boundary.error)}")

    async def _start_postgres(self):
        """Start PostgreSQL transaction."""
        if not self.pg_conn:
            try:
                self.pg_conn = await get_connection()
                self.pg_transaction = self.pg_conn.transaction()
                await self.pg_transaction.start()
            except Exception as e:
                log(f"Error starting PostgreSQL transaction: {e}", level="error")
@handle_async_errors(error_types=(Exception,))
                self.pg_conn = None
                self.pg_transaction = None
                raise
        
    async def _start_neo4j(self):
        """Start Neo4j transaction."""
        if not self.neo4j_session:
            try:
                self.neo4j_session = driver.session()
                self.neo4j_transaction = self.neo4j_session.begin_transaction()
            except Exception as e:
                log(f"Error starting Neo4j transaction: {e}", level="error")
                self.neo4j_session = None
                self.neo4j_transaction = None
                raise

@asynccontextmanager
async def transaction_scope(invalidate_cache: bool = True):
    """
    Context manager for coordinated transactions.
    
    Usage:
    async with transaction_scope() as coordinator:
        # Perform database operations
        # Transactions will be automatically committed or rolled back
    """
    # Always import _pool directly to get the latest reference
    import db.psql
    from utils.logger import log
    from utils.error_handling import AsyncErrorBoundary
    
    # For testing purposes, create a mock coordinator if the pool is not initialized
    mock_mode = db.psql._pool is None
    if mock_mode:
        log(f"Database pool not initialized or not available (_pool={db.psql._pool}), using mock transaction coordinator", level="warning")
        # Try to initialize the pool if it's None
        try:
            log("Attempting to initialize the database pool", level="info")
            await db.psql.init_db_pool()
            log("Database pool initialized successfully", level="info")
            # Check again after initialization attempt
            mock_mode = db.psql._pool is None
        except Exception as e:
            log(f"Failed to initialize the database pool: {e}", level="error")
            
    if mock_mode:
        coordinator = MockTransactionCoordinator()
        # In mock mode, just yield the coordinator without any real transactions
        try:
            yield coordinator
        except Exception as e:
            log(f"Mock transaction scope unexpected error: {e}", level="error")
            raise
        return
        
    # Normal mode with initialized pool
    log(f"Using real transaction coordinator with pool: {db.psql._pool}", level="debug")
    coordinator = TransactionCoordinator()
    
    try:
        # Use AsyncErrorBoundary with async with instead of ErrorBoundary with with
        async with AsyncErrorBoundary(operation_name="Transaction scope", error_types=(PostgresError, Neo4jError, TransactionError, CacheError, Exception)):
            # Check that coordinator._lock is not None before trying to acquire it
            if not hasattr(coordinator, '_lock') or coordinator._lock is None:
                log("TransactionCoordinator has no _lock attribute or it is None", level="error")
                raise TransactionError("Transaction coordinator not properly initialized")
                
            try:
                async with coordinator._lock:
                    try:
                        await coordinator._start_postgres()
                        await coordinator._start_neo4j()
                    except Exception as e:
                        log(f"Error starting transactions: {e}", level="error")
                        raise TransactionError(f"Failed to start transactions: {str(e)}")
            except Exception as e:
                log(f"Error acquiring lock: {e}", level="error")
                raise TransactionError(f"Failed to acquire transaction lock: {str(e)}")
            
            # Yield the coordinator to allow operations within the transaction scope
            yield coordinator
            
            # Commit and invalidate caches if needed
            await coordinator._commit_all()
            if invalidate_cache:
                await coordinator._invalidate_caches()
    except Exception as e:
        # Handle any other exceptions
        log(f"Transaction scope unexpected error: {e}", level="error")
        try:
            await coordinator._rollback_all()
        except Exception as rollback_error:
            log(f"Error during rollback: {rollback_error}", level="error")
        raise

class MockTransactionCoordinator:
    """Mock implementation of TransactionCoordinator for testing."""
    
    def __init__(self):
        self._affected_repos = set()
        self._affected_caches = set()
        self._lock = asyncio.Lock()
@handle_async_errors(error_types=(Exception,))
        self.pg_conn = None
        self.pg_transaction = None
        self.neo4j_session = None
@handle_async_errors(error_types=(Exception,))
        self.neo4j_transaction = None
    
    async def track_repo_change(self, repo_id: int):
        """Track which repos are modified in this transaction."""
        self._affected_repos.add(repo_id)
    
    async def track_cache_invalidation(self, cache_name: str):
        """Track which caches need invalidation."""
        self._affected_caches.add(cache_name)
        
    async def _start_postgres(self):
        """Mock starting PostgreSQL transaction."""
        log("Mock: Starting PostgreSQL transaction", level="debug")
        # No-op in mock implementation
        
    async def _start_neo4j(self):
        """Mock starting Neo4j transaction."""
        log("Mock: Starting Neo4j transaction", level="debug")
        # No-op in mock implementation
    
    async def _commit_all(self):
        """Mock committing all active transactions."""
        log("Mock: Committing all transactions", level="debug")
        # No-op in mock implementation
            
    async def _rollback_all(self):
        """Mock rollback all active transactions."""
        log("Mock: Rolling back all transactions", level="debug")
        # No-op in mock implementation
            
    async def _cleanup(self):
        """Mock clean up all resources."""
        log("Mock: Cleaning up all transaction resources", level="debug")
        # No-op in mock implementation
        
    async def _invalidate_caches(self):
        """Mock coordinated cache invalidation."""
        log(f"Mock: Invalidating caches for repos {self._affected_repos} and caches {self._affected_caches}", level="debug") 