"""[6.3] Graph synchronization and projection coordination.

This module provides functionality for managing Neo4j graph projections, 
which are in-memory subgraphs optimized for graph algorithms. 

Asynchronous Architecture:
-------------------------
All operations in this module are asynchronous and should be awaited.
The module uses asyncio for coordination and locking to ensure thread safety.

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

Usage Examples:
-------------
# Creating a projection for a repository
await graph_sync.ensure_projection(repo_id)

# Invalidating a projection after major changes
await graph_sync.invalidate_projection(repo_id)

# Queueing an update with debouncing (useful for file changes)
await graph_sync.queue_projection_update(repo_id)

# Auto-reinvoking projection for all repositories
await auto_reinvoke_projection_once()

# Auto-reinvoking projection for a specific repository
await auto_reinvoke_projection_once(repo_id)
"""

import asyncio
from typing import Optional, Set, Dict, Any, List
from utils.logger import log
from db.connection import driver
from utils.cache import create_cache
from utils.error_handling import DatabaseError, Neo4jError, TransactionError, handle_async_errors, ErrorBoundary, AsyncErrorBoundary
from db.neo4j_ops import run_query
from db.retry_utils import with_retry

# Cache for graph states
graph_cache = create_cache("graph_state", ttl=300)

# Global projection cache
_projections = {}

class ProjectionError(DatabaseError):
    """Graph projection specific errors."""
    pass

class GraphSyncCoordinator:
    """[6.3.1] Coordinates graph operations and projections.
    
    This class is responsible for managing Neo4j graph projections:
    - Creating and updating projections 
    - Tracking projection state in cache
    - Handling concurrent updates with locking
    - Providing debounced updates for file changes
    
    All methods are asynchronous and should be awaited.
    """
    
    def __init__(self):
        self._lock = asyncio.Lock()
        self._active_projections: Set[str] = set()
        self._pending_updates: Dict[int, asyncio.Event] = {}
        self._update_task = None
        
    @handle_async_errors(error_types=(Neo4jError, ProjectionError, Exception))
    async def ensure_projection(self, repo_id: int) -> bool:
        """[6.3.2] Ensures graph projection exists and is up to date.
        
        This method checks if a projection exists for the specified repository,
        creates it if missing, and validates its state. It uses a cache to 
        avoid unnecessary database operations.
        
        Args:
            repo_id: Repository ID to ensure projection for
            
        Returns:
            bool: True if projection exists or was successfully created
            
        Raises:
            ProjectionError: If projection creation fails
            
        Example:
            ```python
            # Ensure projection exists for repository 123
            success = await graph_sync.ensure_projection(123)
            if success:
                # Projection is ready for use
                pass
            ```
        """
        projection_name = f"code-repo-{repo_id}"
        
        async with self._lock:
            async with AsyncErrorBoundary(operation_name=f"Ensuring graph projection {projection_name}", error_types=(Neo4jError, Exception)) as error_boundary:
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
            
            if error_boundary.error:
                log(f"Error in graph projection: {str(error_boundary.error)}", level="error")
                raise ProjectionError(f"Failed to ensure projection for repo {repo_id}: {str(error_boundary.error)}")
    
    @handle_async_errors(error_types=(Neo4jError, ProjectionError, DatabaseError))
    async def invalidate_projection(self, repo_id: int) -> None:
        """[6.3.3] Invalidates and recreates a graph projection.
        
        This method is used when the underlying data has changed significantly
        and the projection needs to be rebuilt from scratch.
        
        Args:
            repo_id: Repository ID to invalidate projection for
            
        Raises:
            ProjectionError: If projection invalidation fails
            
        Example:
            ```python
            # Invalidate projection for repository 123
            await graph_sync.invalidate_projection(123)
            ```
        """
        projection_name = f"code-repo-{repo_id}"
        
        async with self._lock:
            async with AsyncErrorBoundary(operation_name=f"Invalidating graph projection {projection_name}", error_types=(Neo4jError, DatabaseError, Exception)) as error_boundary:
                # Drop existing projection if it exists
                await self._drop_projection(projection_name)
                
                # Create new projection
                await self._create_projection(repo_id, projection_name)
                self._active_projections.add(projection_name)
            
            if error_boundary.error:
                log(f"Error invalidating projection: {error_boundary.error}", level="error")
    
    @handle_async_errors(error_types=(Neo4jError, DatabaseError))
    async def _is_projection_valid(self, projection_name: str) -> bool:
        """Check if a graph projection exists and is valid."""
        async with AsyncErrorBoundary(operation_name=f"Checking if graph projection {projection_name} exists", error_types=(Neo4jError, DatabaseError, Exception)) as error_boundary:
            # Check if projection exists in Neo4j
            query = """
            CALL gds.graph.exists($projection_name) 
            YIELD exists
            RETURN exists
            """
            
            result = await run_query(query, {"projection_name": projection_name})
            
            if not result or not result[0]:
                return False
                
            return result[0]["exists"]
    
    @handle_async_errors(error_types=(Neo4jError, DatabaseError))
    async def _create_projection(self, repo_id: int, projection_name: str) -> None:
        """Create a new graph projection for a repository."""
        async with AsyncErrorBoundary(operation_name=f"Creating graph projection {projection_name}", error_types=(Neo4jError, DatabaseError)):
            # First drop any existing projection with this name
            await self._drop_projection(projection_name)
            
            # Create the projection
            query = """
            CALL gds.graph.project(
                $projection_name,
                ['File', 'Function', 'Class', 'Module'],
                {
                    IMPORTS: {type: 'IMPORTS', orientation: 'NATURAL'},
                    DEFINES: {type: 'DEFINES', orientation: 'NATURAL'},
                    CALLS: {type: 'CALLS', orientation: 'NATURAL'},
                    CONTAINS: {type: 'CONTAINS', orientation: 'NATURAL'}
                },
                {
                    nodeFilter: 'repository_id = $repo_id'
                }
            )
            """
            
            await run_query(query, {
                "projection_name": projection_name,
                "repo_id": repo_id
            })
    
    @handle_async_errors(error_types=(Neo4jError, DatabaseError))
    async def _drop_projection(self, projection_name: str) -> None:
        """Drops existing graph projection."""
        async with AsyncErrorBoundary(operation_name=f"Dropping graph projection {projection_name}", error_types=(Neo4jError, DatabaseError, Exception)) as error_boundary:
            query = "CALL gds.graph.drop($projection)"
            await run_query(query, {"projection": projection_name})
            await graph_cache.clear_pattern_async(f"projection:{projection_name}")
            log(f"Dropped graph projection: {projection_name}", level="info")
        
        if error_boundary.error:
            log(f"Error dropping projection: {error_boundary.error}", level="error")

@handle_async_errors(error_types=(Exception,))
    async def queue_projection_update(self, repo_id: int) -> None:
        """[6.3.4] Queue projection update with debouncing.
        
        This method is useful for handling frequent updates (e.g., file changes)
        by using a debounce pattern to avoid excessive projection recreation.
        
        Args:
            repo_id: Repository ID to queue update for
            
        Example:
            ```python
            # When files have changed
            for file_change in file_changes:
                await process_file(file_change)
                # Queue update instead of immediate projection recreation
                await graph_sync.queue_projection_update(repo_id)
            ```
        """
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

# Create a singleton instance of GraphSyncCoordinator
graph_sync = GraphSyncCoordinator()

@handle_async_errors(error_types=(Neo4jError, TransactionError, DatabaseError))
async def sync_graph(nodes: List[Dict[str, Any]], relationships: List[Dict[str, Any]]) -> bool:
    """[6.3.7] Synchronize graph with provided nodes and relationships.
    
    This function is used to update the graph with new nodes and relationships.
    It's a lower-level function compared to the GraphSyncCoordinator methods.
    
    Args:
        nodes: List of node dictionaries with properties
        relationships: List of relationship dictionaries with properties
        
    Returns:
        bool: True if synchronization was successful
        
    Example:
        ```python
        nodes = [
            {"id": "n1", "labels": ["Person"], "properties": {"name": "Alice"}},
            {"id": "n2", "labels": ["Person"], "properties": {"name": "Bob"}}
        ]
        relationships = [
            {"id": "r1", "type": "KNOWS", "start_node": "n1", "end_node": "n2", 
             "properties": {"since": 2020}}
        ]
        success = await sync_graph(nodes, relationships)
        ```
    """
    session = None
    tx = None
    
    async with AsyncErrorBoundary(operation_name="Getting graph sync session", error_types=(Neo4jError, TransactionError)) as session_boundary:
        # Get a driver session and run transaction manually
        session = driver.session()
        tx = await session.begin_transaction()
        
        async with AsyncErrorBoundary(operation_name="Starting graph sync transaction", error_types=(Neo4jError, TransactionError)) as tx_boundary:
            # Create nodes
            for node in nodes:
                labels = ":".join(node.get("labels", []))
                properties = node.get("properties", {})
                node_id = node.get("id")
                
                # Create node with properties
                query = f"CREATE (n:{labels} {{id: $id}}) SET n += $properties RETURN n"
                await tx.run(query, {"id": node_id, "properties": properties})
            
            # Create relationships
            for rel in relationships:
                rel_type = rel.get("type")
                start_node = rel.get("start_node")
                end_node = rel.get("end_node")
                properties = rel.get("properties", {})
                
                # Create relationship with properties
                query = """
                MATCH (a), (b) 
                WHERE a.id = $start_id AND b.id = $end_id
                CREATE (a)-[r:`{rel_type}` {{id: $id}}]->(b)
                SET r += $properties
                RETURN r
                """.replace("{rel_type}", rel_type)
                
                await tx.run(query, {
                    "start_id": start_node,
                    "end_id": end_node,
                    "id": rel.get("id"),
                    "properties": properties
                })
            
            # Commit the transaction
            await tx.commit()
            
            if session:
                await session.close()
            return True
    
    # Error handling
    if tx_boundary.error:
        log(f"Error in graph synchronization: {str(tx_boundary.error)}", level="error")
        if tx:
            await tx.rollback()
    
    if session_boundary.error:
        log(f"Error in graph synchronization session: {str(session_boundary.error)}", level="error")
    
    if session:
        await session.close()
    
    return False

@handle_async_errors(error_types=(Exception,))
async def graph_sync_from_file(file_path: str) -> bool:
    # Implementation needed
    return False  # Placeholder return, actual implementation needed
@handle_async_errors(error_types=(Exception,))

async def graph_sync_from_search(query: str) -> bool:
    # Implementation needed
    return False  # Placeholder return, actual implementation needed

@handle_async_errors(error_types=(Neo4jError, TransactionError))
async def ensure_projection(repo_id: int) -> bool:
    """[6.3.1] Ensures graph projection exists and is valid."""
    async with AsyncErrorBoundary(operation_name="graph projection"):
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
        except Neo4jError as e:
            log(f"Neo4j error creating graph projection: {e}", level="error")
            raise Neo4jError(f"Failed to create graph projection: {e}")
        except TransactionError as e:
            log(f"Transaction error creating graph projection: {e}", level="error")
            raise Neo4jError(f"Failed to create graph projection due to transaction error: {e}")
        except Exception as e:
            log(f"Unexpected error creating graph projection: {e}", level="error")
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
        await with_retry(run_query)(
            "CALL gds.graph.drop($graph_name, false)",
            {"graph_name": graph_name}
        )
        log(f"Dropped graph projection: {graph_name}", level="debug")
    except Neo4jError as e:
        # This is likely because the projection doesn't exist, which is OK
        log(f"Neo4j error dropping graph projection (may not exist): {e}", level="debug")
    except TransactionError as e:
        log(f"Transaction error dropping graph projection: {e}", level="warning")
    except Exception as e:
        log(f"Unexpected error dropping graph projection: {e}", level="error")
        raise Neo4jError(f"Failed to drop graph projection: {e}")

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
    async with AsyncErrorBoundary(operation_name="pattern graph projection"):
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
        except Neo4jError as e:
            log(f"Neo4j error creating pattern graph projection: {e}", level="error")
            raise Neo4jError(f"Failed to create pattern graph projection: {e}")
        except TransactionError as e:
            log(f"Transaction error creating pattern graph projection: {e}", level="error")
            raise Neo4jError(f"Failed to create pattern graph projection due to transaction error: {e}")
        except Exception as e:
            log(f"Unexpected error creating pattern graph projection: {e}", level="error")
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
        await with_retry(run_query)(
            "CALL gds.graph.drop($graph_name, false)",
            {"graph_name": graph_name}
        )
        log(f"Dropped pattern graph projection: {graph_name}", level="debug")
    except Neo4jError as e:
        # This is likely because the projection doesn't exist, which is OK
        log(f"Neo4j error dropping pattern graph projection (may not exist): {e}", level="debug")
    except TransactionError as e:
        log(f"Transaction error dropping pattern graph projection: {e}", level="warning")
    except Exception as e:
        log(f"Unexpected error dropping pattern graph projection: {e}", level="error")
        raise Neo4jError(f"Failed to drop pattern graph projection: {e}")

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
    except Neo4jError as e:
        log(f"Neo4j error creating combined projection: {e}", level="error")
        return {"error": f"Database error: {str(e)}"}
    except TransactionError as e:
        log(f"Transaction error creating combined projection: {e}", level="error")
        return {"error": f"Transaction error: {str(e)}"}
    except Exception as e:
        log(f"Unexpected error creating combined projection: {e}", level="error")
        return {"error": f"Unexpected error: {str(e)}"}
    
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

# Export with boundary protection
# Wrap the existing global instance with error boundary
# graph_sync = AsyncErrorBoundary(operation_name="graph_sync_coordinator", graph_sync) 