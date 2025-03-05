"""[6.0] Database Layer Integration.

Flow:
1. Database Operations:
   - PostgreSQL: Code, docs, embeddings storage
   - Neo4j: Graph relationships and analysis
   - Transaction coordination across DBs
   - Retry mechanisms for handling transient failures

2. Integration Points:
   - FileProcessor [2.0] -> upsert_ops.py: Store processed files
   - SearchEngine [5.0] -> psql.py: Vector similarity search
   - UnifiedIndexer [1.0] -> graph_sync.py: Graph projections

3. Components:
   - connection.py [6.1]: Centralized database connection management
   - psql.py [6.2]: PostgreSQL operations
   - neo4j_ops.py [6.3]: Neo4j operations and graph management
   - graph_sync.py [6.4]: Graph projection coordination
   - transaction.py [6.5]: Multi-DB transaction management
   - upsert_ops.py [6.6]: Unified data storage operations
   - schema.py [6.7]: Database schema management
   - retry_utils.py [6.8]: Database retry mechanisms with exponential backoff
"""

from .connection import connection_manager
from .psql import (
    query,
    execute,
    execute_many,
    execute_batch,
    execute_parallel_queries
)
from .upsert_ops import (
    upsert_doc,
    upsert_code_snippet
)
from .neo4j_ops import (
    Neo4jTools,
    run_query,
    run_query_with_retry,
    projections,
    neo4j_tools
)
from .graph_sync import graph_sync
from .retry_utils import (
    RetryableError,
    NonRetryableError,
    RetryableNeo4jError,
    NonRetryableNeo4jError,
    RetryConfig,
    DatabaseRetryManager,
    default_retry_manager
)
from .schema import schema_manager
from .transaction import transaction_scope

from utils.app_init import register_shutdown_handler
from utils.logger import log
from utils.async_runner import submit_async_task, get_loop

# Initialize database components
async def initialize_databases():
    """Initialize all database components."""
    try:
        # Initialize schema first
        await schema_manager.create_all_tables()
        log("Database schema initialized", level="info")
        
        # Initialize connections
        await connection_manager.initialize_postgres()
        await connection_manager.initialize()
        log("Database connections initialized", level="info")
        
        # Initialize graph sync
        await graph_sync.initialize()
        log("Graph sync initialized", level="info")
        
        log("All database components initialized", level="info")
    except Exception as e:
        log(f"Error initializing database components: {e}", level="error")
        raise

# Register cleanup handler
async def cleanup_databases():
    """Cleanup all database components."""
    try:
        # Cleanup in reverse initialization order
        await graph_sync.cleanup()
        await connection_manager.cleanup()
        await schema_manager.cleanup()
        await default_retry_manager.cleanup()
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
    
    # Data storage operations
    "upsert_doc",
    "upsert_code_snippet",
    
    # Neo4j operations
    "Neo4jTools",
    "run_query",
    "run_query_with_retry",
    "projections",
    "neo4j_tools",
    
    # Graph operations
    "graph_sync",
    
    # Retry utilities
    "RetryableError",
    "NonRetryableError",
    "RetryableNeo4jError",
    "NonRetryableNeo4jError",
    "RetryConfig",
    "DatabaseRetryManager",
    "default_retry_manager",
    
    # Schema management
    "schema_manager",
    
    # Transaction management
    "transaction_scope"
] 