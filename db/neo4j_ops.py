"""[6.3] Neo4j operations and graph management.

This module provides high-level Neo4j operations using the centralized connection manager.
All connection management is handled by the connection_manager.
"""

from typing import Dict, Any, Optional, List, Set, Tuple
import asyncio
from db.connection import connection_manager
from db.transaction import transaction_scope
from db.retry_utils import (
    with_retry, 
    RetryableNeo4jError, 
    NonRetryableNeo4jError,
    default_retry_manager,
    is_retryable_error
)
from utils.logger import log
from utils.error_handling import (
    handle_errors,
    handle_async_errors,
    DatabaseError,
    AsyncErrorBoundary,
    Neo4jError,
    TransactionError,
    ErrorSeverity
)
from parsers.types import (
    ExtractedFeatures,
    FeatureCategory
)
from utils.async_runner import submit_async_task, get_loop
from utils.shutdown import register_shutdown_handler

# Create a function to get the graph_sync instance to avoid circular imports
async def get_graph_sync():
    """Get the graph_sync instance."""
    from db.graph_sync import get_graph_sync as _get_graph_sync
    return await _get_graph_sync()

class Neo4jTools:
    """Neo4j database operations coordinator."""
    
    def __init__(self):
        """Private constructor - use create() instead."""
        self._pending_tasks: Set[asyncio.Task] = set()
        self._initialized = False
    
    async def ensure_initialized(self):
        """Ensure the instance is properly initialized before use."""
        if not self._initialized:
            raise DatabaseError("Neo4jTools instance not initialized. Use create() to initialize.")
        return True
    
    @classmethod
    async def create(cls) -> 'Neo4jTools':
        """Async factory method to create and initialize a Neo4jTools instance."""
        instance = cls()
        try:
            async with AsyncErrorBoundary(
                operation_name="Neo4j tools initialization",
                error_types=DatabaseError,
                severity=ErrorSeverity.CRITICAL
            ):
                # Initialize connection
                await connection_manager.initialize()
                
                # Register shutdown handler
                register_shutdown_handler(instance.cleanup)
                
                # Initialize health monitoring
                from utils.health_monitor import global_health_monitor
                global_health_monitor.register_component("neo4j_tools")
                
                instance._initialized = True
                await log("Neo4j tools initialized", level="info")
                return instance
        except Exception as e:
            await log(f"Error initializing Neo4j tools: {e}", level="error")
            raise DatabaseError(f"Failed to initialize Neo4j tools: {e}")
    
    async def cleanup(self):
        """Clean up Neo4j tools resources."""
        try:
            # Cancel all pending tasks
            if self._pending_tasks:
                for task in self._pending_tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                self._pending_tasks.clear()
            
            # Clean up connection manager
            await connection_manager.cleanup()
            
            # Unregister from health monitoring
            from utils.health_monitor import global_health_monitor
            global_health_monitor.unregister_component("neo4j_tools")
            
            self._initialized = False
            await log("Neo4j tools cleaned up", level="info")
        except Exception as e:
            await log(f"Error cleaning up Neo4j tools: {e}", level="error")
            raise DatabaseError(f"Failed to cleanup Neo4j tools: {e}")

    @handle_async_errors(error_types=DatabaseError)
    async def store_code_node(self, code_data: dict) -> None:
        """Store code node with transaction coordination."""
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary(
            "Neo4j node storage",
            error_types=(Neo4jError, TransactionError),
            severity=ErrorSeverity.ERROR
        ):
            async with transaction_scope() as txn:
                query = """
                MERGE (n:Code {repo_id: $repo_id, file_path: $file_path})
                SET n += $properties
                """
                await txn.neo4j_transaction.run(query, {
                    "repo_id": code_data["repo_id"],
                    "file_path": code_data["file_path"],
                    "properties": code_data
                })
                
                log("Stored code node", level="debug", context={
                    "operation": "store_code_node",
                    "repo_id": code_data["repo_id"],
                    "file_path": code_data["file_path"]
                })

    @handle_async_errors(error_types=DatabaseError)
    async def update_code_relationships(self, repo_id: int, relationships: list) -> None:
        """Update code relationships with graph synchronization."""
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary(
            "Neo4j relationship update",
            error_types=DatabaseError,
            severity=ErrorSeverity.ERROR
        ):
            query = """
            UNWIND $relationships as rel
            MATCH (s:Code {repo_id: $repo_id, file_path: rel.source})
            MATCH (t:Code {repo_id: $repo_id, file_path: rel.target})
            MERGE (s)-[r:rel.type]->(t)
            """
            await run_query(query, {
                "repo_id": repo_id,
                "relationships": relationships
            })
            
            graph_sync = await get_graph_sync()
            await graph_sync.invalidate_projection(repo_id)
            await graph_sync.ensure_projection(repo_id)

# Create singleton instance
_neo4j_tools = Neo4jTools()

# Export with proper async handling
async def get_neo4j_tools() -> Neo4jTools:
    """Get the Neo4j tools instance.
    
    Returns:
        Neo4jTools: The singleton Neo4j tools instance
    """
    if not _neo4j_tools._initialized:
        await _neo4j_tools.initialize()
    return _neo4j_tools

# For backward compatibility and direct access
neo4j_tools = _neo4j_tools

# Update the run_query function to properly classify errors
@with_retry()
async def run_query(query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Run a Neo4j query and return results."""
    session = await connection_manager.get_session()
    try:
        async with AsyncErrorBoundary("neo4j_query_execution"):
            result = await session.run(query, params or {})
            data = await result.data()
            return data
    except Exception as e:
        error_msg = str(e).lower()
        if not is_retryable_error(e):
            raise NonRetryableNeo4jError(f"Non-retryable error: {error_msg}")
        raise RetryableNeo4jError(f"Retryable error: {error_msg}")
    finally:
        await session.close()

async def cleanup_neo4j():
    """Cleanup Neo4j resources."""
    try:
        await _neo4j_tools.cleanup()
        await default_retry_manager.cleanup()
        log("Neo4j resources cleaned up", level="info")
    except Exception as e:
        log(f"Error cleaning up Neo4j resources: {e}", level="error")

register_shutdown_handler(cleanup_neo4j)

@handle_async_errors(error_types=(DatabaseError, Neo4jError))
async def create_schema_indexes_and_constraints():
    """Create Neo4j schema indexes and constraints."""
    async with AsyncErrorBoundary(
        operation_name="creating_schema_indexes",
        error_types=(Neo4jError, DatabaseError),
        reraise=False,
        severity=ErrorSeverity.CRITICAL
    ) as boundary:
        session = await connection_manager.get_session()
        try:
            # Create indexes for different node types
            await run_query("CREATE INDEX IF NOT EXISTS FOR (c:Code) ON (c.repo_id, c.file_path)")
            await run_query("CREATE INDEX IF NOT EXISTS FOR (d:Documentation) ON (d.repo_id, d.path)")
            await run_query("CREATE INDEX IF NOT EXISTS FOR (r:Repository) ON (r.id)")
            await run_query("CREATE INDEX IF NOT EXISTS FOR (l:Language) ON (l.name)")
            await run_query("CREATE INDEX IF NOT EXISTS FOR (p:Pattern) ON (p.id)")
            await run_query("CREATE INDEX IF NOT EXISTS FOR (f:Feature) ON (f.name)")
            
            # Create constraints for uniqueness
            await run_query("CREATE CONSTRAINT IF NOT EXISTS FOR (r:Repository) REQUIRE r.id IS UNIQUE")
            await run_query("CREATE CONSTRAINT IF NOT EXISTS FOR (c:Code) REQUIRE (c.repo_id, c.file_path) IS UNIQUE")
            await run_query("CREATE CONSTRAINT IF NOT EXISTS FOR (p:Pattern) REQUIRE p.id IS UNIQUE")
            
            log("Created Neo4j schema indexes and constraints", level="info")
        finally:
            await session.close()
    
    if boundary.error:
        error_msg = f"Error creating Neo4j schema indexes and constraints: {str(boundary.error)}"
        log(error_msg, level="error")
        raise DatabaseError(error_msg)
    
    return True

class Neo4jProjections:
    """[6.2.9] Neo4j graph projections and algorithms for pattern analysis."""
    
    def __init__(self):
        self._pending_tasks: Set[asyncio.Task] = set()
        self._lock = asyncio.Lock()
    
    @handle_async_errors(error_types=DatabaseError)
    async def run_pattern_similarity(self, repo_id: int) -> List[Dict[str, Any]]:
        """Run similarity algorithm to identify similar patterns."""
        # Ensure pattern projection exists
        graph_sync = await get_graph_sync()
        await graph_sync.ensure_pattern_projection(repo_id)
        graph_name = f"pattern-repo-{repo_id}"
        
        query = """
        CALL gds.nodeSimilarity.stream($graph_name)
        YIELD node1, node2, similarity
        WITH gds.util.asNode(node1) AS pattern1, 
             gds.util.asNode(node2) AS pattern2, 
             similarity
        WHERE pattern1:Pattern AND pattern2:Pattern AND similarity > 0.5
        RETURN pattern1.pattern_id AS pattern1_id, 
               pattern2.pattern_id AS pattern2_id,
               pattern1.pattern_type AS pattern_type, 
               similarity
        ORDER BY similarity DESC
        LIMIT 100
        """
        return await run_query(query, {"graph_name": graph_name})
    
    @handle_async_errors(error_types=DatabaseError)
    async def find_pattern_clusters(self, repo_id: int) -> List[Dict[str, Any]]:
        """Find clusters of similar patterns using community detection."""
        # Ensure pattern projection exists
        graph_sync = await get_graph_sync()
        await graph_sync.ensure_pattern_projection(repo_id)
        graph_name = f"pattern-repo-{repo_id}"
        
        query = """
        CALL gds.louvain.stream($graph_name)
        YIELD nodeId, communityId
        WITH gds.util.asNode(nodeId) AS node, communityId
        WHERE node:Pattern
        RETURN communityId, 
               collect(node.pattern_id) AS patterns,
               collect(node.pattern_type) AS pattern_types,
               count(*) AS cluster_size
        ORDER BY cluster_size DESC
        """
        task = asyncio.create_task(run_query(query, {"graph_name": graph_name}))
        self._pending_tasks.add(task)
        try:
            results = await task
            return results
        finally:
            self._pending_tasks.remove(task)
    
    @handle_async_errors(error_types=DatabaseError)
    async def get_component_dependencies(self, repo_id: int) -> List[Dict[str, Any]]:
        """Get dependencies between top-level components."""
        # Ensure code projection exists
        graph_sync = await get_graph_sync()
        await graph_sync.ensure_projection(repo_id)
        
        query = """
        MATCH (c1:Code)-[:IMPORTS|CALLS|DEPENDS_ON]->(c2:Code)
        WITH split(c1.file_path, '/')[0] AS comp1, 
             split(c2.file_path, '/')[0] AS comp2, 
             count(*) AS weight
        WHERE comp1 <> comp2
        RETURN comp1 AS source_component, 
               comp2 AS target_component, 
               weight
        ORDER BY weight DESC
        """
        task = asyncio.create_task(run_query(query, {}))
        self._pending_tasks.add(task)
        try:
            results = await task
            return results
        finally:
            self._pending_tasks.remove(task)
    
    @handle_errors(error_types=(Exception,))
    async def close(self):
        """Clean up any pending tasks."""
        if self._pending_tasks:
            await asyncio.gather(*self._pending_tasks, return_exceptions=True)
            self._pending_tasks.clear()

# Create global instance
projections = Neo4jProjections() 