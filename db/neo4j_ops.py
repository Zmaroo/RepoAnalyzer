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
    ErrorBoundary,
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

# Create a function to get the graph_sync instance to avoid circular imports
async def get_graph_sync():
    """Get the graph_sync instance."""
    from db.graph_sync import get_graph_sync as _get_graph_sync
    return await _get_graph_sync()

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

class Neo4jTools:
    """Neo4j database operations coordinator."""
    
    def __init__(self):
        self._pending_tasks: Set[asyncio.Future] = set()
        with ErrorBoundary(
            error_types=DatabaseError,
            operation_name="Neo4j tools initialization",
            severity=ErrorSeverity.CRITICAL
        ):
            # Initialize connection
            future = submit_async_task(connection_manager.initialize())
            self._pending_tasks.add(future)
            try:
                asyncio.get_event_loop().run_until_complete(future)
            finally:
                self._pending_tasks.remove(future)

    @handle_async_errors(error_types=DatabaseError)
    async def store_code_node(self, code_data: dict) -> None:
        """Store code node with transaction coordination."""
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

    @handle_async_errors(error_types=DatabaseError)
    async def close(self):
        """Clean up any pending tasks."""
        if self._pending_tasks:
            await asyncio.gather(*[asyncio.wrap_future(f) for f in self._pending_tasks], return_exceptions=True)
            self._pending_tasks.clear()

    @handle_async_errors(error_types=DatabaseError)
    async def store_node_with_features(
        self,
        repo_id: int,
        file_path: str,
        ast: dict,
        features: ExtractedFeatures
    ) -> None:
        """[6.2.3] Store node with all its features and relationships."""
        # Create base node
        query = """
        MERGE (n:Content {repo_id: $repo_id, file_path: $file_path})
        SET n += $properties
        """
        
        # Properties from all feature categories
        properties = {
            "repo_id": repo_id,
            "file_path": file_path,
            "ast": ast,
            "syntax_features": features.get_category(FeatureCategory.SYNTAX),
            "semantic_features": features.get_category(FeatureCategory.SEMANTICS),
            "doc_features": features.get_category(FeatureCategory.DOCUMENTATION),
            "structural_features": features.get_category(FeatureCategory.STRUCTURE)
        }
        
        await run_query(query, properties)
        await self.create_feature_relationships(repo_id, file_path, features)

    @handle_async_errors(error_types=DatabaseError)
    async def store_pattern_node(self, pattern_data: dict) -> None:
        """[6.2.6] Store code pattern node for reference repository learning."""
        async with AsyncErrorBoundary(
            "Neo4j pattern node storage",
            error_types=(Neo4jError, TransactionError),
            severity=ErrorSeverity.ERROR
        ):
            # Create pattern node
            query = """
            MERGE (p:Pattern {
                repo_id: $repo_id, 
                pattern_id: $pattern_id,
                pattern_type: $pattern_type
            })
            SET p += $properties,
                p.updated_at = timestamp()
            """
            
            await run_query(query, {
                "repo_id": pattern_data["repo_id"],
                "pattern_id": pattern_data["pattern_id"],
                "pattern_type": pattern_data["pattern_type"],
                "properties": pattern_data
            })
            
            # If this is a code pattern, create relationship to relevant code
            if pattern_data.get("file_path") and pattern_data.get("pattern_type") == "code_structure":
                rel_query = """
                MATCH (p:Pattern {repo_id: $repo_id, pattern_id: $pattern_id})
                MATCH (c:Code {repo_id: $repo_id, file_path: $file_path})
                MERGE (p)-[r:EXTRACTED_FROM]->(c)
                """
                
                await run_query(rel_query, {
                    "repo_id": pattern_data["repo_id"],
                    "pattern_id": pattern_data["pattern_id"],
                    "file_path": pattern_data["file_path"]
                })
            
            log("Stored pattern node", level="debug", context={
                "operation": "store_pattern_node",
                "repo_id": pattern_data["repo_id"],
                "pattern_id": pattern_data["pattern_id"],
                "pattern_type": pattern_data["pattern_type"]
            })

    @handle_async_errors(error_types=DatabaseError)
    async def link_patterns_to_repository(self, repo_id: int, pattern_ids: List[int], is_reference: bool = True) -> None:
        """[6.2.7] Link patterns to a repository with appropriate relationship type."""
        rel_type = "REFERENCE_PATTERN" if is_reference else "APPLIED_PATTERN"
        
        query = """
        MATCH (r:Repository {id: $repo_id})
        MATCH (p:Pattern {pattern_id: $pattern_id})
        MERGE (r)-[rel:%s]->(p)
        """ % rel_type
        
        for pattern_id in pattern_ids:
            await run_query(query, {
                "repo_id": repo_id,
                "pattern_id": pattern_id
            })

    @handle_async_errors(error_types=DatabaseError)
    async def find_similar_patterns(self, repo_id: int, file_path: str, limit: int = 5) -> List[Dict[str, Any]]:
        """[6.2.8] Find patterns similar to a given file."""
        # Get language of the file
        lang_query = """
        MATCH (c:Code {repo_id: $repo_id, file_path: $file_path})
        RETURN c.language as language
        """
        
        lang_result = await run_query(lang_query, {
            "repo_id": repo_id,
            "file_path": file_path
        })
        
        if not lang_result:
            return []
        
        language = lang_result[0].get("language")
        
        # Find patterns of the same language
        patterns_query = """
        MATCH (p:Pattern)
        WHERE p.language = $language AND p.pattern_type = 'code_structure'
        RETURN p.pattern_id as pattern_id, p.repo_id as repo_id, 
               p.language as language, p.file_path as file_path,
               p.elements as elements, p.sample as sample
        LIMIT $limit
        """
        
        return await run_query(patterns_query, {
            "language": language,
            "limit": limit
        })

@handle_async_errors(error_types=(DatabaseError, Neo4jError))
async def create_schema_indexes_and_constraints():
    """Create Neo4j schema indexes and constraints."""
    with ErrorBoundary(
        operation_name="creating_schema_indexes",
        error_types=(Neo4jError, DatabaseError),
        reraise=False,
        severity=ErrorSeverity.CRITICAL
    ) as boundary:
        session = await connection_manager.get_session()
        try:
            # Create indexes for different node types
            await session.run("CREATE INDEX IF NOT EXISTS FOR (c:Code) ON (c.repo_id, c.file_path)")
            await session.run("CREATE INDEX IF NOT EXISTS FOR (d:Documentation) ON (d.repo_id, d.path)")
            await session.run("CREATE INDEX IF NOT EXISTS FOR (r:Repository) ON (r.id)")
            await session.run("CREATE INDEX IF NOT EXISTS FOR (l:Language) ON (l.name)")
            await session.run("CREATE INDEX IF NOT EXISTS FOR (p:Pattern) ON (p.id)")
            await session.run("CREATE INDEX IF NOT EXISTS FOR (f:Feature) ON (f.name)")
            
            # Create constraints for uniqueness
            await session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (r:Repository) REQUIRE r.id IS UNIQUE")
            await session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (c:Code) REQUIRE (c.repo_id, c.file_path) IS UNIQUE")
            await session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (p:Pattern) REQUIRE p.id IS UNIQUE")
            
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
        self._pending_tasks: Set[asyncio.Future] = set()
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
        future = submit_async_task(run_query(query, {"graph_name": graph_name}))
        self._pending_tasks.add(future)
        try:
            results = await asyncio.wrap_future(future)
            return results
        finally:
            self._pending_tasks.remove(future)
    
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
        future = submit_async_task(run_query(query, {"graph_name": graph_name}))
        self._pending_tasks.add(future)
        try:
            results = await asyncio.wrap_future(future)
            return results
        finally:
            self._pending_tasks.remove(future)
    
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
        future = submit_async_task(run_query(query, {}))
        self._pending_tasks.add(future)
        try:
            results = await asyncio.wrap_future(future)
            return results
        finally:
            self._pending_tasks.remove(future)
    
    @handle_errors(error_types=(Exception,))
    async def close(self):
        """Clean up any pending tasks."""
        if self._pending_tasks:
            await asyncio.gather(*[asyncio.wrap_future(f) for f in self._pending_tasks], return_exceptions=True)
            self._pending_tasks.clear()

# Create global instance
projections = Neo4jProjections() 