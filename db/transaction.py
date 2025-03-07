"""[6.4] Multi-database transaction coordination.

This module provides centralized transaction management across multiple databases:
1. Transaction lifecycle management
2. Cache invalidation coordination
3. Error handling and recovery
4. Resource cleanup
"""

import asyncio
from contextlib import asynccontextmanager
from typing import Optional, Set, Dict, Any, List
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
from utils.health_monitor import global_health_monitor, ComponentStatus
import time

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
    
    # Generate unique transaction ID
    txn_id = f"txn_{int(time.time() * 1000)}_{id(asyncio.current_task())}"
    
    try:
        async with transaction_coordinator._lock:
            try:
                # Ensure connections are initialized
                await connection_manager.initialize_postgres()
                await connection_manager.initialize()
                
                # Register transaction with deadlock detector
                await deadlock_detector.register_transaction(txn_id, "postgres")
                await deadlock_detector.register_transaction(txn_id, "neo4j")
                
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
        # Unregister transaction from deadlock detector
        await deadlock_detector.unregister_transaction(txn_id)
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

class DeadlockDetector:
    """Detects and manages database deadlocks."""
    
    def __init__(self):
        self._lock = asyncio.Lock()
        self._transaction_graph = {}  # Graph of transaction dependencies
        self._transaction_timestamps = {}  # Transaction start times
        self._deadlock_timeout = 30.0  # Seconds before considering a potential deadlock
        self._pending_tasks: Set[asyncio.Task] = set()
        self._monitoring = False
        self._monitor_task = None
    
    async def start_monitoring(self):
        """Start deadlock monitoring."""
        async with self._lock:
            if self._monitoring:
                return
            self._monitoring = True
            self._monitor_task = asyncio.create_task(self._monitor_deadlocks())
            self._pending_tasks.add(self._monitor_task)
    
    async def stop_monitoring(self):
        """Stop deadlock monitoring."""
        async with self._lock:
            if not self._monitoring:
                return
            self._monitoring = False
            if self._monitor_task and not self._monitor_task.done():
                self._monitor_task.cancel()
                try:
                    await self._monitor_task
                except asyncio.CancelledError:
                    pass
            if self._monitor_task in self._pending_tasks:
                self._pending_tasks.remove(self._monitor_task)
    
    async def register_transaction(self, txn_id: str, resource_id: str):
        """Register a transaction's intent to access a resource."""
        async with self._lock:
            if txn_id not in self._transaction_graph:
                self._transaction_graph[txn_id] = set()
                self._transaction_timestamps[txn_id] = time.time()
            self._transaction_graph[txn_id].add(resource_id)
    
    async def unregister_transaction(self, txn_id: str):
        """Unregister a completed transaction."""
        async with self._lock:
            if txn_id in self._transaction_graph:
                del self._transaction_graph[txn_id]
            if txn_id in self._transaction_timestamps:
                del self._transaction_timestamps[txn_id]
    
    def _has_cycle(self, graph: Dict[str, Set[str]], start: str, visited: Set[str], path: Set[str]) -> bool:
        """Check for cycles in the transaction dependency graph using DFS."""
        visited.add(start)
        path.add(start)
        
        for neighbor in graph.get(start, set()):
            if neighbor not in visited:
                if self._has_cycle(graph, neighbor, visited, path):
                    return True
            elif neighbor in path:
                return True
        
        path.remove(start)
        return False
    
    async def check_for_deadlocks(self) -> List[Set[str]]:
        """Check for potential deadlocks in current transactions.
        
        Returns:
            List[Set[str]]: Sets of transaction IDs involved in deadlocks
        """
        async with self._lock:
            deadlocks = []
            visited = set()
            
            # Check for cycles in transaction graph
            for txn_id in self._transaction_graph:
                if txn_id not in visited:
                    path = set()
                    if self._has_cycle(self._transaction_graph, txn_id, visited, path):
                        deadlocks.append(path)
            
            # Check for long-running transactions
            current_time = time.time()
            for txn_id, start_time in self._transaction_timestamps.items():
                if current_time - start_time > self._deadlock_timeout:
                    deadlocks.append({txn_id})
            
            return deadlocks
    
    async def _monitor_deadlocks(self):
        """Background task to monitor for deadlocks."""
        while self._monitoring:
            try:
                deadlocks = await self.check_for_deadlocks()
                if deadlocks:
                    for deadlock in deadlocks:
                        # Log the deadlock
                        txn_ids = ", ".join(deadlock)
                        await log(f"Potential deadlock detected involving transactions: {txn_ids}", level="warning")
                        
                        # Add retry tracking for health status updates
                        retry_count = 0
                        while retry_count < 3:
                            try:
                                await global_health_monitor.update_component_status(
                                    "transaction_coordinator",
                                    ComponentStatus.DEGRADED,
                                    error=True,
                                    details={
                                        "deadlock_transactions": list(deadlock),
                                        "deadlock_duration": time.time() - min(
                                            self._transaction_timestamps[txn_id] 
                                            for txn_id in deadlock
                                        ),
                                        "affected_resources": [
                                            res for txn_id in deadlock 
                                            for res in self._transaction_graph.get(txn_id, set())
                                        ],
                                        "retry_attempt": retry_count + 1,
                                        "deadlock_type": "cycle" if len(deadlock) > 1 else "timeout",
                                        "resource_contention": {
                                            res: [txn for txn in deadlock 
                                                 if res in self._transaction_graph.get(txn, set())]
                                            for res in set(res for txn in deadlock 
                                                         for res in self._transaction_graph.get(txn, set()))
                                        }
                                    }
                                )
                                break
                            except Exception as e:
                                retry_count += 1
                                await asyncio.sleep(1)
                                if retry_count == 3:
                                    await log(f"Failed to update health status after retries: {e}", level="error")
                                    
                                # Record error for audit
                                from utils.error_handling import ErrorAudit
                                await ErrorAudit.record_error(
                                    e,
                                    "deadlock_detector_health_update",
                                    Exception,
                                    severity=ErrorSeverity.WARNING
                                )
                    
                    await asyncio.sleep(1.0)  # Check every second
                else:
                    # Update healthy status periodically
                    try:
                        await global_health_monitor.update_component_status(
                            "transaction_coordinator",
                            ComponentStatus.HEALTHY,
                            details={
                                "active_transactions": len(self._transaction_graph),
                                "monitoring_status": "active",
                                "last_check": time.time()
                            }
                        )
                    except Exception as e:
                        await log(f"Error updating healthy status: {e}", level="warning")
                    
                    await asyncio.sleep(5.0)  # Longer sleep when no deadlocks
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                await log(f"Error in deadlock monitor: {e}", level="error")
                await asyncio.sleep(5.0)  # Back off on error
    
    async def cleanup(self):
        """Clean up resources."""
        await self.stop_monitoring()
        self._transaction_graph.clear()
        self._transaction_timestamps.clear()
        
        # Cancel any remaining tasks
        if self._pending_tasks:
            for task in self._pending_tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*self._pending_tasks, return_exceptions=True)
            self._pending_tasks.clear()

# Create global instance
deadlock_detector = DeadlockDetector()

# Register cleanup handler
register_shutdown_handler(deadlock_detector.cleanup) 