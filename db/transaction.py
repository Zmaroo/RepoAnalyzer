"""[6.4] Multi-database transaction coordination.

This module provides centralized transaction management across multiple databases:
1. Transaction lifecycle management
2. Cache invalidation coordination
3. Error handling and recovery
4. Resource cleanup
5. Distributed transaction support
6. Enhanced deadlock detection
7. Transaction monitoring
"""

import asyncio
from contextlib import asynccontextmanager
from typing import Optional, Set, Dict, Any, List, Tuple
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
import uuid

class TransactionState:
    """Transaction state for distributed transactions."""
    PREPARING = "preparing"
    PREPARED = "prepared"
    COMMITTING = "committing"
    COMMITTED = "committed"
    ROLLING_BACK = "rolling_back"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"

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
        # New fields for distributed transactions
        self._distributed_txns: Dict[str, Dict[str, Any]] = {}
        self._prepared_txns: Set[str] = set()
        self._transaction_states: Dict[str, str] = {}
        self._transaction_timeouts: Dict[str, float] = {}
        self._transaction_metrics: Dict[str, Dict[str, Any]] = {}
        self._transaction_participants: Dict[str, Set[str]] = {}
    
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
                # Update initialization status
                await global_health_monitor.update_component_status(
                    "transaction_coordinator",
                    ComponentStatus.INITIALIZING,
                    details={"stage": "starting"}
                )
                
                # Initialize retry manager through async_runner
                retry_init_task = submit_async_task(RetryManager.create(
                    RetryConfig(max_retries=3, base_delay=1.0, max_delay=10.0)
                ))
                instance._retry_manager = await asyncio.wrap_future(retry_init_task)
                
                # Register shutdown handler
                register_shutdown_handler(instance.cleanup)
                
                # Initialize health monitoring
                global_health_monitor.register_component("transaction_coordinator")
                
                instance._initialized = True
                await log("Transaction coordinator initialized", level="info")
                
                # Update final status
                await global_health_monitor.update_component_status(
                    "transaction_coordinator",
                    ComponentStatus.HEALTHY,
                    details={"stage": "complete"}
                )
                
                return instance
        except Exception as e:
            await log(f"Error initializing transaction coordinator: {e}", level="error")
            await global_health_monitor.update_component_status(
                "transaction_coordinator",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"initialization_error": str(e)}
            )
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
    
    async def prepare_transaction(self, txn_id: str) -> bool:
        """Prepare a distributed transaction for two-phase commit."""
        async with self._lock:
            try:
                if txn_id not in self._distributed_txns:
                    return False
                
                # Set transaction state to preparing
                self._transaction_states[txn_id] = TransactionState.PREPARING
                
                # Prepare PostgreSQL transaction
                if self.pg_transaction:
                    await self.pg_conn.execute('PREPARE TRANSACTION $1', [txn_id])
                
                # Prepare Neo4j transaction (if supported)
                if self.neo4j_transaction:
                    # Neo4j doesn't support native prepare, so we track it ourselves
                    self._prepared_txns.add(txn_id)
                
                self._transaction_states[txn_id] = TransactionState.PREPARED
                return True
                
            except Exception as e:
                self._transaction_states[txn_id] = TransactionState.FAILED
                await log(f"Error preparing transaction {txn_id}: {e}", level="error")
                return False
    
    async def commit_prepared(self, txn_id: str) -> bool:
        """Commit a prepared distributed transaction."""
        async with self._lock:
            try:
                if txn_id not in self._prepared_txns:
                    return False
                
                self._transaction_states[txn_id] = TransactionState.COMMITTING
                
                # Commit PostgreSQL prepared transaction
                await self.pg_conn.execute('COMMIT PREPARED $1', [txn_id])
                
                # Commit Neo4j transaction
                if self.neo4j_transaction:
                    await self.neo4j_transaction.commit()
                
                self._prepared_txns.remove(txn_id)
                self._transaction_states[txn_id] = TransactionState.COMMITTED
                
                # Update metrics
                end_time = time.time()
                if txn_id in self._transaction_metrics:
                    metrics = self._transaction_metrics[txn_id]
                    metrics["commit_time"] = end_time
                    metrics["duration"] = end_time - metrics["start_time"]
                    metrics["state"] = "committed"
                
                return True
                
            except Exception as e:
                self._transaction_states[txn_id] = TransactionState.FAILED
                await log(f"Error committing prepared transaction {txn_id}: {e}", level="error")
                return False
    
    async def rollback_prepared(self, txn_id: str) -> bool:
        """Rollback a prepared distributed transaction."""
        async with self._lock:
            try:
                if txn_id not in self._prepared_txns:
                    return False
                
                self._transaction_states[txn_id] = TransactionState.ROLLING_BACK
                
                # Rollback PostgreSQL prepared transaction
                await self.pg_conn.execute('ROLLBACK PREPARED $1', [txn_id])
                
                # Rollback Neo4j transaction
                if self.neo4j_transaction:
                    await self.neo4j_transaction.rollback()
                
                self._prepared_txns.remove(txn_id)
                self._transaction_states[txn_id] = TransactionState.ROLLED_BACK
                
                # Update metrics
                end_time = time.time()
                if txn_id in self._transaction_metrics:
                    metrics = self._transaction_metrics[txn_id]
                    metrics["rollback_time"] = end_time
                    metrics["duration"] = end_time - metrics["start_time"]
                    metrics["state"] = "rolled_back"
                
                return True
                
            except Exception as e:
                self._transaction_states[txn_id] = TransactionState.FAILED
                await log(f"Error rolling back prepared transaction {txn_id}: {e}", level="error")
                return False
    
    async def start_distributed_transaction(self, participants: List[str]) -> str:
        """Start a new distributed transaction."""
        txn_id = f"dtx_{uuid.uuid4().hex}"
        async with self._lock:
            self._distributed_txns[txn_id] = {
                "start_time": time.time(),
                "participants": set(participants),
                "state": TransactionState.PREPARING
            }
            self._transaction_states[txn_id] = TransactionState.PREPARING
            self._transaction_participants[txn_id] = set(participants)
            self._transaction_metrics[txn_id] = {
                "start_time": time.time(),
                "participants": participants,
                "operations": [],
                "state": "started"
            }
            return txn_id

# Global instance (private)
_transaction_coordinator = None

# Public proxy for backward compatibility
transaction_coordinator = None

async def initialize_transaction_coordinator() -> None:
    """Initialize the global transaction coordinator instance and related components.
    This should be called during the DATABASE initialization stage."""
    global _transaction_coordinator, transaction_coordinator
    try:
        if _transaction_coordinator is None:
            _transaction_coordinator = await TransactionCoordinator.create()
            # Set public proxy
            transaction_coordinator = _transaction_coordinator
            
        # Initialize transaction monitor
        await transaction_monitor.initialize()
            
    except Exception as e:
        await log(f"Failed to initialize transaction coordinator: {e}", level="error")
        raise DatabaseError(f"Transaction coordinator initialization failed: {e}")

async def get_transaction_coordinator() -> TransactionCoordinator:
    """Get the global transaction coordinator instance."""
    global _transaction_coordinator
    if not _transaction_coordinator:
        raise DatabaseError("Transaction coordinator not initialized. Must call initialize_transaction_coordinator first.")
    return _transaction_coordinator

@asynccontextmanager
@handle_async_errors(error_types=(PostgresError, Neo4jError, TransactionError, CacheError, ConnectionError, Exception))
async def transaction_scope(invalidate_cache: bool = True, distributed: bool = False):
    """Context manager for coordinated transactions.
    
    Args:
        invalidate_cache: Whether to invalidate caches after transaction
        distributed: Whether to use distributed transaction protocol
    """
    if not _transaction_coordinator._initialized:
        await _transaction_coordinator.ensure_initialized()
    
    # Generate unique transaction ID
    txn_id = f"txn_{int(time.time() * 1000)}_{id(asyncio.current_task())}"
    
    try:
        async with _transaction_coordinator._lock:
            try:
                # Ensure connections are initialized
                await connection_manager.initialize_postgres()
                await connection_manager.initialize()
                
                # Start transaction monitoring
                await transaction_monitor.record_transaction_start(txn_id, {
                    "distributed": distributed,
                    "invalidate_cache": invalidate_cache,
                    "start_time": time.time()
                })
                
                if distributed:
                    # Start distributed transaction
                    txn_id = await _transaction_coordinator.start_distributed_transaction(
                        ["postgres", "neo4j"]  # List of participating databases
                    )
                
                # Register transaction with deadlock detector
                await deadlock_detector.register_resource_lock(txn_id, "postgres")
                await deadlock_detector.register_resource_lock(txn_id, "neo4j")
                
                # Start transactions
                await _transaction_coordinator._start_postgres()
                await _transaction_coordinator._start_neo4j()
                
                try:
                    yield _transaction_coordinator
                    
                    if distributed:
                        # Two-phase commit for distributed transactions
                        await transaction_monitor.record_transaction_operation(txn_id, {
                            "operation": "prepare",
                            "timestamp": time.time()
                        })
                        
                        # Prepare phase
                        if await _transaction_coordinator.prepare_transaction(txn_id):
                            await transaction_monitor.record_transaction_operation(txn_id, {
                                "operation": "commit",
                                "timestamp": time.time()
                            })
                            # Commit phase
                            await _transaction_coordinator.commit_prepared(txn_id)
                        else:
                            raise TransactionError("Transaction preparation failed")
                    else:
                        # Regular commit
                        await transaction_monitor.record_transaction_operation(txn_id, {
                            "operation": "commit",
                            "timestamp": time.time()
                        })
                        if _transaction_coordinator.pg_transaction:
                            await _transaction_coordinator.pg_transaction.commit()
                        if _transaction_coordinator.neo4j_transaction:
                            await _transaction_coordinator.neo4j_transaction.commit()
                    
                    # Handle cache invalidation
                    if invalidate_cache:
                        await _transaction_coordinator._invalidate_caches()
                    
                    # Record successful completion
                    await transaction_monitor.record_transaction_end(txn_id, "committed")
                    
                except Exception as e:
                    await transaction_monitor.record_transaction_operation(txn_id, {
                        "operation": "error",
                        "error": str(e),
                        "timestamp": time.time()
                    })
                    
                    if distributed:
                        # Rollback prepared transaction
                        await _transaction_coordinator.rollback_prepared(txn_id)
                    
                    # Record error
                    await transaction_monitor.record_transaction_end(txn_id, "failed", error=e)
                    log(f"Transaction scope error: {e}", level="error")
                    raise TransactionError(f"Transaction scope failed: {str(e)}")
                    
            except (PostgresError, Neo4jError, TransactionError, CacheError, ConnectionError, Exception) as e:
                # Record error for audit purposes
                from utils.error_handling import ErrorAudit
                future = submit_async_task(ErrorAudit.record_error(
                    e, 
                    "transaction_scope", 
                    (PostgresError, Neo4jError, TransactionError, CacheError, ConnectionError, Exception),
                    severity=ErrorSeverity.ERROR,
                    context={"txn_id": txn_id}
                ))
                _transaction_coordinator._pending_tasks.add(future)
                try:
                    await asyncio.wrap_future(future)
                finally:
                    _transaction_coordinator._pending_tasks.remove(future)
                raise
    finally:
        # Release resource locks
        await deadlock_detector.release_resource_lock(txn_id, "postgres")
        await deadlock_detector.release_resource_lock(txn_id, "neo4j")
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
        # New fields for enhanced detection
        self._resource_locks: Dict[str, Set[str]] = {}  # Resource -> Set of transactions
        self._transaction_resources: Dict[str, Set[str]] = {}  # Transaction -> Set of resources
        self._wait_for_graph: Dict[str, Set[str]] = {}  # Transaction -> Set of transactions it's waiting for
        self._deadlock_history: List[Dict[str, Any]] = []  # History of detected deadlocks
        self._resource_contention_stats: Dict[str, Dict[str, int]] = {}  # Resource contention statistics
        self._deadlock_patterns: Dict[str, int] = {}  # Patterns of deadlocks for analysis
    
    async def register_resource_lock(self, txn_id: str, resource_id: str, lock_type: str = "write") -> None:
        """Register a resource lock by a transaction."""
        async with self._lock:
            if resource_id not in self._resource_locks:
                self._resource_locks[resource_id] = set()
            
            # Check for potential conflicts
            if self._resource_locks[resource_id]:
                # Add edges to wait-for graph for conflicting transactions
                if txn_id not in self._wait_for_graph:
                    self._wait_for_graph[txn_id] = set()
                self._wait_for_graph[txn_id].update(self._resource_locks[resource_id])
            
            self._resource_locks[resource_id].add(txn_id)
            
            # Track resources held by transaction
            if txn_id not in self._transaction_resources:
                self._transaction_resources[txn_id] = set()
            self._transaction_resources[txn_id].add(resource_id)
            
            # Update contention stats
            if resource_id not in self._resource_contention_stats:
                self._resource_contention_stats[resource_id] = {"total_locks": 0, "conflicts": 0}
            self._resource_contention_stats[resource_id]["total_locks"] += 1
            if len(self._resource_locks[resource_id]) > 1:
                self._resource_contention_stats[resource_id]["conflicts"] += 1
    
    async def release_resource_lock(self, txn_id: str, resource_id: str) -> None:
        """Release a resource lock held by a transaction."""
        async with self._lock:
            if resource_id in self._resource_locks:
                self._resource_locks[resource_id].discard(txn_id)
                if not self._resource_locks[resource_id]:
                    del self._resource_locks[resource_id]
            
            if txn_id in self._transaction_resources:
                self._transaction_resources[txn_id].discard(resource_id)
                if not self._transaction_resources[txn_id]:
                    del self._transaction_resources[txn_id]
            
            # Clean up wait-for graph
            if txn_id in self._wait_for_graph:
                del self._wait_for_graph[txn_id]
            # Remove txn_id from other transactions' wait sets
            for waiting_set in self._wait_for_graph.values():
                waiting_set.discard(txn_id)
    
    async def check_for_deadlocks(self) -> List[Set[str]]:
        """Check for potential deadlocks in current transactions."""
        async with self._lock:
            deadlocks = []
            visited = set()
            
            # Check for cycles in wait-for graph
            for txn_id in self._wait_for_graph:
                if txn_id not in visited:
                    path = set()
                    if self._has_cycle(self._wait_for_graph, txn_id, visited, path):
                        deadlocks.append(path)
                        # Record deadlock pattern
                        pattern = self._get_deadlock_pattern(path)
                        self._deadlock_patterns[pattern] = self._deadlock_patterns.get(pattern, 0) + 1
            
            # Check for long-running transactions
            current_time = time.time()
            for txn_id, start_time in self._transaction_timestamps.items():
                if current_time - start_time > self._deadlock_timeout:
                    deadlocks.append({txn_id})
            
            # Record deadlocks in history
            for deadlock in deadlocks:
                self._record_deadlock(deadlock)
            
            return deadlocks
    
    def _get_deadlock_pattern(self, deadlock: Set[str]) -> str:
        """Generate a pattern string for a deadlock for analysis."""
        resources = set()
        for txn_id in deadlock:
            if txn_id in self._transaction_resources:
                resources.update(self._transaction_resources[txn_id])
        return f"resources:{len(resources)}_txns:{len(deadlock)}"
    
    def _record_deadlock(self, deadlock: Set[str]) -> None:
        """Record a deadlock for historical analysis."""
        self._deadlock_history.append({
            "timestamp": time.time(),
            "transactions": list(deadlock),
            "resources": [
                res for txn_id in deadlock
                for res in self._transaction_resources.get(txn_id, set())
            ],
            "wait_for_edges": {
                txn_id: list(self._wait_for_graph.get(txn_id, set()))
                for txn_id in deadlock
            }
        })
    
    async def get_resource_contention_report(self) -> Dict[str, Any]:
        """Get a report of resource contention statistics."""
        async with self._lock:
            return {
                "resource_stats": self._resource_contention_stats,
                "deadlock_patterns": self._deadlock_patterns,
                "recent_deadlocks": self._deadlock_history[-10:] if self._deadlock_history else [],
                "active_transactions": len(self._transaction_timestamps),
                "locked_resources": len(self._resource_locks),
                "wait_for_edges": sum(len(edges) for edges in self._wait_for_graph.values())
            }
    
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
                        
                        # Get detailed information about the deadlock
                        deadlock_info = {
                            "transactions": list(deadlock),
                            "resources": [
                                res for txn_id in deadlock
                                for res in self._transaction_resources.get(txn_id, set())
                            ],
                            "wait_for_edges": {
                                txn_id: list(self._wait_for_graph.get(txn_id, set()))
                                for txn_id in deadlock
                            },
                            "duration": time.time() - min(
                                self._transaction_timestamps[txn_id] 
                                for txn_id in deadlock
                            ),
                            "pattern": self._get_deadlock_pattern(deadlock)
                        }
                        
                        # Update health monitor with detailed information
                        await global_health_monitor.update_component_status(
                            "transaction_coordinator",
                            ComponentStatus.DEGRADED,
                            error=True,
                            details={
                                "deadlock_info": deadlock_info,
                                "resource_contention": await self.get_resource_contention_report()
                            }
                        )
                    
                    await asyncio.sleep(1.0)  # Check every second during deadlock
                else:
                    # Update healthy status with monitoring information
                    await global_health_monitor.update_component_status(
                        "transaction_coordinator",
                        ComponentStatus.HEALTHY,
                        details={
                            "active_transactions": len(self._transaction_timestamps),
                            "locked_resources": len(self._resource_locks),
                            "wait_for_edges": len(self._wait_for_graph),
                            "monitoring_status": "active",
                            "last_check": time.time()
                        }
                    )
                    
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
        self._resource_locks.clear()
        self._transaction_resources.clear()
        self._wait_for_graph.clear()
        self._deadlock_history.clear()
        self._resource_contention_stats.clear()
        self._deadlock_patterns.clear()
        
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

class TransactionMonitor:
    """Monitors and analyzes transaction performance and health."""
    
    def __init__(self):
        self._lock = asyncio.Lock()
        self._transaction_metrics: Dict[str, Dict[str, Any]] = {}
        self._performance_stats: Dict[str, List[float]] = {
            "commit_times": [],
            "rollback_times": [],
            "prepare_times": [],
            "total_times": []
        }
        self._error_stats: Dict[str, int] = {
            "commit_errors": 0,
            "rollback_errors": 0,
            "prepare_errors": 0,
            "deadlock_errors": 0,
            "timeout_errors": 0
        }
        self._monitoring = False
        self._monitor_task = None
        self._pending_tasks: Set[asyncio.Task] = set()
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize and start the transaction monitor."""
        if self._initialized:
            return
            
        try:
            # Update initialization status
            await global_health_monitor.update_component_status(
                "transaction_monitor",
                ComponentStatus.INITIALIZING,
                details={"stage": "starting"}
            )
            
            # Start monitoring
            await self.start_monitoring()
            
            self._initialized = True
            
            # Update final status
            await global_health_monitor.update_component_status(
                "transaction_monitor",
                ComponentStatus.HEALTHY,
                details={"stage": "complete"}
            )
            
        except Exception as e:
            await log(f"Failed to initialize transaction monitor: {e}", level="error")
            await global_health_monitor.update_component_status(
                "transaction_monitor",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"initialization_error": str(e)}
            )
            raise DatabaseError(f"Transaction monitor initialization failed: {e}")
    
    async def start_monitoring(self):
        """Start transaction monitoring."""
        async with self._lock:
            if self._monitoring:
                return
            self._monitoring = True
            self._monitor_task = asyncio.create_task(self._monitor_transactions())
            self._pending_tasks.add(self._monitor_task)
    
    async def stop_monitoring(self):
        """Stop transaction monitoring."""
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
    
    async def record_transaction_start(self, txn_id: str, details: Dict[str, Any]) -> None:
        """Record the start of a transaction."""
        async with self._lock:
            self._transaction_metrics[txn_id] = {
                "start_time": time.time(),
                "details": details,
                "operations": [],
                "state": "started"
            }
    
    async def record_transaction_operation(self, txn_id: str, operation: Dict[str, Any]) -> None:
        """Record an operation within a transaction."""
        async with self._lock:
            if txn_id in self._transaction_metrics:
                self._transaction_metrics[txn_id]["operations"].append({
                    **operation,
                    "timestamp": time.time()
                })
    
    async def record_transaction_end(self, txn_id: str, status: str, error: Optional[Exception] = None) -> None:
        """Record the end of a transaction."""
        async with self._lock:
            if txn_id in self._transaction_metrics:
                end_time = time.time()
                metrics = self._transaction_metrics[txn_id]
                duration = end_time - metrics["start_time"]
                
                metrics.update({
                    "end_time": end_time,
                    "duration": duration,
                    "status": status,
                    "error": str(error) if error else None
                })
                
                # Update performance stats
                self._performance_stats["total_times"].append(duration)
                if status == "committed":
                    self._performance_stats["commit_times"].append(duration)
                elif status == "rolled_back":
                    self._performance_stats["rollback_times"].append(duration)
                
                # Update error stats if applicable
                if error:
                    error_type = type(error).__name__
                    if "deadlock" in str(error).lower():
                        self._error_stats["deadlock_errors"] += 1
                    elif "timeout" in str(error).lower():
                        self._error_stats["timeout_errors"] += 1
                    elif status == "commit_failed":
                        self._error_stats["commit_errors"] += 1
                    elif status == "rollback_failed":
                        self._error_stats["rollback_errors"] += 1
    
    async def get_transaction_metrics(self, txn_id: str) -> Optional[Dict[str, Any]]:
        """Get metrics for a specific transaction."""
        async with self._lock:
            return self._transaction_metrics.get(txn_id)
    
    async def get_performance_report(self) -> Dict[str, Any]:
        """Get a comprehensive performance report."""
        async with self._lock:
            def calculate_stats(times: List[float]) -> Dict[str, float]:
                if not times:
                    return {"avg": 0.0, "min": 0.0, "max": 0.0, "p95": 0.0}
                return {
                    "avg": sum(times) / len(times),
                    "min": min(times),
                    "max": max(times),
                    "p95": sorted(times)[int(len(times) * 0.95)]
                }
            
            return {
                "performance": {
                    metric: calculate_stats(times)
                    for metric, times in self._performance_stats.items()
                },
                "errors": self._error_stats.copy(),
                "active_transactions": len(self._transaction_metrics),
                "completed_transactions": len([
                    txn for txn in self._transaction_metrics.values()
                    if "end_time" in txn
                ]),
                "error_rate": sum(self._error_stats.values()) / max(len(self._transaction_metrics), 1)
            }
    
    async def _monitor_transactions(self):
        """Background task to monitor transaction health."""
        while self._monitoring:
            try:
                # Get current performance report
                report = await self.get_performance_report()
                
                # Update health monitor
                status = ComponentStatus.HEALTHY
                if report["error_rate"] > 0.1:  # More than 10% errors
                    status = ComponentStatus.DEGRADED
                if report["error_rate"] > 0.3:  # More than 30% errors
                    status = ComponentStatus.UNHEALTHY
                
                await global_health_monitor.update_component_status(
                    "transaction_monitor",
                    status,
                    error=status != ComponentStatus.HEALTHY,
                    details={
                        "performance_metrics": report["performance"],
                        "error_stats": report["errors"],
                        "active_transactions": report["active_transactions"],
                        "error_rate": report["error_rate"]
                    }
                )
                
                await asyncio.sleep(5.0)  # Check every 5 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                await log(f"Error in transaction monitor: {e}", level="error")
                await asyncio.sleep(5.0)  # Back off on error
    
    async def cleanup(self):
        """Clean up resources."""
        await self.stop_monitoring()
        self._transaction_metrics.clear()
        self._performance_stats = {
            "commit_times": [],
            "rollback_times": [],
            "prepare_times": [],
            "total_times": []
        }
        self._error_stats = {
            "commit_errors": 0,
            "rollback_errors": 0,
            "prepare_errors": 0,
            "deadlock_errors": 0,
            "timeout_errors": 0
        }
        
        # Cancel any remaining tasks
        if self._pending_tasks:
            for task in self._pending_tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*self._pending_tasks, return_exceptions=True)
            self._pending_tasks.clear()

# Create global instance
transaction_monitor = TransactionMonitor()

# Register cleanup handler
register_shutdown_handler(transaction_monitor.cleanup) 