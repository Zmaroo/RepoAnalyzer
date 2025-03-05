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

@handle_async_errors(error_types=DatabaseError)
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
            
            # Enhanced pattern indexes
            await run_query("CREATE INDEX IF NOT EXISTS FOR (p:Pattern) ON (p.id, p.type)")
            await run_query("CREATE INDEX IF NOT EXISTS FOR (p:Pattern) ON (p.confidence)")
            await run_query("CREATE INDEX IF NOT EXISTS FOR (p:Pattern) ON (p.ai_confidence)")
            await run_query("CREATE INDEX IF NOT EXISTS FOR (p:Pattern) ON (p.language)")
            
            # AI-specific indexes
            await run_query("CREATE INDEX IF NOT EXISTS FOR (ai:AIInsight) ON (ai.type)")
            await run_query("CREATE INDEX IF NOT EXISTS FOR (ai:AIMetric) ON (ai.metric_type)")
            await run_query("CREATE INDEX IF NOT EXISTS FOR (ai:AIRecommendation) ON (ai.priority)")
            
            # Create constraints for uniqueness
            await run_query("CREATE CONSTRAINT IF NOT EXISTS FOR (r:Repository) REQUIRE r.id IS UNIQUE")
            await run_query("CREATE CONSTRAINT IF NOT EXISTS FOR (c:Code) REQUIRE (c.repo_id, c.file_path) IS UNIQUE")
            await run_query("CREATE CONSTRAINT IF NOT EXISTS FOR (p:Pattern) REQUIRE p.id IS UNIQUE")
            await run_query("CREATE CONSTRAINT IF NOT EXISTS FOR (ai:AIInsight) REQUIRE ai.id IS UNIQUE")
            
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

@handle_async_errors(error_types=DatabaseError)
async def store_pattern_node(pattern_data: dict) -> None:
    """Store pattern node with AI enhancements."""
    session = await connection_manager.get_session()
    try:
        # Create pattern node
        pattern_query = """
        MERGE (p:Pattern {id: $id})
        SET p += $properties,
            p.updated_at = timestamp()
        """
        pattern_props = {
            "id": pattern_data["pattern_id"],
            "type": pattern_data["pattern_type"],
            "language": pattern_data.get("language"),
            "confidence": pattern_data.get("confidence", 0.7),
            "ai_confidence": pattern_data.get("ai_confidence"),
            "complexity": pattern_data.get("complexity"),
            "embedding": pattern_data.get("embedding")
        }
        
        await session.run(pattern_query, {
            "id": pattern_data["pattern_id"],
            "properties": pattern_props
        })
        
        # Store AI insights if available
        if pattern_data.get("ai_insights"):
            insights_query = """
            MATCH (p:Pattern {id: $pattern_id})
            MERGE (ai:AIInsight {id: $insight_id})
            SET ai += $properties
            MERGE (p)-[r:HAS_INSIGHT]->(ai)
            """
            
            for i, insight in enumerate(pattern_data["ai_insights"]):
                insight_id = f"{pattern_data['pattern_id']}_insight_{i}"
                await session.run(insights_query, {
                    "pattern_id": pattern_data["pattern_id"],
                    "insight_id": insight_id,
                    "properties": insight
                })
        
        # Store AI metrics if available
        if pattern_data.get("ai_metrics"):
            metrics_query = """
            MATCH (p:Pattern {id: $pattern_id})
            MERGE (m:AIMetric {id: $metric_id})
            SET m += $properties
            MERGE (p)-[r:HAS_METRIC]->(m)
            """
            
            for metric_type, value in pattern_data["ai_metrics"].items():
                metric_id = f"{pattern_data['pattern_id']}_{metric_type}"
                await session.run(metrics_query, {
                    "pattern_id": pattern_data["pattern_id"],
                    "metric_id": metric_id,
                    "properties": {
                        "type": metric_type,
                        "value": value,
                        "updated_at": pattern_data.get("updated_at")
                    }
                })
        
        # Store AI recommendations if available
        if pattern_data.get("ai_recommendations"):
            rec_query = """
            MATCH (p:Pattern {id: $pattern_id})
            MERGE (r:AIRecommendation {id: $rec_id})
            SET r += $properties
            MERGE (p)-[rel:HAS_RECOMMENDATION]->(r)
            """
            
            for i, rec in enumerate(pattern_data["ai_recommendations"]):
                rec_id = f"{pattern_data['pattern_id']}_rec_{i}"
                await session.run(rec_query, {
                    "pattern_id": pattern_data["pattern_id"],
                    "rec_id": rec_id,
                    "properties": {
                        "description": rec["description"],
                        "priority": rec.get("priority", "medium"),
                        "created_at": pattern_data.get("created_at")
                    }
                })
        
        log(f"Stored pattern node with AI enhancements: {pattern_data['pattern_id']}", level="debug")
    finally:
        await session.close()

@handle_async_errors(error_types=DatabaseError)
async def store_pattern_relationships(
    pattern_id: int,
    relationships: List[Dict[str, Any]]
) -> None:
    """Store pattern relationships with AI insights."""
    session = await connection_manager.get_session()
    try:
        relationship_query = """
        MATCH (p1:Pattern {id: $source_id})
        MATCH (p2:Pattern {id: $target_id})
        MERGE (p1)-[r:$rel_type]->(p2)
        SET r += $properties
        """
        
        for rel in relationships:
            properties = {
                "strength": rel["strength"],
                "ai_strength": rel.get("ai_strength"),
                "ai_insights": rel.get("ai_insights"),
                "created_at": rel.get("created_at"),
                "updated_at": rel.get("updated_at")
            }
            
            await session.run(relationship_query, {
                "source_id": pattern_id,
                "target_id": rel["target_id"],
                "rel_type": rel["relationship_type"],
                "properties": properties
            })
        
        log(f"Stored pattern relationships for pattern: {pattern_id}", level="debug")
    finally:
        await session.close()

@handle_async_errors(error_types=DatabaseError)
async def find_similar_patterns(
    repo_id: int,
    file_path: Optional[str] = None,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """Find similar patterns using graph algorithms."""
    session = await connection_manager.get_session()
    try:
        # Ensure pattern projection exists
        graph_sync = await get_graph_sync()
        await graph_sync.ensure_pattern_projection(repo_id)
        
        # Use node similarity algorithm
        query = """
        CALL gds.nodeSimilarity.stream('pattern-repo-' || $repo_id, {
            nodeProjection: ['Pattern'],
            relationshipProjection: {
                SIMILAR_TO: {
                    type: 'SIMILAR_TO',
                    orientation: 'UNDIRECTED',
                    properties: ['ai_strength', 'strength']
                }
            },
            similarityCutoff: 0.5,
            topK: $limit
        })
        YIELD node1, node2, similarity
        WITH gds.util.asNode(node1) AS pattern1,
             gds.util.asNode(node2) AS pattern2,
             similarity
        WHERE pattern1.repo_id = $repo_id
        RETURN pattern1.id as pattern_id,
               pattern1.type as pattern_type,
               pattern1.language as language,
               pattern1.confidence as confidence,
               pattern1.ai_confidence as ai_confidence,
               pattern2.id as similar_pattern_id,
               similarity
        ORDER BY similarity DESC
        LIMIT $limit
        """
        
        params = {"repo_id": repo_id, "limit": limit}
        if file_path:
            params["file_path"] = file_path
        
        result = await session.run(query, params)
        return await result.data()
    finally:
        await session.close()

@handle_async_errors(error_types=DatabaseError)
async def get_pattern_insights(
    pattern_id: int
) -> Dict[str, Any]:
    """Get all AI insights for a pattern."""
    session = await connection_manager.get_session()
    try:
        query = """
        MATCH (p:Pattern {id: $pattern_id})
        OPTIONAL MATCH (p)-[:HAS_INSIGHT]->(i:AIInsight)
        OPTIONAL MATCH (p)-[:HAS_METRIC]->(m:AIMetric)
        OPTIONAL MATCH (p)-[:HAS_RECOMMENDATION]->(r:AIRecommendation)
        RETURN p.id as pattern_id,
               p.type as pattern_type,
               p.confidence as confidence,
               p.ai_confidence as ai_confidence,
               collect(DISTINCT i) as insights,
               collect(DISTINCT m) as metrics,
               collect(DISTINCT r) as recommendations
        """
        
        result = await session.run(query, {"pattern_id": pattern_id})
        data = await result.data()
        return data[0] if data else {}
    finally:
        await session.close()

@handle_async_errors(error_types=DatabaseError)
async def analyze_pattern_trends(
    repo_id: int,
    pattern_type: Optional[str] = None,
    time_window: int = 30  # days
) -> List[Dict[str, Any]]:
    """Analyze pattern trends using AI metrics."""
    session = await connection_manager.get_session()
    try:
        query = """
        MATCH (p:Pattern)-[:HAS_METRIC]->(m:AIMetric)
        WHERE p.repo_id = $repo_id
        AND m.updated_at >= timestamp() - (1000 * 60 * 60 * 24 * $time_window)
        WITH p, m
        ORDER BY m.updated_at
        WITH p,
             collect(m) as metrics,
             avg(m.value) as avg_value,
             min(m.value) as min_value,
             max(m.value) as max_value
        RETURN p.id as pattern_id,
               p.type as pattern_type,
               p.ai_confidence as ai_confidence,
               avg_value,
               min_value,
               max_value,
               metrics
        ORDER BY avg_value DESC
        """
        
        params = {
            "repo_id": repo_id,
            "time_window": time_window
        }
        if pattern_type:
            params["pattern_type"] = pattern_type
            query = query.replace("WHERE p.repo_id = $repo_id", 
                                "WHERE p.repo_id = $repo_id AND p.type = $pattern_type")
        
        result = await session.run(query, params)
        return await result.data()
    finally:
        await session.close() 