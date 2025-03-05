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
    retry_manager,
    with_retry
)
from .schema import schema_manager
from .transaction import transaction_scope, transaction_coordinator

from utils.logger import log
from utils.error_handling import handle_async_errors, AsyncErrorBoundary
from utils.shutdown import register_shutdown_handler
from utils.async_runner import submit_async_task, get_loop

# Create coordinator instance
upsert_coordinator = UpsertCoordinator()

# Initialize database components
async def initialize_databases():
    """Initialize all database components with AI support."""
    try:
        # Initialize schema first
        await schema_manager.create_all_tables()
        log("Database schema initialized with AI pattern support", level="info")
        
        # Initialize connections with AI operation settings
        await connection_manager.initialize()
        log("Database connections initialized with AI support", level="info")
        
        # Initialize upsert coordinator
        await upsert_coordinator.initialize()
        log("Upsert coordinator initialized with AI pattern support", level="info")
        
        # Initialize graph sync with AI enhancements
        await graph_sync.initialize()
        log("Graph sync initialized with AI pattern support", level="info")
        
        # Initialize retry manager with AI-specific settings
        await retry_manager.initialize()
        log("Retry manager initialized with AI operation support", level="info")
        
        log("All database components initialized with AI support", level="info")
    except Exception as e:
        log(f"Error initializing database components: {e}", level="error")
        raise

# Register cleanup handler
async def cleanup_databases():
    """Cleanup all database components."""
    try:
        # Cleanup in reverse initialization order
        await retry_manager.cleanup()
        await graph_sync.cleanup()
        await upsert_coordinator.cleanup()
        await connection_manager.cleanup()
        await schema_manager.cleanup()
        log("All database components cleaned up", level="info")
    except Exception as e:
        log(f"Error cleaning up database components: {e}", level="error")

register_shutdown_handler(cleanup_databases)

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
    "retry_manager",
    "with_retry",
    
    # Schema management
    "schema_manager",
    
    # Transaction management
    "transaction_scope",
    "transaction_coordinator"
] 