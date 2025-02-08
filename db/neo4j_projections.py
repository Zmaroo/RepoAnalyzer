from db.neo4j import run_query
from utils.logger import log
from typing import Dict, List, Optional, Any

class Neo4jProjections:
    @staticmethod
    def create_code_dependency_projection(graph_name: str) -> Dict:
        """
        Creates a graph projection optimized for code dependency analysis.
        Uses the new Cypher projection syntax (not legacy).
        """
        query = """
        MATCH (n:Code)
        OPTIONAL MATCH (n)-[r]->(m:Code)
        WHERE type(r) IN ['CALLS', 'IMPORTS', 'CONTAINS', 'DEPENDS_ON']
        WITH gds.graph.project(
            $graph_name,
            n,
            m,
            {
                sourceNodeProperties: n {
                    .language,
                    .type,
                    .complexity,
                    .lines_of_code
                },
                targetNodeProperties: m {
                    .language,
                    .type,
                    .complexity,
                    .lines_of_code
                },
                relationshipType: type(r)
            }
        ) AS g
        RETURN g.graphName AS graph, 
               g.nodeCount AS nodes, 
               g.relationshipCount AS rels
        """
        try:
            result = run_query(query, {'graph_name': graph_name})
            log(f"Created code dependency projection '{graph_name}'", level="info")
            return result[0] if result else {}
        except Exception as e:
            log(f"Error creating code dependency projection: {e}", level="error")
            return {}

    @staticmethod
    def estimate_projection_memory(node_count: int, relationship_count: int) -> Dict:
        """
        Estimates memory requirements for graph projection.
        """
        query = """
        CALL gds.graph.project.estimate('*', '*', {
            nodeCount: $node_count,
            relationshipCount: $rel_count
        })
        YIELD requiredMemory, bytesMin, bytesMax
        RETURN requiredMemory, bytesMin, bytesMax
        """
        try:
            result = run_query(query, {
                'node_count': node_count,
                'rel_count': relationship_count
            })
            return result[0] if result else {}
        except Exception as e:
            log(f"Error estimating projection memory: {e}", level="error")
            return {}

    @staticmethod
    def run_community_detection(graph_name: str) -> List[Dict]:
        """
        Runs Louvain community detection algorithm on the projected graph.
        """
        query = """
        CALL gds.louvain.stream($graph_name, {
            relationshipTypes: ['CALLS', 'IMPORTS', 'CONTAINS', 'DEPENDS_ON'],
            nodeLabels: ['Code']
        })
        YIELD nodeId, communityId, intermediateCommunityIds
        WITH gds.util.asNode(nodeId) AS node, communityId
        RETURN node.file_path AS file_path,
               node.type AS component_type,
               communityId AS community
        ORDER BY community
        """
        try:
            return run_query(query, {'graph_name': graph_name})
        except Exception as e:
            log(f"Error running community detection: {e}", level="error")
            return []

    @staticmethod
    def run_centrality_analysis(graph_name: str) -> List[Dict]:
        """
        Runs multiple centrality algorithms to identify important code components.
        """
        query = """
        CALL gds.betweenness.stream($graph_name, {
            relationshipTypes: ['CALLS', 'IMPORTS', 'CONTAINS', 'DEPENDS_ON']
        })
        YIELD nodeId, score
        WITH gds.util.asNode(nodeId) AS node, score
        RETURN node.file_path AS file_path,
               node.type AS component_type,
               score AS centrality_score
        ORDER BY centrality_score DESC
        LIMIT 10
        """
        try:
            return run_query(query, {'graph_name': graph_name})
        except Exception as e:
            log(f"Error running centrality analysis: {e}", level="error")
            return [] 