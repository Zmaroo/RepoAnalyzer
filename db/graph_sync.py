"""[6.3] Graph synchronization and projection coordination.

Flow:
1. Projection Management:
   - Create/update graph projections
   - Cache projection states
   - Handle projection invalidation

2. Integration Points:
   - UnifiedIndexer [1.0]: Initial graph creation
   - FileWatcher [7.0]: Updates on file changes
   - SearchEngine [5.0]: Graph-enhanced search

3. Coordination:
   - Lock-based synchronization
   - Cache-based state tracking
   - Error handling and recovery
"""

import asyncio
from typing import Optional, Set, Dict, Any, List
from utils.logger import log
from db.connection import driver
from utils.cache import create_cache
from utils.error_handling import DatabaseError, Neo4jError
from utils.error_handling import handle_async_errors, AsyncErrorBoundary
from db.neo4j_ops import run_query

# Cache for graph states
graph_cache = create_cache("graph_state", ttl=300)

# Global projection cache
_projections = {}

class ProjectionError(DatabaseError):
    """Graph projection specific errors."""
    pass

class GraphSyncCoordinator:
    """[6.3.1] Coordinates graph operations and projections."""
    
    def __init__(self):
        self._lock = asyncio.Lock()
        self._active_projections: Set[str] = set()
        self._pending_updates: Dict[int, asyncio.Event] = {}
        self._update_task = None
        
    @handle_async_errors(error_types=(ProjectionError, Neo4jError))
    async def ensure_projection(self, repo_id: int) -> bool:
        """[6.3.2] Ensures graph projection exists and is up to date."""
        projection_name = f"code-repo-{repo_id}"
        
        async with self._lock:
            try:
                async with AsyncErrorBoundary("graph projection", error_types=(ProjectionError, Neo4jError)):
                    # Check if projection exists and is valid
                    if await self._is_projection_valid(projection_name):
                        return True
                    
                    # Create or update projection
                    await self._create_projection(repo_id, projection_name)
                    self._active_projections.add(projection_name)
                    
                    log("Graph projection ensured", level="debug", context={
                        "repo_id": repo_id,
                        "projection": projection_name
                    })
                    return True
                    
            except Exception as e:
                log("Failed to ensure graph projection", level="error", context={
                    "repo_id": repo_id,
                    "projection": projection_name,
                    "error": str(e)
                })
                raise ProjectionError(f"Failed to ensure projection for repo {repo_id}: {str(e)}")
    
    async def invalidate_projection(self, repo_id: int) -> None:
        """[6.3.3] Invalidates existing projection for repository."""
        projection_name = f"code-repo-{repo_id}"
        
        async with self._lock:
            try:
                if projection_name in self._active_projections:
                    await self._drop_projection(projection_name)
                    self._active_projections.remove(projection_name)
                await graph_cache.clear_pattern_async(f"graph:{repo_id}:*")
            except Exception as e:
                log(f"Error invalidating projection: {e}", level="error")
    
    async def _is_projection_valid(self, projection_name: str) -> bool:
        """Checks if projection exists and is valid."""
        try:
            result = await graph_cache.get_async(f"projection:{projection_name}")
            if result:
                return True
            
            query = """
            CALL gds.graph.exists($projection)
            YIELD exists
            """
            response = await driver.run(query, {"projection": projection_name})
            exists = response[0].get("exists", False)
            
            if exists:
                await graph_cache.set_async(f"projection:{projection_name}", True)
            
            return exists
            
        except Exception as e:
            log(f"Error checking projection validity: {e}", level="error")
            return False
    
    async def _create_projection(self, repo_id: int, projection_name: str) -> None:
        """Creates or updates graph projection."""
        projection_query = f"""
        CALL gds.graph.project.cypher(
            '{projection_name}',
            'MATCH (n:Code) WHERE n.repo_id = $repo_id RETURN id(n) AS id, labels(n) AS labels',
            'MATCH (n:Code)-[r]->(m:Code) WHERE n.repo_id = $repo_id AND m.repo_id = $repo_id 
             RETURN id(n) AS source, id(m) AS target, type(r) AS type',
            {{
                validateRelationships: false
            }}
        )
        """
        try:
            await driver.run(projection_query, {"repo_id": repo_id})
            await graph_cache.set_async(f"projection:{projection_name}", True)
            log(f"Created graph projection: {projection_name}", level="info")
        except Exception as e:
            log(f"Error creating graph projection: {e}", level="error")
            raise
    
    async def _drop_projection(self, projection_name: str) -> None:
        """Drops existing graph projection."""
        try:
            query = "CALL gds.graph.drop($projection)"
            await driver.run(query, {"projection": projection_name})
            await graph_cache.clear_pattern_async(f"projection:{projection_name}")
            log(f"Dropped graph projection: {projection_name}", level="info")
        except Exception as e:
            log(f"Error dropping projection: {e}", level="error")

    async def queue_projection_update(self, repo_id: int) -> None:
        """[6.3.4] Queue projection update with debouncing."""
        if repo_id not in self._pending_updates:
            self._pending_updates[repo_id] = asyncio.Event()
        
        if not self._update_task or self._update_task.done():
            self._update_task = asyncio.create_task(self._process_updates())
    
    async def _process_updates(self) -> None:
        """Process queued updates with debouncing."""
        await asyncio.sleep(1.0)  # Debounce window
        async with self._lock:
            for repo_id, event in self._pending_updates.items():
                await self.ensure_projection(repo_id)
                event.set()
            self._pending_updates.clear()

# Global instance
graph_sync = GraphSyncCoordinator()

async def graph_sync(nodes: List[Dict[str, Any]], relationships: List[Dict[str, Any]]) -> bool:
    """Synchronize graph with provided nodes and relationships."""
    async with driver.session() as session:
        # Implement using direct session operations instead of run_query
        # ... implementation ...
        return True  # Placeholder return, actual implementation needed

async def graph_sync_from_file(file_path: str) -> bool:
    # Implementation needed
    return False  # Placeholder return, actual implementation needed

async def graph_sync_from_search(query: str) -> bool:
    # Implementation needed
    return False  # Placeholder return, actual implementation needed

@handle_async_errors(error_types=(Neo4jError, TransactionError))
async def ensure_projection(repo_id: int) -> bool:
    """[6.3.1] Ensures graph projection exists and is valid."""
    async with AsyncErrorBoundary("graph projection"):
        # Check if projection exists
        graph_name = f"code-repo-{repo_id}"
        if graph_name in _projections and _projections[graph_name]["valid"]:
            log(f"Using cached graph projection: {graph_name}", level="debug")
            return True
        
        # Create graph projection
        try:
            await create_repository_projection(repo_id)
            _projections[graph_name] = {"valid": True}
            return True
        except Exception as e:
            raise Neo4jError(f"Failed to create graph projection: {e}")

@handle_async_errors(error_types=(Neo4jError, TransactionError))
async def invalidate_projection(repo_id: int) -> None:
    """[6.3.2] Invalidates an existing projection for re-creation."""
    graph_name = f"code-repo-{repo_id}"
    
    if graph_name in _projections:
        _projections[graph_name]["valid"] = False
        log(f"Invalidated graph projection: {graph_name}", level="debug")
    
    # Try to drop the existing projection
    try:
        await run_query(
            "CALL gds.graph.drop($graph_name, false)",
            {"graph_name": graph_name}
        )
        log(f"Dropped graph projection: {graph_name}", level="debug")
    except Exception as e:
        log(f"Error dropping graph projection (may not exist): {e}", level="debug")

@handle_async_errors(error_types=(Neo4jError, TransactionError))
async def create_repository_projection(repo_id: int) -> None:
    """[6.3.3] Creates a Neo4j in-memory graph projection for a repository."""
    graph_name = f"code-repo-{repo_id}"
    
    # Check if we already have nodes for this repo
    count_query = """
    MATCH (n:Code {repo_id: $repo_id})
    RETURN count(n) as count
    """
    result = await run_query(count_query, {"repo_id": repo_id})
    node_count = result[0]["count"] if result else 0
    
    if node_count == 0:
        log(f"No nodes found for repo {repo_id}, skipping projection", level="warn")
        return
    
    # Create the graph projection
    projection_query = """
    CALL gds.graph.project.cypher(
        $graph_name,
        'MATCH (n:Code {repo_id: $repo_id}) RETURN id(n) AS id, labels(n) AS labels, properties(n) AS properties',
        'MATCH (s:Code {repo_id: $repo_id})-[r:CALLS|IMPORTS|DEPENDS_ON|CONTAINS]->(t:Code {repo_id: $repo_id}) 
         RETURN id(s) AS source, id(t) AS target, type(r) AS type, properties(r) AS properties',
        {validateRelationships: false}
    )
    """
    
    await run_query(projection_query, {
        "graph_name": graph_name,
        "repo_id": repo_id
    })
    
    log(f"Created graph projection: {graph_name}", level="info")

@handle_async_errors(error_types=(Neo4jError, TransactionError))
async def create_pattern_projection(repo_id: int) -> None:
    """[6.3.5] Creates a Neo4j in-memory graph projection for patterns."""
    graph_name = f"pattern-repo-{repo_id}"
    
    # Check if we already have pattern nodes for this repo
    count_query = """
    MATCH (p:Pattern {repo_id: $repo_id})
    RETURN count(p) as count
    """
    result = await run_query(count_query, {"repo_id": repo_id})
    pattern_count = result[0]["count"] if result else 0
    
    if pattern_count == 0:
        log(f"No pattern nodes found for repo {repo_id}, skipping pattern projection", level="warn")
        return
    
    # Create the pattern graph projection
    projection_query = """
    CALL gds.graph.project.cypher(
        $graph_name,
        'MATCH (n) WHERE (n:Pattern AND n.repo_id = $repo_id) OR (n:Code AND n.repo_id = $repo_id) OR (n:Repository AND n.id = $repo_id) 
         RETURN id(n) AS id, labels(n) AS labels, properties(n) AS properties',
        'MATCH (n:Pattern {repo_id: $repo_id})-[r:EXTRACTED_FROM]->(m:Code {repo_id: $repo_id}) 
         RETURN id(n) AS source, id(m) AS target, type(r) AS type, properties(r) AS properties
         UNION
         MATCH (n:Repository {id: $repo_id})-[r:REFERENCE_PATTERN|APPLIED_PATTERN]->(m:Pattern) 
         RETURN id(n) AS source, id(m) AS target, type(r) AS type, properties(r) AS properties',
        {validateRelationships: false}
    )
    """
    
    await run_query(projection_query, {
        "graph_name": graph_name,
        "repo_id": repo_id
    })
    
    log(f"Created pattern graph projection: {graph_name}", level="info")

@handle_async_errors(error_types=(Neo4jError, TransactionError))
async def ensure_pattern_projection(repo_id: int) -> bool:
    """[6.3.6] Ensures pattern graph projection exists and is valid."""
    async with AsyncErrorBoundary("pattern graph projection"):
        # Check if projection exists
        graph_name = f"pattern-repo-{repo_id}"
        if graph_name in _projections and _projections[graph_name]["valid"]:
            log(f"Using cached pattern graph projection: {graph_name}", level="debug")
            return True
        
        # Create graph projection
        try:
            await create_pattern_projection(repo_id)
            _projections[graph_name] = {"valid": True}
            return True
        except Exception as e:
            raise Neo4jError(f"Failed to create pattern graph projection: {e}")

@handle_async_errors(error_types=(Neo4jError, TransactionError))
async def invalidate_pattern_projection(repo_id: int) -> None:
    """[6.3.7] Invalidates an existing pattern projection for re-creation."""
    graph_name = f"pattern-repo-{repo_id}"
    
    if graph_name in _projections:
        _projections[graph_name]["valid"] = False
        log(f"Invalidated pattern graph projection: {graph_name}", level="debug")
    
    # Try to drop the existing projection
    try:
        await run_query(
            "CALL gds.graph.drop($graph_name, false)",
            {"graph_name": graph_name}
        )
        log(f"Dropped pattern graph projection: {graph_name}", level="debug")
    except Exception as e:
        log(f"Error dropping pattern graph projection (may not exist): {e}", level="debug")

@handle_async_errors(error_types=(Neo4jError, TransactionError))
async def create_repository_with_reference_projection(active_repo_id: int, reference_repo_id: int) -> None:
    """[6.3.8] Creates a combined graph projection of active and reference repositories."""
    graph_name = f"active-reference-{active_repo_id}-{reference_repo_id}"
    
    # Create the combined graph projection
    projection_query = """
    CALL gds.graph.project.cypher(
        $graph_name,
        'MATCH (n) WHERE (n:Code AND (n.repo_id = $active_repo_id OR n.repo_id = $reference_repo_id)) OR 
                         (n:Pattern AND (n.repo_id = $active_repo_id OR n.repo_id = $reference_repo_id))
         RETURN id(n) AS id, labels(n) AS labels, properties(n) AS properties',
        'MATCH (s)-[r]->(t) 
         WHERE (s:Code OR s:Pattern) AND (t:Code OR t:Pattern) AND 
               (s.repo_id = $active_repo_id OR s.repo_id = $reference_repo_id) AND
               (t.repo_id = $active_repo_id OR t.repo_id = $reference_repo_id)
         RETURN id(s) AS source, id(t) AS target, type(r) AS type, properties(r) AS properties',
        {validateRelationships: false}
    )
    """
    
    await run_query(projection_query, {
        "graph_name": graph_name,
        "active_repo_id": active_repo_id,
        "reference_repo_id": reference_repo_id
    })
    
    log(f"Created combined active-reference graph projection: {graph_name}", level="info")

@handle_async_errors(error_types=(Neo4jError, TransactionError))
async def compare_repository_structures(active_repo_id: int, reference_repo_id: int) -> dict:
    """[6.3.9] Compares the structure of an active repository with a reference repository."""
    # Create combined projection if needed
    graph_name = f"active-reference-{active_repo_id}-{reference_repo_id}"
    
    try:
        await create_repository_with_reference_projection(active_repo_id, reference_repo_id)
    except Exception as e:
        log(f"Error creating combined projection: {e}", level="error")
        return {"error": str(e)}
    
    # Run similarity algorithm
    similarity_query = """
    CALL gds.nodeSimilarity.stream($graph_name, {
        topK: 10,
        similarityCutoff: 0.5
    })
    YIELD node1, node2, similarity
    WITH gds.util.asNode(node1) AS n1, gds.util.asNode(node2) AS n2, similarity
    WHERE n1.repo_id <> n2.repo_id  // Only compare nodes from different repos
    RETURN n1.file_path AS active_file, 
           n2.file_path AS reference_file, 
           n1.language AS language,
           similarity
    ORDER BY similarity DESC
    LIMIT 20
    """
    
    similarity_results = await run_query(similarity_query, {"graph_name": graph_name})
    
    # Get structure statistics for each repo
    active_stats_query = """
    MATCH (c:Code {repo_id: $repo_id})
    RETURN c.language AS language, count(*) AS file_count
    ORDER BY file_count DESC
    """
    
    active_stats = await run_query(active_stats_query, {"repo_id": active_repo_id})
    reference_stats = await run_query(active_stats_query, {"repo_id": reference_repo_id})
    
    return {
        "similarities": similarity_results,
        "active_repo_stats": active_stats,
        "reference_repo_stats": reference_stats,
        "similarity_count": len(similarity_results)
    }

# Global export
graph_sync = AsyncErrorBoundary("graph_sync", locals()) 