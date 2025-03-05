"""[6.3] Graph synchronization and projection coordination.

This module provides centralized management of Neo4j graph projections:
1. Projection creation and updates
2. Cache state management
3. Graph algorithm coordination
4. Asynchronous task management

All database operations use the centralized connection manager.

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
coordinator = await get_graph_sync()
await coordinator.ensure_projection(repo_id)

# Invalidating a projection after major changes
coordinator = await get_graph_sync()
await coordinator.invalidate_projection(repo_id)

# Queueing an update with debouncing (useful for file changes)
coordinator = await get_graph_sync()
await coordinator.queue_projection_update(repo_id)

# Auto-reinvoking projection for all repositories
await auto_reinvoke_projection_once()

# Auto-reinvoking projection for a specific repository
await auto_reinvoke_projection_once(repo_id)

# Comparing repository structures
coordinator = await get_graph_sync()
await coordinator.compare_repository_structures(active_repo_id, reference_repo_id)

# Synchronizing graph nodes and relationships
coordinator = await get_graph_sync()
await coordinator.sync_graph(nodes, relationships)

# Creating pattern projections
coordinator = await get_graph_sync()
await coordinator.ensure_pattern_projection(repo_id)
"""

import asyncio
from typing import Optional, Set, Dict, Any, List
from utils.logger import log
from db.connection import connection_manager
from utils.cache import UnifiedCache, cache_coordinator
from utils.error_handling import (
    DatabaseError, 
    Neo4jError, 
    TransactionError, 
    handle_async_errors, 
    AsyncErrorBoundary,
    ProcessingError,
    ErrorSeverity
)
from utils.async_runner import submit_async_task
from utils.shutdown import register_shutdown_handler
from analytics.pattern_statistics import pattern_profiler
from utils.health_monitor import global_health_monitor

# Create cache instance for graph state
graph_cache = UnifiedCache("graph_state", ttl=300)

class ProjectionError(DatabaseError):
    """Graph projection specific errors."""
    pass

class GraphSyncCoordinator:
    """Coordinates graph operations and projections."""
    
    def __init__(self):
        """Private constructor - use create() instead."""
        self._initialized = False
        self._pending_tasks: Set[asyncio.Task] = set()
        self._lock = asyncio.Lock()
        self._update_task = None
        self._active_projections: Set[str] = set()
        self._projections: Dict[str, Dict[str, Any]] = {}
        self._retry_manager = None
    
    async def ensure_initialized(self):
        """Ensure the instance is properly initialized before use."""
        if not self._initialized:
            raise DatabaseError("GraphSyncCoordinator not initialized. Use create() to initialize.")
        if not self._retry_manager:
            raise DatabaseError("Retry manager not initialized")
        return True
    
    @classmethod
    async def create(cls) -> 'GraphSyncCoordinator':
        """Async factory method to create and initialize a GraphSyncCoordinator instance."""
        instance = cls()
        try:
            async with AsyncErrorBoundary(
                operation_name="graph sync coordinator initialization",
                error_types=DatabaseError,
                severity=ErrorSeverity.CRITICAL
            ):
                # Initialize retry manager
                from db.retry_utils import DatabaseRetryManager, RetryConfig
                instance._retry_manager = await DatabaseRetryManager.create(
                    RetryConfig(max_retries=3, base_delay=1.0, max_delay=10.0)
                )
                
                # Register shutdown handler
                register_shutdown_handler(instance.cleanup)
                
                # Initialize health monitoring
                from utils.health_monitor import global_health_monitor
                global_health_monitor.register_component("graph_sync_coordinator")
                
                instance._initialized = True
                await log("Graph sync coordinator initialized", level="info")
                return instance
        except Exception as e:
            await log(f"Error initializing graph sync coordinator: {e}", level="error")
            # Cleanup on initialization failure
            await instance.cleanup()
            raise DatabaseError(f"Failed to initialize graph sync coordinator: {e}")
    
    async def cleanup(self):
        """Clean up all resources."""
        try:
            if not self._initialized:
                return
                
            # Stop update task
            if self._update_task and not self._update_task.done():
                self._update_task.cancel()
                try:
                    await self._update_task
                except asyncio.CancelledError:
                    pass
            
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
            
            # Clear all projections
            for projection_name in self._active_projections:
                try:
                    await self._drop_projection(projection_name)
                except Exception as e:
                    await log(f"Error dropping projection {projection_name}: {e}", level="error")
            
            self._active_projections.clear()
            self._projections.clear()
            
            # Unregister from health monitoring
            from utils.health_monitor import global_health_monitor
            global_health_monitor.unregister_component("graph_sync_coordinator")
            
            self._initialized = False
            await log("Graph sync coordinator cleaned up", level="info")
        except Exception as e:
            await log(f"Error cleaning up graph sync coordinator: {e}", level="error")
            raise DatabaseError(f"Failed to cleanup graph sync coordinator: {e}")
    
    @handle_async_errors(error_types=ProcessingError)
    async def ensure_projection(self, repo_id: int) -> bool:
        """Ensure graph projection exists for repository."""
        async with AsyncErrorBoundary(
            operation_name="ensuring graph projection",
            error_types=ProcessingError,
            severity=ErrorSeverity.ERROR
        ):
            if not self._initialized:
                await self.ensure_initialized()
            
            projection_name = f"code-repo-{repo_id}"
            
            async with self._lock:
                async with AsyncErrorBoundary(
                    operation_name="ensure_graph_projection", 
                    error_types=(Neo4jError,), 
                    reraise=True, 
                    severity=ErrorSeverity.CRITICAL
                ) as error_boundary:
                    # Check if projection exists and is valid
                    is_valid = await self._is_projection_valid(projection_name)
                    if is_valid:
                        return True
                    
                    # Create or update projection
                    await self._create_projection(repo_id, projection_name)
                    self._active_projections.add(projection_name)
                    self._projections[projection_name] = {"valid": True}
                    
                    log("Graph projection ensured", level="debug", context={
                        "repo_id": repo_id,
                        "projection": projection_name
                    })
                    return True
                
                if error_boundary.error:
                    log(f"Error in graph projection: {str(error_boundary.error)}", level="error")
                    raise ProjectionError(f"Failed to ensure projection for repo {repo_id}: {str(error_boundary.error)}")
    
    @handle_async_errors(error_types=ProcessingError)
    async def ensure_pattern_projection(self, repo_id: int) -> bool:
        """Ensure pattern graph projection exists."""
        async with AsyncErrorBoundary(
            operation_name="ensuring pattern projection",
            error_types=ProcessingError,
            severity=ErrorSeverity.ERROR
        ):
            graph_name = f"pattern-repo-{repo_id}"
            
            async with self._lock:
                async with AsyncErrorBoundary(
                    operation_name="pattern_graph_projection", 
                    error_types=(Neo4jError,), 
                    reraise=True, 
                    severity=ErrorSeverity.CRITICAL
                ) as error_boundary:
                    # Check if projection exists and is valid
                    if graph_name in self._projections and self._projections[graph_name]["valid"]:
                        log(f"Using cached pattern graph projection: {graph_name}", level="debug")
                        return True
                    
                    # Create pattern projection
                    await self._create_pattern_projection(repo_id, graph_name)
                    self._projections[graph_name] = {"valid": True}
                    return True
                
                if error_boundary.error:
                    log(f"Error in pattern graph projection: {str(error_boundary.error)}", level="error")
                    raise ProjectionError(f"Failed to ensure pattern projection for repo {repo_id}: {str(error_boundary.error)}")
    
    @handle_async_errors(error_types=ProcessingError)
    async def invalidate_projection(self, repo_id: int) -> None:
        """Invalidate graph projection for repository."""
        async with AsyncErrorBoundary(
            operation_name="invalidating graph projection",
            error_types=ProcessingError,
            severity=ErrorSeverity.ERROR
        ):
            projection_name = f"code-repo-{repo_id}"
            
            async with self._lock:
                async with AsyncErrorBoundary(
                    operation_name="invalidating_projection",
                    error_types=[Neo4jError, DatabaseError, Exception], 
                    severity=ErrorSeverity.WARNING
                ) as error_boundary:
                    if projection_name in self._active_projections:
                        await self._drop_projection(projection_name)
                        self._active_projections.remove(projection_name)
                        if projection_name in self._projections:
                            self._projections[projection_name]["valid"] = False
                    
                    await graph_cache.clear_pattern_async(f"graph:{repo_id}:*")
                
                if error_boundary.error:
                    log(f"Error invalidating projection: {error_boundary.error}", level="error")
    
    @handle_async_errors(error_types=ProcessingError)
    async def invalidate_pattern_projection(self, repo_id: int) -> None:
        """Invalidate pattern graph projection."""
        async with AsyncErrorBoundary(
            operation_name="invalidating pattern projection",
            error_types=ProcessingError,
            severity=ErrorSeverity.ERROR
        ):
            graph_name = f"pattern-repo-{repo_id}"
            
            async with self._lock:
                async with AsyncErrorBoundary(
                    operation_name="invalidating_pattern_projection",
                    error_types=[Neo4jError, DatabaseError, Exception], 
                    severity=ErrorSeverity.WARNING
                ) as error_boundary:
                    if graph_name in self._projections:
                        self._projections[graph_name]["valid"] = False
                        await self._drop_projection(graph_name)
                        log(f"Invalidated pattern graph projection: {graph_name}", level="debug")
                    
                    await graph_cache.clear_pattern_async(f"pattern:{repo_id}:*")
                
                if error_boundary.error:
                    log(f"Error invalidating pattern projection: {error_boundary.error}", level="error")
    
    @handle_async_errors(error_types=[Neo4jError, DatabaseError])
    async def _is_projection_valid(self, projection_name: str) -> bool:
        """Checks if projection exists and is valid."""
        async with AsyncErrorBoundary(
            operation_name="checking_projection_validity",
            error_types=[Neo4jError, DatabaseError, Exception], 
            severity=ErrorSeverity.ERROR
        ) as error_boundary:
            # Check in-memory cache first
            if projection_name in self._projections and self._projections[projection_name]["valid"]:
                return True
            
            # Check distributed cache next
            result = await graph_cache.get_async(f"projection:{projection_name}")
            if result:
                return True
            
            # Finally check database
            session = await connection_manager.get_session()
            try:
                query = "CALL gds.graph.exists($projection) YIELD exists"
                future = submit_async_task(session.run(query, {"projection": projection_name}))
                self._pending_tasks.add(future)
                try:
                    result = await asyncio.wrap_future(future)
                    data = await result.data()
                    exists = data[0].get("exists", False) if data else False
                finally:
                    self._pending_tasks.remove(future)
                
                if exists:
                    await graph_cache.set_async(f"projection:{projection_name}", "valid", expire=3600)
                    self._projections[projection_name] = {"valid": True}
                    return True
                
                return False
            finally:
                await session.close()
            
        if error_boundary.error:
            log(f"Error checking projection validity: {error_boundary.error}", level="error")
            return False
    
    @handle_async_errors(error_types=(Neo4jError, DatabaseError))
    async def _create_projection(self, repo_id: int, projection_name: str) -> None:
        """Creates or updates graph projection."""
        # Check if we already have nodes for this repo
        session = await connection_manager.get_session()
        try:
            count_query = """
            MATCH (n:Code {repo_id: $repo_id})
            RETURN count(n) as count
            """
            future = submit_async_task(session.run(count_query, {"repo_id": repo_id}))
            self._pending_tasks.add(future)
            try:
                result = await asyncio.wrap_future(future)
                data = await result.data()
                node_count = data[0]["count"] if data else 0
            finally:
                self._pending_tasks.remove(future)
            
            if node_count == 0:
                log(f"No nodes found for repo {repo_id}, skipping projection", level="warn")
                return
            
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
            
            future = submit_async_task(session.run(projection_query, {"repo_id": repo_id}))
            self._pending_tasks.add(future)
            try:
                await asyncio.wrap_future(future)
                await graph_cache.set_async(f"projection:{projection_name}", True)
                log(f"Created graph projection: {projection_name}", level="info")
            finally:
                self._pending_tasks.remove(future)
        finally:
            await session.close()
    
    @handle_async_errors(error_types=(Neo4jError, DatabaseError))
    async def _create_pattern_projection(self, repo_id: int, graph_name: str) -> None:
        """Creates a Neo4j in-memory graph projection for patterns."""
        session = await connection_manager.get_session()
        try:
            # Check if we already have pattern nodes
            count_query = """
            MATCH (p:Pattern {repo_id: $repo_id})
            RETURN count(p) as count
            """
            future = submit_async_task(session.run(count_query, {"repo_id": repo_id}))
            self._pending_tasks.add(future)
            try:
                result = await asyncio.wrap_future(future)
                data = await result.data()
                pattern_count = data[0]["count"] if data else 0
            finally:
                self._pending_tasks.remove(future)
            
            if pattern_count == 0:
                log(f"No pattern nodes found for repo {repo_id}, skipping pattern projection", level="warn")
                return
            
            projection_query = """
            CALL gds.graph.project.cypher(
                $graph_name,
                'MATCH (n) 
                 WHERE (n:Pattern AND n.repo_id = $repo_id) OR 
                       (n:Code AND n.repo_id = $repo_id) OR 
                       (n:Repository AND n.id = $repo_id) OR
                       (n:AIInsight AND exists((n)<-[:HAS_INSIGHT]-(:Pattern {repo_id: $repo_id}))) OR
                       (n:AIMetric AND exists((n)<-[:HAS_METRIC]-(:Pattern {repo_id: $repo_id}))) OR
                       (n:AIRecommendation AND exists((n)<-[:HAS_RECOMMENDATION]-(:Pattern {repo_id: $repo_id})))
                 RETURN id(n) AS id, labels(n) AS labels, properties(n) AS properties',
                'MATCH (s)-[r]->(t)
                 WHERE (s:Pattern OR s:Code OR s:Repository OR s:AIInsight OR s:AIMetric OR s:AIRecommendation) AND
                       (t:Pattern OR t:Code OR t:Repository OR t:AIInsight OR t:AIMetric OR t:AIRecommendation) AND
                       (s.repo_id = $repo_id OR t.repo_id = $repo_id OR
                        exists((s)<-[:HAS_INSIGHT|HAS_METRIC|HAS_RECOMMENDATION]-(:Pattern {repo_id: $repo_id})) OR
                        exists((t)<-[:HAS_INSIGHT|HAS_METRIC|HAS_RECOMMENDATION]-(:Pattern {repo_id: $repo_id})))
                 RETURN id(s) AS source, id(t) AS target, type(r) AS type, properties(r) AS properties',
                {validateRelationships: false}
            )
            """
            
            future = submit_async_task(session.run(projection_query, {"graph_name": graph_name, "repo_id": repo_id}))
            self._pending_tasks.add(future)
            try:
                await asyncio.wrap_future(future)
                await graph_cache.set_async(f"projection:{graph_name}", True)
                log(f"Created pattern graph projection with AI enhancements: {graph_name}", level="info")
            finally:
                self._pending_tasks.remove(future)
        finally:
            await session.close()
    
    @handle_async_errors(error_types=[Neo4jError, DatabaseError])
    async def _drop_projection(self, projection_name: str) -> None:
        """Drops existing graph projection."""
        session = await connection_manager.get_session()
        try:
            query = "CALL gds.graph.drop($projection)"
            future = submit_async_task(session.run(query, {"projection": projection_name}))
            self._pending_tasks.add(future)
            try:
                await asyncio.wrap_future(future)
                await graph_cache.clear_pattern_async(f"projection:{projection_name}")
                log(f"Dropped graph projection: {projection_name}", level="info")
            finally:
                self._pending_tasks.remove(future)
        finally:
            await session.close()

    async def queue_projection_update(self, repo_id: int) -> None:
        """Queue projection update with debouncing."""
        if repo_id not in self._projections:
            self._projections[repo_id] = {}
        
        if not self._update_task or self._update_task.done():
            self._update_task = submit_async_task(self._process_updates())
            self._pending_tasks.add(self._update_task)
    
    async def _process_updates(self) -> None:
        """Process queued updates with debouncing."""
        try:
            await asyncio.sleep(1.0)  # Debounce window
            async with self._lock:
                futures = []
                for repo_id, projection in self._projections.items():
                    if not projection.get("valid", False):
                        future = submit_async_task(self.ensure_projection(repo_id))
                        futures.append((future, repo_id))
                        self._pending_tasks.add(future)
                
                try:
                    for future, repo_id in futures:
                        await asyncio.wrap_future(future)
                        self._projections[repo_id]["valid"] = True
                finally:
                    for future, _ in futures:
                        if future in self._pending_tasks:
                            self._pending_tasks.remove(future)
                self._projections.clear()
        finally:
            if self._update_task in self._pending_tasks:
                self._pending_tasks.remove(self._update_task)
    
    @handle_async_errors(error_types=(Neo4jError, TransactionError))
    async def create_repository_with_reference_projection(self, active_repo_id: int, reference_repo_id: int) -> None:
        """Creates a combined graph projection of active and reference repositories."""
        graph_name = f"active-reference-{active_repo_id}-{reference_repo_id}"
        
        session = await connection_manager.get_session()
        try:
            projection_query = """
            CALL gds.graph.project.cypher(
                $graph_name,
                'MATCH (n) 
                 WHERE (n:Pattern AND (n.repo_id = $active_repo_id OR n.repo_id = $reference_repo_id)) OR 
                       (n:Code AND (n.repo_id = $active_repo_id OR n.repo_id = $reference_repo_id)) OR
                       (n:AIInsight AND exists((n)<-[:HAS_INSIGHT]-(:Pattern {repo_id: $active_repo_id}))) OR
                       (n:AIInsight AND exists((n)<-[:HAS_INSIGHT]-(:Pattern {repo_id: $reference_repo_id}))) OR
                       (n:AIMetric AND exists((n)<-[:HAS_METRIC]-(:Pattern {repo_id: $active_repo_id}))) OR
                       (n:AIMetric AND exists((n)<-[:HAS_METRIC]-(:Pattern {repo_id: $reference_repo_id}))) OR
                       (n:AIRecommendation AND exists((n)<-[:HAS_RECOMMENDATION]-(:Pattern {repo_id: $active_repo_id}))) OR
                       (n:AIRecommendation AND exists((n)<-[:HAS_RECOMMENDATION]-(:Pattern {repo_id: $reference_repo_id})))
                 RETURN id(n) AS id, labels(n) AS labels, properties(n) AS properties',
                'MATCH (s)-[r]->(t) 
                 WHERE (s:Pattern OR s:Code OR s:AIInsight OR s:AIMetric OR s:AIRecommendation) AND 
                       (t:Pattern OR t:Code OR s:AIInsight OR s:AIMetric OR s:AIRecommendation) AND 
                       ((s.repo_id = $active_repo_id OR s.repo_id = $reference_repo_id) OR
                        (t.repo_id = $active_repo_id OR t.repo_id = $reference_repo_id) OR
                        exists((s)<-[:HAS_INSIGHT|HAS_METRIC|HAS_RECOMMENDATION]-(:Pattern {repo_id: $active_repo_id})) OR
                        exists((s)<-[:HAS_INSIGHT|HAS_METRIC|HAS_RECOMMENDATION]-(:Pattern {repo_id: $reference_repo_id})) OR
                        exists((t)<-[:HAS_INSIGHT|HAS_METRIC|HAS_RECOMMENDATION]-(:Pattern {repo_id: $active_repo_id})) OR
                        exists((t)<-[:HAS_INSIGHT|HAS_METRIC|HAS_RECOMMENDATION]-(:Pattern {repo_id: $reference_repo_id})))
                 RETURN id(s) AS source, id(t) AS target, type(r) AS type, properties(r) AS properties',
                {validateRelationships: false}
            )
            """
            
            future = submit_async_task(session.run(projection_query, {
                "graph_name": graph_name,
                "active_repo_id": active_repo_id,
                "reference_repo_id": reference_repo_id
            }))
            self._pending_tasks.add(future)
            try:
                await asyncio.wrap_future(future)
                log(f"Created combined active-reference graph projection with AI enhancements: {graph_name}", level="info")
            finally:
                self._pending_tasks.remove(future)
        finally:
            await session.close()
    
    @handle_async_errors(error_types=(Neo4jError, TransactionError))
    async def compare_repository_structures(self, active_repo_id: int, reference_repo_id: int) -> dict:
        """Compares the structure of an active repository with a reference repository."""
        # Create combined projection if needed
        graph_name = f"active-reference-{active_repo_id}-{reference_repo_id}"
        
        try:
            await self.create_repository_with_reference_projection(active_repo_id, reference_repo_id)
        except Exception as e:
            log(f"Error creating combined projection: {e}", level="error")
            return {"error": str(e)}
        
        session = await connection_manager.get_session()
        try:
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
            
            future = submit_async_task(session.run(similarity_query, {"graph_name": graph_name}))
            self._pending_tasks.add(future)
            try:
                result = await asyncio.wrap_future(future)
                similarity_results = await result.data()
            finally:
                self._pending_tasks.remove(future)
            
            # Get structure statistics for each repo
            active_stats_query = """
            MATCH (c:Code {repo_id: $repo_id})
            RETURN c.language AS language, count(*) AS file_count
            ORDER BY file_count DESC
            """
            
            future = submit_async_task(session.run(active_stats_query, {"repo_id": active_repo_id}))
            self._pending_tasks.add(future)
            try:
                result = await asyncio.wrap_future(future)
                active_stats = await result.data()
            finally:
                self._pending_tasks.remove(future)
            
            return {
                "similarities": similarity_results,
                "active_stats": active_stats
            }
        finally:
            await session.close()
    
    @handle_async_errors(error_types=(Neo4jError, TransactionError, DatabaseError))
    async def sync_graph(self, nodes: List[Dict[str, Any]], relationships: List[Dict[str, Any]]) -> bool:
        """Synchronize graph with provided nodes and relationships.
        
        Args:
            nodes: List of node dictionaries with properties
            relationships: List of relationship dictionaries with properties
            
        Returns:
            bool: True if synchronization was successful
        """
        session = await connection_manager.get_session()
        try:
            tx = await session.begin_transaction()
            try:
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
                return True
            except Exception as e:
                log(f"Error in graph synchronization: {str(e)}", level="error")
                await tx.rollback()
                return False
        finally:
            await session.close()

# Create singleton instance of GraphSyncCoordinator
_graph_sync = GraphSyncCoordinator()

# Export with proper async handling
async def get_graph_sync() -> GraphSyncCoordinator:
    """Get the graph sync coordinator instance.
    
    Returns:
        GraphSyncCoordinator: The singleton graph sync coordinator instance
    """
    if not _graph_sync._initialized:
        await _graph_sync.ensure_initialized()
    return _graph_sync

# For backward compatibility and direct access
graph_sync = _graph_sync 