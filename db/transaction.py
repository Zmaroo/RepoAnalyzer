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
    ErrorSeverity,
    PostgresError, 
    Neo4jError, 
    TransactionError, 
    CacheError,
    ConnectionError,
    DatabaseError
)
from db.retry_utils import RetryManager, RetryConfig
from utils.async_runner import submit_async_task, get_loop
from utils.shutdown import register_shutdown_handler
from utils.health_monitor import global_health_monitor

class TransactionCoordinator:
    """Coordinates transactions across different databases and caches."""
    
    def __init__(self):
        """Private constructor - use create() instead."""
        self._initialized = False
        self._pending_tasks: Set[asyncio.Task] = set()
        self._retry_manager = None
        self._lock = asyncio.Lock()
        self.pg_transaction = None
        self.neo4j_transaction = None
        self.pg_conn = None
        self.neo4j_session = None
        self._ai_operation_stats = {
            "total_transactions": 0,
            "pattern_transactions": 0,
            "ai_enhanced_transactions": 0,
            "failed_transactions": 0
        }
    
    async def track_ai_operation(self, operation_type: str) -> None:
        """Track AI operation statistics."""
        self._ai_operation_stats["total_transactions"] += 1
        if operation_type == "pattern":
            self._ai_operation_stats["pattern_transactions"] += 1
        if operation_type == "ai_enhanced":
            self._ai_operation_stats["ai_enhanced_transactions"] += 1
    
    async def _start_postgres(self) -> None:
        """Start PostgreSQL transaction with AI operation settings."""
        if not self.pg_conn:
            self.pg_conn = await connection_manager.get_connection()
            # Configure for AI operations
            await self.pg_conn.execute("""
                SET SESSION statement_timeout = '300s';  -- 5 minutes for AI operations
                SET SESSION idle_in_transaction_session_timeout = '60s';
            """)
        self.pg_transaction = self.pg_conn.transaction()
        await self.pg_transaction.start()
    
    async def _start_neo4j(self) -> None:
        """Start Neo4j transaction with AI operation settings."""
        if not self.neo4j_session:
            self.neo4j_session = await connection_manager.get_session()
        self.neo4j_transaction = await self.neo4j_session.begin_transaction(
            timeout=300,  # 5 minutes for AI operations
            metadata={"type": "ai_pattern_processor"}
        )
    
    async def track_pattern_change(
        self,
        pattern_id: int,
        operation_type: str = "update",
        is_ai_enhanced: bool = False
    ) -> None:
        """Track pattern changes for cache invalidation."""
        await cache_coordinator.track_change(f"pattern:{pattern_id}")
        if is_ai_enhanced:
            await cache_coordinator.track_change(f"ai_pattern:{pattern_id}")
        await self.track_ai_operation("pattern" if not is_ai_enhanced else "ai_enhanced")
    
    async def _invalidate_caches(self) -> None:
        """Invalidate relevant caches after transaction."""
        try:
            changes = await cache_coordinator.get_tracked_changes()
            for change in changes:
                if change.startswith("pattern:"):
                    pattern_id = change.split(":")[1]
                    await cache_coordinator.invalidate(f"pattern_cache:{pattern_id}")
                    await cache_coordinator.invalidate(f"pattern_metrics:{pattern_id}")
                elif change.startswith("ai_pattern:"):
                    pattern_id = change.split(":")[1]
                    await cache_coordinator.invalidate(f"ai_insights:{pattern_id}")
                    await cache_coordinator.invalidate(f"ai_metrics:{pattern_id}")
                    await cache_coordinator.invalidate(f"ai_recommendations:{pattern_id}")
        except Exception as e:
            log(f"Error invalidating caches: {e}", level="error")
            raise CacheError(f"Failed to invalidate caches: {str(e)}")
    
    def get_stats(self) -> Dict[str, int]:
        """Get AI operation statistics."""
        return self._ai_operation_stats.copy()
    
    def reset_stats(self) -> None:
        """Reset AI operation statistics."""
        self._ai_operation_stats = {
            "total_transactions": 0,
            "pattern_transactions": 0,
            "ai_enhanced_transactions": 0,
            "failed_transactions": 0
        }
    
    async def ensure_initialized(self):
        """Ensure the instance is properly initialized before use."""
        if not self._initialized:
            raise DatabaseError("TransactionCoordinator not initialized. Use create() to initialize.")
        return True
    
    @classmethod
    async def create(cls) -> 'TransactionCoordinator':
        """Async factory method to create and initialize a TransactionCoordinator instance."""
        instance = cls()
        try:
            async with AsyncErrorBoundary(
                operation_name="transaction coordinator initialization",
                error_types=DatabaseError,
                severity=ErrorSeverity.CRITICAL
            ):
                # Initialize retry manager
                instance._retry_manager = await RetryManager.create(
                    RetryConfig(max_retries=3, base_delay=1.0, max_delay=10.0)
                )
                
                # Register shutdown handler
                register_shutdown_handler(instance.cleanup)
                
                # Initialize health monitoring
                global_health_monitor.register_component("transaction_coordinator")
                
                instance._initialized = True
                await log("Transaction coordinator initialized", level="info")
                return instance
        except Exception as e:
            await log(f"Error initializing transaction coordinator: {e}", level="error")
            # Cleanup on initialization failure
            await instance.cleanup()
            raise DatabaseError(f"Failed to initialize transaction coordinator: {e}")
    
    async def cleanup(self):
        """Clean up all resources."""
        try:
            if not self._initialized:
                return
                
            # Cancel all pending tasks
            if self._pending_tasks:
                for task in self._pending_tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                self._pending_tasks.clear()
            
            # Clean up retry manager
            if self._retry_manager:
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
            
            # Unregister from health monitoring
            global_health_monitor.unregister_component("transaction_coordinator")
            
            self._initialized = False
            await log("Transaction coordinator cleaned up", level="info")
        except Exception as e:
            await log(f"Error cleaning up transaction coordinator: {e}", level="error")
            raise DatabaseError(f"Failed to cleanup transaction coordinator: {e}")

# Global instance
transaction_coordinator = None

async def get_transaction_coordinator() -> TransactionCoordinator:
    """Get the global transaction coordinator instance."""
    global transaction_coordinator
    if not transaction_coordinator:
        transaction_coordinator = await TransactionCoordinator.create()
    return transaction_coordinator

@asynccontextmanager
@handle_async_errors(error_types=(PostgresError, Neo4jError, TransactionError, CacheError, ConnectionError, Exception))
async def transaction_scope(invalidate_cache: bool = True):
    """Context manager for coordinated transactions."""
    if not transaction_coordinator._initialized:
        await transaction_coordinator.ensure_initialized()
        
    try:
        async with transaction_coordinator._lock:
            try:
                # Ensure connections are initialized
                await connection_manager.initialize_postgres()
                await connection_manager.initialize()
                
                # Start transactions
                await transaction_coordinator._start_postgres()
                await transaction_coordinator._start_neo4j()
                
                try:
                    yield transaction_coordinator
                    
                    # Commit transactions
                    if transaction_coordinator.pg_transaction:
                        await transaction_coordinator.pg_transaction.commit()
                    if transaction_coordinator.neo4j_transaction:
                        await transaction_coordinator.neo4j_transaction.commit()
                    
                    # Handle cache invalidation
                    if invalidate_cache:
                        await transaction_coordinator._invalidate_caches()
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
                transaction_coordinator._pending_tasks.add(future)
                try:
                    await asyncio.wrap_future(future)
                finally:
                    transaction_coordinator._pending_tasks.remove(future)
                raise
    finally:
        # Ensure resources are cleaned up
        await transaction_coordinator.cleanup()

# Register cleanup handler
async def cleanup_transaction():
    """Cleanup transaction coordinator resources."""
    try:
        await transaction_coordinator.cleanup()
        log("Transaction coordinator resources cleaned up", level="info")
    except Exception as e:
        log(f"Error cleaning up transaction coordinator resources: {e}", level="error")

register_shutdown_handler(cleanup_transaction) 