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
   - psql.py [6.1]: PostgreSQL connection and queries
   - neo4j_ops.py [6.2]: Neo4j operations and graph management
   - graph_sync.py [6.3]: Graph projection coordination
   - transaction.py [6.4]: Multi-DB transaction management
   - upsert_ops.py [6.5]: Unified data storage operations
   - schema.py [6.6]: Database schema management
   - retry_utils.py [6.7]: Database retry mechanisms with exponential backoff
"""

from .psql import (
    query,
    execute,
    init_db_pool,
    close_db_pool,
    get_connection,
    release_connection,
)
# postgres upserts
from .upsert_ops import (
    upsert_doc,
    upsert_code_snippet
)
from .neo4j_ops import (
    Neo4jTools,
    run_query,
    run_query_with_retry,
    driver,
)
from .graph_sync import graph_sync
from .retry_utils import (
    with_retry,
    RetryableError,
    NonRetryableError,
    RetryableNeo4jError,
    NonRetryableNeo4jError,
    RetryConfig,
    DatabaseRetryManager,
    default_retry_manager
)


__all__ = [
    # PostgreSQL operations
    "query",
    "execute",
    "init_db_pool",
    "close_db_pool",
    "get_connection",
    "release_connection",
    "upsert_doc",
    "upsert_code_snippet",
    
    # Neo4j operations
    "run_query",
    "run_query_with_retry",
    "driver",
    "Neo4jTools",
    "graph_sync",
    "search_docs_common",
    
    # Retry utilities
    "with_retry",
    "RetryableError",
    "NonRetryableError",
    "RetryableNeo4jError",
    "NonRetryableNeo4jError",
    "RetryConfig",
    "DatabaseRetryManager",
    "default_retry_manager"
] 