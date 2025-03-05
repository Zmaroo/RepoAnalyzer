"""[4.3] Graph-based code analysis capabilities.

Flow:
1. Analysis Operations:
   - Code metrics calculation
   - Structure analysis
   - Similarity detection

2. Integration Points:
   - Neo4jTools [6.2]: Graph operations
   - GraphSync [6.3]: Graph projections
   - GDS Library: Graph algorithms

3. Error Handling:
   - ProcessingError: Analysis operations
   - DatabaseError: Graph operations
"""

from typing import Dict, List, Optional, Any
import asyncio
from db.neo4j_ops import run_query, Neo4jTools
from utils.logger import log
from utils.error_handling import (
    handle_async_errors,
    handle_errors,
    ProcessingError,
    DatabaseError,
    ErrorBoundary,
    AsyncErrorBoundary,
    ErrorSeverity
)
from parsers.types import (
    FileType,
    ParserResult,
    ExtractedFeatures
)
from parsers.models import (
    FileClassification
)
from config import Neo4jConfig
from utils.async_runner import submit_async_task
from db.graph_sync import get_graph_sync

class GraphAnalysis:
    """[4.3.1] Graph-based code analysis capabilities using GDS."""
    
    def __init__(self):
        with ErrorBoundary("Neo4j tools initialization", severity=ErrorSeverity.CRITICAL):
            self.neo4j = Neo4jTools()
            self._pending_tasks = set()
            
            # Validate Neo4j configuration and plugins
            # Skip validation during initialization to avoid sync/async issues
            # We'll validate when methods are actually called
            pass
    
    async def _validate_plugins(self):
        """Validate that required plugins are installed."""
        future = submit_async_task(run_query("CALL dbms.procedures()"))
        self._pending_tasks.add(future)
        try:
            results = await asyncio.wrap_future(future)
            procedures = [r["name"] for r in results]
            
            required = ["gds.", "apoc."]
            missing = [p for p in required if not any(proc.startswith(p) for proc in procedures)]
            if missing:
                log(f"Missing required Neo4j plugins: {', '.join(missing)}", level="warning")
                return False
            return True
        finally:
            self._pending_tasks.remove(future)
    
    @handle_async_errors(error_types=(ProcessingError, DatabaseError))
    async def get_code_metrics(
        self,
        repo_id: int,
        file_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """[4.3.2] Get advanced code metrics using GDS."""
        async with AsyncErrorBoundary("code metrics analysis", severity=ErrorSeverity.ERROR):
            # Ensure code projection exists
            graph_sync = await get_graph_sync()
            await graph_sync.ensure_projection(repo_id)
            
            file_filter = 'WHERE n.file_path = $file_path' if file_path else ''
            
            # Use GDS for centrality and community detection
            query = f"""
            CALL gds.pageRank.stream('code-repo-' || $repo_id)
            YIELD nodeId, score as pageRank
            WITH gds.util.asNode(nodeId) AS n, pageRank
            WHERE n.repo_id = $repo_id {file_filter}
            RETURN n.file_path as file_path,
                   pageRank as centrality,
                   size((n)-->()) as outDegree,
                   apoc.node.degree(n) as totalDegree
            """
            
            params = {"repo_id": repo_id}
            if file_path:
                params["file_path"] = file_path
            
            future = submit_async_task(run_query(query, params))
            self._pending_tasks.add(future)
            try:
                results = await asyncio.wrap_future(future)
                return results[0] if results else {}
            finally:
                self._pending_tasks.remove(future)
    
    @handle_async_errors(error_types=(ProcessingError, DatabaseError))
    async def analyze_code_structure(
        self,
        repo_id: int
    ) -> Dict[str, Any]:
        """Analyze code structure using GDS algorithms."""
        async with AsyncErrorBoundary("structure analysis", severity=ErrorSeverity.ERROR):
            # Ensure code projection exists
            graph_sync = await get_graph_sync()
            await graph_sync.ensure_projection(repo_id)
            
            # Run community detection
            community_query = """
            CALL gds.louvain.stream('code-repo-' || $repo_id)
            YIELD nodeId, communityId
            WITH gds.util.asNode(nodeId) as node, communityId
            WITH collect({file: node.file_path, community: communityId}) as communities
            
            CALL gds.betweenness.stream('code-repo-' || $repo_id)
            YIELD nodeId, score
            WITH communities, gds.util.asNode(nodeId) as node, score
            WHERE score > 0
            WITH communities, collect({file: node.file_path, score: score}) as central_files
            
            RETURN communities, central_files
            """
            
            future = submit_async_task(run_query(community_query, {"repo_id": repo_id}))
            self._pending_tasks.add(future)
            try:
                results = await asyncio.wrap_future(future)
                return results[0] if results else {}
            finally:
                self._pending_tasks.remove(future)
    
    @handle_async_errors(error_types=(ProcessingError, DatabaseError))
    async def find_similar_components(
        self,
        file_path: str,
        repo_id: int,
        similarity_cutoff: float = 0.8
    ) -> List[Dict[str, Any]]:
        """Find similar code components using node2vec."""
        async with AsyncErrorBoundary("similarity analysis", severity=ErrorSeverity.ERROR):
            # Ensure code projection exists
            graph_sync = await get_graph_sync()
            await graph_sync.ensure_projection(repo_id)
            
            query = """
            CALL gds.node2vec.stream('code-repo-' || $repo_id, {
                walkLength: 80,
                walks: 10,
                dimensions: 128
            })
            YIELD nodeId, embedding
            
            WITH gds.util.asNode(nodeId) as node, embedding
            WHERE node.file_path = $file_path
            
            CALL gds.similarity.cosine.stream({
                data: [embedding],
                topK: 5,
                similarityCutoff: $cutoff
            })
            YIELD item2, similarity
            WITH item2, similarity
            
            MATCH (similar:Code)
            WHERE id(similar) = item2
            RETURN similar.file_path as file_path,
                   similarity as score
            ORDER BY score DESC
            """
            
            future = submit_async_task(run_query(
                query,
                {
                    "repo_id": repo_id,
                    "file_path": file_path,
                    "cutoff": similarity_cutoff
                }
            ))
            self._pending_tasks.add(future)
            try:
                results = await asyncio.wrap_future(future)
                return results
            finally:
                self._pending_tasks.remove(future)
    
    @handle_async_errors(error_types=(ProcessingError, DatabaseError))
    async def get_references(self, repo_id: int, file_path: str) -> list:
        """Retrieve code references for a given file via Neo4j."""
        async with AsyncErrorBoundary("reference retrieval", severity=ErrorSeverity.ERROR):
            query = """
            MATCH (n:Code {repo_id: $repo_id, file_path: $file_path})-[:RELATED_TO]->(m:Code)
            RETURN m.file_path as file_path
            """
            future = submit_async_task(run_query(query, {"repo_id": repo_id, "file_path": file_path}))
            self._pending_tasks.add(future)
            try:
                results = await asyncio.wrap_future(future)
                return results if results else []
            finally:
                self._pending_tasks.remove(future)
    
    @handle_async_errors(error_types=(ProcessingError, DatabaseError))
    async def analyze_code_patterns(self, repo_id: int) -> Dict[str, Any]:
        """Analyze code patterns in a repository using graph algorithms."""
        async with AsyncErrorBoundary("pattern analysis", severity=ErrorSeverity.ERROR):
            # Get graph sync coordinator
            graph_sync = await get_graph_sync()
            
            # Ensure pattern projection exists
            await graph_sync.ensure_pattern_projection(repo_id)
            
            # Run pattern similarity analysis
            similarity_query = """
            CALL gds.nodeSimilarity.stream('pattern-repo-' || $repo_id)
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
            future = submit_async_task(run_query(similarity_query, {"repo_id": repo_id}))
            self._pending_tasks.add(future)
            try:
                similarity_results = await asyncio.wrap_future(future)
            finally:
                self._pending_tasks.remove(future)
            
            # Find pattern clusters
            cluster_query = """
            CALL gds.louvain.stream('pattern-repo-' || $repo_id)
            YIELD nodeId, communityId
            WITH gds.util.asNode(nodeId) AS node, communityId
            WHERE node:Pattern
            RETURN communityId, 
                   collect(node.pattern_id) AS patterns,
                   collect(node.pattern_type) AS pattern_types,
                   count(*) AS cluster_size
            ORDER BY cluster_size DESC
            """
            future = submit_async_task(run_query(cluster_query, {"repo_id": repo_id}))
            self._pending_tasks.add(future)
            try:
                cluster_results = await asyncio.wrap_future(future)
            finally:
                self._pending_tasks.remove(future)
            
            # Get component dependencies
            dependency_query = """
            MATCH (c1:Code)-[:IMPORTS|CALLS|DEPENDS_ON]->(c2:Code)
            WHERE c1.repo_id = $repo_id AND c2.repo_id = $repo_id
            WITH split(c1.file_path, '/')[0] AS comp1, 
                 split(c2.file_path, '/')[0] AS comp2, 
                 count(*) AS weight
            WHERE comp1 <> comp2
            RETURN comp1 AS source_component, 
                   comp2 AS target_component, 
                   weight
            ORDER BY weight DESC
            """
            future = submit_async_task(run_query(dependency_query, {"repo_id": repo_id}))
            self._pending_tasks.add(future)
            try:
                dependency_results = await asyncio.wrap_future(future)
            finally:
                self._pending_tasks.remove(future)
            
            return {
                "similarities": similarity_results,
                "clusters": cluster_results,
                "dependencies": dependency_results
            }
    
    @handle_async_errors(error_types=(ProcessingError, DatabaseError))
    async def get_dependencies(self, repo_id: int, file_path: str, depth: int = 3) -> list:
        """Retrieve code dependencies up to a specified depth using variable-length relationships."""
        async with AsyncErrorBoundary("dependency retrieval", severity=ErrorSeverity.ERROR):
            # Ensure code projection exists
            graph_sync = await get_graph_sync()
            await graph_sync.ensure_projection(repo_id)
            
            query = """
            MATCH (n:Code {repo_id: $repo_id, file_path: $file_path})-[:DEPENDS_ON*1..$depth]->(dep:Code)
            RETURN dep.file_path as file_path
            """
            future = submit_async_task(run_query(query, {"repo_id": repo_id, "file_path": file_path, "depth": depth}))
            self._pending_tasks.add(future)
            try:
                results = await asyncio.wrap_future(future)
                return results if results else []
            finally:
                self._pending_tasks.remove(future)
    
    @handle_errors(error_types=(Exception,))
    async def close(self):
        """Closes Neo4j connections and graph projections."""
        with ErrorBoundary("Neo4j connection cleanup", severity=ErrorSeverity.WARNING):
            # Clean up any pending tasks
            if self._pending_tasks:
                await asyncio.gather(*[asyncio.wrap_future(f) for f in self._pending_tasks], return_exceptions=True)
                self._pending_tasks.clear()
            
            if hasattr(self, 'neo4j'):
                try:
                    await self.neo4j.close()
                except Exception as e:
                    log(f"Error closing neo4j connection: {e}", level="error")

# Do not create global instance until implementation is ready
graph_analysis = None 