from db.neo4j import run_query
from utils.logger import log

def create_schema_constraints():
    """Creates necessary indexes and constraints for the Neo4j database."""
    constraints = [
        """CREATE CONSTRAINT code_unique_path IF NOT EXISTS
           FOR (n:Code) REQUIRE (n.file_path, n.repo_id) IS UNIQUE""",
        
        """CREATE INDEX code_language_idx IF NOT EXISTS
           FOR (n:Code) ON (n.language)""",
        
        """CREATE INDEX code_type_idx IF NOT EXISTS
           FOR (n:Code) ON (n.type)"""
    ]
    
    for constraint in constraints:
        try:
            run_query(constraint)
            log(f"Successfully created constraint/index: {constraint}", level="debug")
        except Exception as e:
            log(f"Error creating constraint/index: {e}", level="error")

def setup_graph_projections():
    """Sets up named graph projections for use with Graph Data Science library."""
    projections = [
        """
        CALL gds.graph.project.cypher(
            'code-dependency-graph',
            'MATCH (n:Code) RETURN id(n) AS id, labels(n) AS labels, properties(n) AS properties',
            'MATCH (n:Code)-[r:CALLS|DEPENDS_ON|IMPORTS|CONTAINS]->(m:Code) 
             RETURN id(n) AS source, id(m) AS target, type(r) AS type, properties(r) AS properties',
            {
                validateRelationships: false
            }
        )
        """
    ]
    
    for projection in projections:
        try:
            run_query(projection)
            log(f"Successfully created graph projection", level="debug")
        except Exception as e:
            log(f"Error creating graph projection: {e}", level="error") 