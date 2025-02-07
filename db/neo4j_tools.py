from neo4j import GraphDatabase
from utils.logger import log

class Neo4jTools:
    def __init__(self, uri="bolt://localhost:7687", user="neo4j", password="neo4j"):
        """
        Initializes the connection to Neo4j.
        Adjust the URI, username, and password as needed.
        """
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        """Closes the Neo4j driver connection."""
        self.driver.close()

    def run_query(self, query, parameters=None):
        """Generic query runner that returns a list of dictionaries for each record."""
        with self.driver.session() as session:
            result = session.run(query, parameters)
            return [record.data() for record in result]

    def run_pagerank(self):
        """
        Runs the PageRank algorithm on the code dependency graph using the Graph Data Science plugin.
        It assumes that code components are stored as nodes with the label 'Code' and that dependencies
        between them are modeled as relationships of type 'DEPENDS_ON'.
        
        Returns:
            A list of records containing the file path and PageRank score.
        """
        query = """
        CALL gds.pageRank.stream({
            nodeProjection: 'Code',
            relationshipProjection: {
                DEPENDS_ON: {
                    type: 'DEPENDS_ON',
                    orientation: 'NATURAL'
                }
            },
            maxIterations: 20,
            dampingFactor: 0.85
        })
        YIELD nodeId, score
        RETURN gds.util.asNode(nodeId).file_path AS file_path, score
        ORDER BY score DESC
        """
        log("Running PageRank algorithm...", level="debug")
        return self.run_query(query)

    def run_louvain(self):
        """
        Runs the Louvain community detection algorithm on the code dependency graph.
        Assumes that code nodes are labeled 'Code' and that they are connected by 'DEPENDS_ON' relationships.
        
        Returns:
            A list of records containing the file path, community ID, and weight.
        """
        query = """
        CALL gds.louvain.stream({
            nodeProjection: 'Code',
            relationshipProjection: {
                DEPENDS_ON: {
                    type: 'DEPENDS_ON',
                    orientation: 'NATURAL'
                }
            }
        })
        YIELD nodeId, communityId, weight
        RETURN gds.util.asNode(nodeId).file_path AS file_path, communityId, weight
        ORDER BY communityId, weight DESC
        """
        log("Running Louvain community detection...", level="debug")
        return self.run_query(query)

    def run_apoc_meta(self):
        """
        Executes an APOC procedure to retrieve metadata about the current Neo4j database.
        This can be used to help the assistant understand details like the counts of nodes and relationships.
        
        Returns:
            A dictionary of metadata statistics.
        """
        query = "CALL apoc.meta.stats()"
        log("Running APOC meta stats query...", level="debug")
        return self.run_query(query)
    
    def find_cross_repo_relationships(self):
        """
        Finds relationships between code nodes that belong to different repositories.
        This helps in understanding how code in one repository (e.g., the active project)
        depends on code from a reference repository, or vice versa.
        
        IMPORTANT: This query assumes that when indexing code, you store the 'repo_id' property on each node.
        
        Returns:
            A list of dictionaries containing:
                - source: File path for the source code node,
                - target: File path for the target code node,
                - source_repo: Repository ID for the source node,
                - target_repo: Repository ID for the target node,
                - relationship: The type of relationship (typically 'DEPENDS_ON'),
                - weight: Relationship weight (if applicable).
        """
        query = """
        MATCH (a:Code)-[r:DEPENDS_ON]->(b:Code)
        WHERE a.repo_id <> b.repo_id
        RETURN a.file_path AS source,
               b.file_path AS target,
               a.repo_id AS source_repo,
               b.repo_id AS target_repo,
               type(r) AS relationship,
               r.weight AS weight
        """
        log("Finding cross-repository relationships...", level="debug")
        return self.run_query(query)


if __name__ == "__main__":
    # For demonstration purposes. In your production setup, your assistant could call these methods directly.
    tools = Neo4jTools()
    try:
        pagerank_results = tools.run_pagerank()
        log(f"PageRank Results: {pagerank_results}")

        louvain_results = tools.run_louvain()
        log(f"Louvain Results: {louvain_results}")

        apoc_stats = tools.run_apoc_meta()
        log(f"APOC Meta Stats: {apoc_stats}")

        cross_repo_rels = tools.find_cross_repo_relationships()
        log(f"Cross-Repository Relationships: {cross_repo_rels}")
    finally:
        tools.close() 