"""[4.3] Graph-based code analysis capabilities.

Flow:
1. Analysis Operations:
   - Code metrics calculation
   - Structure analysis
   - Similarity detection

2. Integration Points:
   - Neo4jTools [6.2]: Graph operations
   - Neo4jProjections [6.2]: Graph projections
   - GDS Library: Graph algorithms

3. Error Handling:
   - ProcessingError: Analysis operations
   - DatabaseError: Graph operations
"""

from typing import Dict, List, Optional, Any
from db.neo4j_ops import run_query, Neo4jTools
from db.neo4j_ops import Neo4jProjections
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

class GraphAnalysis:
    """[4.3.1] Graph-based code analysis capabilities using GDS."""
    
    def __init__(self):
        with ErrorBoundary("Neo4j tools initialization", severity=ErrorSeverity.CRITICAL):
            self.neo4j = Neo4jTools()
            self.projections = Neo4jProjections()
            
            # Validate Neo4j configuration and plugins
            # Skip validation during initialization to avoid sync/async issues
            # We'll validate when methods are actually called
            pass
    
    async def _validate_plugins(self):
        """Validate that required plugins are installed."""
        plugins_query = "CALL dbms.procedures()"
        results = await run_query(plugins_query)
        procedures = [r["name"] for r in results]
        
        required = ["gds.", "apoc."]
        missing = [p for p in required if not any(proc.startswith(p) for proc in procedures)]
        if missing:
            log(f"Missing required Neo4j plugins: {', '.join(missing)}", level="warning")
            return False
        return True
    
    @handle_async_errors(error_types=(ProcessingError, DatabaseError))
    async def get_code_metrics(
        self,
        repo_id: int,
        file_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """[4.3.2] Get advanced code metrics using GDS."""
        async with AsyncErrorBoundary("code metrics analysis", severity=ErrorSeverity.ERROR):
            file_filter = 'WHERE n.file_path = $file_path' if file_path else ''
            
            # Use GDS for centrality and community detection
            query = f"""
            CALL gds.graph.project.cypher(
                'code-graph',
                'MATCH (n:Code) WHERE n.repo_id = $repo_id {file_filter} RETURN id(n) AS id',
                'MATCH (n:Code)-[r]->(m:Code) WHERE n.repo_id = $repo_id RETURN id(n) AS source, id(m) AS target'
            )
            YIELD graphName
            
            CALL gds.pageRank.stream('code-graph')
            YIELD nodeId, score as pageRank
            
            CALL gds.louvain.stream('code-graph')
            YIELD nodeId, communityId
            
            WITH nodeId, pageRank, communityId
            MATCH (n:Code) WHERE id(n) = nodeId
            RETURN n.file_path as file_path,
                   pageRank as centrality,
                   communityId as community,
                   size((n)-->()) as outDegree,
                   apoc.node.degree(n) as totalDegree
            """
            
            params = {"repo_id": repo_id}
            if file_path:
                params["file_path"] = file_path
                
            results = await run_query(query, params)
            
            # Cleanup temporary graph
            await run_query("CALL gds.graph.drop('code-graph')")
            
            return results[0] if results else {}
    
    @handle_async_errors(error_types=(ProcessingError, DatabaseError))
    async def analyze_code_structure(
        self,
        repo_id: int
    ) -> Dict[str, Any]:
        """Analyze code structure using GDS algorithms."""
        async with AsyncErrorBoundary("structure analysis", severity=ErrorSeverity.ERROR):
            query = """
            CALL gds.graph.project.cypher(
                'code-structure',
                'MATCH (n:Code) WHERE n.repo_id = $repo_id RETURN id(n) AS id',
                'MATCH (n:Code)-[r]->(m:Code) WHERE n.repo_id = $repo_id RETURN id(n) AS source, id(m) AS target'
            )
            
            CALL gds.louvain.stream('code-structure')
            YIELD nodeId, communityId
            WITH gds.util.asNode(nodeId) as node, communityId
            WITH collect({file: node.file_path, community: communityId}) as communities
            
            CALL gds.betweenness.stream('code-structure')
            YIELD nodeId, score
            WITH communities, gds.util.asNode(nodeId) as node, score
            WHERE score > 0
            WITH communities, collect({file: node.file_path, score: score}) as central_files
            
            RETURN communities, central_files
            """
            
            results = await run_query(query, {"repo_id": repo_id})
            await run_query("CALL gds.graph.drop('code-structure')")
            
            return results[0] if results else {}
    
    @handle_async_errors(error_types=(ProcessingError, DatabaseError))
    async def find_similar_components(
        self,
        file_path: str,
        repo_id: int,
        similarity_cutoff: float = 0.8
    ) -> List[Dict[str, Any]]:
        """Find similar code components using node2vec."""
        async with AsyncErrorBoundary("similarity analysis", severity=ErrorSeverity.ERROR):
            query = """
            CALL gds.graph.project.cypher(
                'similarity-graph',
                'MATCH (n:Code) WHERE n.repo_id = $repo_id RETURN id(n) AS id',
                'MATCH (n:Code)-[r]->(m:Code) WHERE n.repo_id = $repo_id RETURN id(n) AS source, id(m) AS target'
            )
            
            CALL gds.node2vec.stream('similarity-graph', {
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
            
            results = await run_query(
                query,
                {
                    "repo_id": repo_id,
                    "file_path": file_path,
                    "cutoff": similarity_cutoff
                }
            )
            
            await run_query("CALL gds.graph.drop('similarity-graph')")
            return results
    
    @handle_async_errors(error_types=(ProcessingError, DatabaseError))
    async def get_references(self, repo_id: int, file_path: str) -> list:
        """Retrieve code references for a given file via Neo4j."""
        async with AsyncErrorBoundary("reference retrieval", severity=ErrorSeverity.ERROR):
            query = """
            MATCH (n:Code {repo_id: $repo_id, file_path: $file_path})-[:RELATED_TO]->(m:Code)
            RETURN m.file_path as file_path
            """
            results = await run_query(query, {"repo_id": repo_id, "file_path": file_path})
            return results if results else []
    
    @handle_async_errors(error_types=(ProcessingError, DatabaseError))
    async def get_dependencies(self, repo_id: int, file_path: str, depth: int = 3) -> list:
        """Retrieve code dependencies up to a specified depth using variable-length relationships."""
        async with AsyncErrorBoundary("dependency retrieval", severity=ErrorSeverity.ERROR):
            query = """
            MATCH (n:Code {repo_id: $repo_id, file_path: $file_path})-[:DEPENDS_ON*1..$depth]->(dep:Code)
            RETURN dep.file_path as file_path
            """
            results = await run_query(query, {"repo_id": repo_id, "file_path": file_path, "depth": depth})
            return results if results else []
    
    @handle_errors(error_types=(Exception,))
    def close(self):
        """Closes Neo4j connections and graph projections."""
        with ErrorBoundary("Neo4j connection cleanup", severity=ErrorSeverity.WARNING):
            if hasattr(self, 'neo4j'):
                try:
                    self.neo4j.close()
                except Exception as e:
                    log(f"Error closing neo4j connection: {e}", level="error")
            if hasattr(self, 'projections'):
                try:
                    self.projections.close()
                except Exception as e:
                    log(f"Error closing projections: {e}", level="error")

# Do not create global instance until implementation is ready
graph_analysis = None 