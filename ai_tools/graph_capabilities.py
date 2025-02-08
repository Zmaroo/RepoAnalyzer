"""
Neo4j Graph Analysis Capabilities

This module provides the main interface for AI assistants to access
graph analysis tools and capabilities.
"""

from typing import Dict, List, Optional, Any
from db.neo4j_tools import Neo4jTools
from db.neo4j_projections import Neo4jProjections

class GraphAnalysisCapabilities:
    """
    A class that documents and provides access to all graph analysis capabilities.
    This class serves as the main interface for AI assistants to analyze code repositories.
    """
    
    def __init__(self):
        self.neo4j = Neo4jTools()
        self.projections = Neo4jProjections()
    
    def analyze_code_structure(self, repo_id: int) -> Dict[str, Any]:
        """
        Performs comprehensive code structure analysis.
        
        Args:
            repo_id: The repository ID to analyze
            
        Returns:
            Dictionary containing:
            - communities: List of code communities
            - central_components: List of important components
            - complexity_metrics: Code complexity metrics
            - dependency_stats: Dependency statistics
        """
        graph_name = f"code_dep_{repo_id}"
        
        # Get communities
        communities = self.projections.run_community_detection(graph_name)
        
        # Get central components
        central_components = self.projections.run_centrality_analysis(graph_name)
        
        # Get complexity metrics
        complexity_metrics = self.neo4j.run_query("""
            MATCH (n:Code {repo_id: $repo_id})
            RETURN 
                avg(n.complexity) as avg_complexity,
                max(n.complexity) as max_complexity,
                avg(n.lines_of_code) as avg_loc
        """, {'repo_id': repo_id})
        
        # Get dependency statistics
        dependency_stats = self.neo4j.run_query("""
            MATCH (n:Code {repo_id: $repo_id})-[r]->(m:Code {repo_id: $repo_id})
            RETURN 
                type(r) as relationship_type,
                count(*) as count
        """, {'repo_id': repo_id})
        
        return {
            'communities': communities,
            'central_components': central_components,
            'complexity_metrics': complexity_metrics,
            'dependency_stats': dependency_stats
        }
    
    def find_similar_code(self, file_path: str, repo_id: int, limit: int = 5) -> List[Dict]:
        """
        Finds similar code components using node2vec embeddings.
        
        Args:
            file_path: Path to the source file
            repo_id: Repository ID
            limit: Maximum number of similar components to return
            
        Returns:
            List of similar code components with similarity scores
        """
        return self.neo4j.find_similar_components(file_path, repo_id, limit)
    
    def trace_code_flow(self, entry_point: str, repo_id: int) -> List[Dict]:
        """
        Traces code flow from an entry point.
        
        Args:
            entry_point: Path to the entry point file
            repo_id: Repository ID
            
        Returns:
            List of code paths and their relationships
        """
        return self.neo4j.analyze_code_paths(entry_point, repo_id)
    
    def get_code_metrics(self, repo_id: int) -> Dict[str, Any]:
        """
        Gets comprehensive code metrics.
        
        Args:
            repo_id: Repository ID
            
        Returns:
            Dictionary containing various code metrics
        """
        metrics_query = """
        MATCH (n:Code {repo_id: $repo_id})
        OPTIONAL MATCH (n)-[r]->(m:Code {repo_id: $repo_id})
        WITH n, type(r) as rel_type, count(r) as rel_count
        RETURN 
            n.file_path as file_path,
            n.language as language,
            n.complexity as complexity,
            n.lines_of_code as loc,
            collect({type: rel_type, count: rel_count}) as relationships
        """
        return self.neo4j.run_query(metrics_query, {'repo_id': repo_id})

    def close(self):
        """Closes Neo4j connections."""
        self.neo4j.close() 