"""
Neo4j Graph Analysis Capabilities using APOC and Graph Data Science.
Provides graph-based code analysis features.
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
    AsyncErrorBoundary
)
from config import neo4j_config

class GraphAnalysis:
    """Graph-based code analysis capabilities using GDS."""
    
    def __init__(self):
        with ErrorBoundary("Neo4j tools initialization"):
            self.neo4j = Neo4jTools()
            self.projections = Neo4jProjections()
            
            # Validate Neo4j configuration and plugins
            self._validate_plugins()
    
    def _validate_plugins(self):
        """Validate that required plugins are installed."""
        plugins_query = "CALL dbms.procedures()"
        results = self.neo4j.run_sync(plugins_query)
        procedures = [r["name"] for r in results]
        
        required = ["gds.", "apoc."]
        missing = [p for p in required if not any(proc.startswith(p) for proc in procedures)]
        if missing:
            raise ProcessingError(f"Missing required Neo4j plugins: {', '.join(missing)}")
    
    @handle_async_errors(error_types=(ProcessingError, DatabaseError))
    async def get_code_metrics(
        self,
        repo_id: int,
        file_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get advanced code metrics using GDS."""
        async with AsyncErrorBoundary("code metrics analysis"):
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
        async with AsyncErrorBoundary("structure analysis"):
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
        async with AsyncErrorBoundary("similarity analysis"):
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
    
    @handle_errors(error_types=ProcessingError)
    def close(self):
        """Closes Neo4j connections."""
        with ErrorBoundary("Neo4j connection cleanup"):
            self.neo4j.close()
            self.projections.close()

# Global instance
graph_analysis = GraphAnalysis() 