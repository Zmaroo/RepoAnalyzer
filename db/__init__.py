"""[6.0] Database Layer Integration with AI Support.

Flow:
1. Database Operations:
   - PostgreSQL: Code, docs, embeddings, and AI pattern storage
   - Neo4j: Graph relationships, AI insights, and pattern analysis
   - Transaction coordination with AI operation support
   - Retry mechanisms optimized for AI workloads

2. Integration Points:
   - FileProcessor [2.0] -> upsert_ops.py: Store processed files with AI insights
   - SearchEngine [5.0] -> psql.py: Vector similarity search for patterns
   - UnifiedIndexer [1.0] -> graph_sync.py: Graph projections with AI enhancements
   - AIPatternProcessor [3.0] -> pattern_storage.py: AI pattern analysis

3. Components:
   - connection.py [6.1]: Database connection management with AI operation support
   - psql.py [6.2]: PostgreSQL operations optimized for AI workloads
   - neo4j_ops.py [6.3]: Neo4j operations with AI pattern management
   - graph_sync.py [6.4]: Graph projection coordination with AI insights
   - transaction.py [6.5]: Multi-DB transaction management for AI operations
   - upsert_ops.py [6.6]: Unified data storage with AI enhancements
   - schema.py [6.7]: Database schema with AI pattern support
   - retry_utils.py [6.8]: Retry mechanisms optimized for AI operations
"""

import asyncio
from typing import Dict, Any

from .connection import connection_manager
from .psql import (
    query,
    execute,
    execute_many,
    execute_batch,
    execute_parallel_queries,
    execute_vector_similarity_search,
    execute_pattern_metrics_update
)
from .upsert_ops import UpsertCoordinator
from .neo4j_ops import (
    Neo4jTools,
    run_query,
    projections,
    neo4j_tools,
    store_pattern_node,
    store_pattern_relationships,
    find_similar_patterns,
    get_pattern_insights,
    analyze_pattern_trends
)
from .graph_sync import graph_sync
from .retry_utils import (
    RetryableError,
    NonRetryableError,
    RetryableNeo4jError,
    NonRetryableNeo4jError,
    RetryConfig,
    RetryManager,
    get_retry_manager,
    with_retry
)
from .schema import schema_manager
from .transaction import transaction_scope, transaction_coordinator

from utils.logger import log
from utils.error_handling import (
    handle_async_errors, 
    AsyncErrorBoundary, 
    ErrorAudit,
    ErrorSeverity,
    DatabaseError
)
from utils.shutdown import register_shutdown_handler
from utils.async_runner import submit_async_task, get_loop
from utils.health_monitor import global_health_monitor, ComponentStatus
import time

class DatabaseInitializer:
    """Manages database initialization with health monitoring."""
    
    def __init__(self):
        """Initialize the database initializer."""
        self._initialized = False
        self._metrics = {
            "total_initializations": 0,
            "successful_initializations": 0,
            "failed_initializations": 0,
            "initialization_times": []
        }
        self._pending_tasks = set()
    
    async def _check_health(self) -> Dict[str, Any]:
        """Health check for database initialization."""
        # Calculate average initialization time
        avg_init_time = sum(self._metrics["initialization_times"]) / len(self._metrics["initialization_times"]) if self._metrics["initialization_times"] else 0
        
        # Calculate health status
        status = ComponentStatus.HEALTHY
        details = {
            "metrics": {
                "total_initializations": self._metrics["total_initializations"],
                "success_rate": self._metrics["successful_initializations"] / self._metrics["total_initializations"] if self._metrics["total_initializations"] > 0 else 0,
                "avg_initialization_time": avg_init_time
            }
        }
        
        # Check for degraded conditions
        if details["metrics"]["success_rate"] < 0.8:
            status = ComponentStatus.DEGRADED
            details["reason"] = "Low initialization success rate"
        elif avg_init_time > 5.0:  # More than 5 seconds
            status = ComponentStatus.DEGRADED
            details["reason"] = "High initialization times"
        
        return {
            "status": status,
            "details": details
        }
    
    @handle_async_errors(error_types=(DatabaseError,))
    async def initialize(self):
        """Initialize all database components with AI support."""
        if self._initialized:
            return
        
        start_time = time.time()
        self._metrics["total_initializations"] += 1
        
        try:
            async with AsyncErrorBoundary(
                operation_name="database_initialization",
                error_types=(DatabaseError,),
                severity=ErrorSeverity.CRITICAL
            ):
                # Initialize schema first
                await schema_manager.create_all_tables()
                await log("Database schema initialized with AI pattern support", level="info")
                
                # Initialize connections with AI operation settings
                await connection_manager.initialize()
                await log("Database connections initialized with AI support", level="info")
                
                # Initialize upsert coordinator
                await upsert_coordinator.initialize()
                await log("Upsert coordinator initialized with AI pattern support", level="info")
                
                # Initialize graph sync with AI enhancements
                await graph_sync.initialize()
                await log("Graph sync initialized with AI pattern support", level="info")
                
                # Initialize retry manager with AI-specific settings
                await get_retry_manager.initialize()
                await log("Retry manager initialized with AI operation support", level="info")
                
                # Update metrics
                self._metrics["successful_initializations"] += 1
                init_time = time.time() - start_time
                self._metrics["initialization_times"].append(init_time)
                
                # Update health status
                await global_health_monitor.update_component_status(
                    "database_initialization",
                    ComponentStatus.HEALTHY,
                    response_time=init_time * 1000,  # Convert to ms
                    error=False
                )
                
                self._initialized = True
                await log("All database components initialized with AI support", level="info")
        except Exception as e:
            self._metrics["failed_initializations"] += 1
            
            # Record error for audit
            await ErrorAudit.record_error(
                e,
                "database_initialization",
                DatabaseError,
                severity=ErrorSeverity.CRITICAL
            )
            
            # Update health status
            await global_health_monitor.update_component_status(
                "database_initialization",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"error": str(e)}
            )
            
            await log(f"Error initializing database components: {e}", level="error")
            raise
    
    async def cleanup(self):
        """Cleanup all database components."""
        try:
            async with AsyncErrorBoundary(
                operation_name="database_cleanup",
                error_types=(Exception,),
                severity=ErrorSeverity.ERROR
            ):
                # Cleanup in reverse initialization order
                await get_retry_manager.cleanup()
                await graph_sync.cleanup()
                await upsert_coordinator.cleanup()
                await connection_manager.cleanup()
                await schema_manager.cleanup()
                
                # Cancel any pending tasks
                if self._pending_tasks:
                    for task in self._pending_tasks:
                        if not task.done():
                            task.cancel()
                    await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                    self._pending_tasks.clear()
                
                # Update health status
                await global_health_monitor.update_component_status(
                    "database_initialization",
                    ComponentStatus.HEALTHY,
                    error=False,
                    details={"operation": "cleanup_completed"}
                )
                
                self._initialized = False
                await log("All database components cleaned up", level="info")
        except Exception as e:
            # Record error for audit
            await ErrorAudit.record_error(
                e,
                "database_cleanup",
                Exception,
                severity=ErrorSeverity.ERROR
            )
            
            # Update health status
            await global_health_monitor.update_component_status(
                "database_initialization",
                ComponentStatus.DEGRADED,
                error=True,
                details={"error": str(e)}
            )
            
            await log(f"Error cleaning up database components: {e}", level="error")

# Create coordinator instance
upsert_coordinator = UpsertCoordinator()

# Create database initializer instance
db_initializer = DatabaseInitializer()

# Register with health monitor
global_health_monitor.register_component(
    "database_initialization",
    health_check=db_initializer._check_health
)

# Register cleanup handler
register_shutdown_handler(db_initializer.cleanup)

# Initialize module asynchronously
from utils.async_runner import submit_async_task
submit_async_task(db_initializer.initialize())

# Export all necessary components
__all__ = [
    # Connection management
    "connection_manager",
    
    # PostgreSQL operations
    "query",
    "execute",
    "execute_many",
    "execute_batch",
    "execute_parallel_queries",
    "execute_vector_similarity_search",
    "execute_pattern_metrics_update",
    
    # Data storage operations
    "upsert_coordinator",
    
    # Neo4j operations
    "Neo4jTools",
    "run_query",
    "projections",
    "neo4j_tools",
    "store_pattern_node",
    "store_pattern_relationships",
    "find_similar_patterns",
    "get_pattern_insights",
    "analyze_pattern_trends",
    
    # Graph operations
    "graph_sync",
    
    # Retry utilities
    "RetryableError",
    "NonRetryableError",
    "RetryableNeo4jError",
    "NonRetryableNeo4jError",
    "RetryConfig",
    "RetryManager",
    "get_retry_manager",
    "with_retry",
    
    # Schema management
    "schema_manager",
    
    # Transaction management
    "transaction_scope",
    "transaction_coordinator",
    
    # Database initialization
    "db_initializer"
] 