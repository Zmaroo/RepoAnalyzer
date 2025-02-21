from neo4j import GraphDatabase
from config import neo4j_config
from utils.logger import log
from db.graph_sync import graph_sync
from utils.error_handling import (
    handle_errors,
    handle_async_errors,
    DatabaseError,
    ErrorBoundary,
    AsyncErrorBoundary
)
import logging

# Create the Neo4j driver instance using configuration from .env
with ErrorBoundary("Neo4j driver initialization", error_types=DatabaseError):
    driver = GraphDatabase.driver(
        neo4j_config.uri,
        auth=(neo4j_config.user, neo4j_config.password)
    )

# You can add a logging statement to confirm the connection
log(f"Connected to Neo4j Desktop at {neo4j_config.uri} using database '{neo4j_config.database}'", level="info")

@handle_errors(error_types=DatabaseError, default_return=[])
def run_query(cypher: str, params: dict = None) -> list:
    """Execute a Neo4j query."""
    with ErrorBoundary("Neo4j query execution", error_types=DatabaseError):
        with driver.session(database=neo4j_config.database) as session:
            result = session.run(cypher, params or {})
            return [record.data() for record in result]

class Neo4jTools:
    def __init__(self, config=neo4j_config):
        self.config = config
        with ErrorBoundary("Neo4j tools initialization", error_types=DatabaseError):
            self.driver = GraphDatabase.driver(
                config.uri,
                auth=(config.user, config.password)
            )
        logging.info("Neo4j driver initialized with URI: %s and Database: %s", config.uri, config.database)

    @handle_async_errors(error_types=DatabaseError)
    async def store_code_node(self, code_data: dict) -> None:
        """Store code node with graph synchronization."""
        async with AsyncErrorBoundary("Neo4j node storage", error_types=DatabaseError):
            query = """
            MERGE (n:Code {repo_id: $repo_id, file_path: $file_path})
            SET n += $properties
            """
            run_query(query, {
                "repo_id": code_data["repo_id"],
                "file_path": code_data["file_path"],
                "properties": code_data
            })
            
            await graph_sync.ensure_projection(code_data["repo_id"])
    
    @handle_async_errors(error_types=DatabaseError)
    async def update_code_relationships(self, repo_id: int, relationships: list) -> None:
        """Update code relationships with graph synchronization."""
        async with AsyncErrorBoundary("Neo4j relationship update", error_types=DatabaseError):
            query = """
            UNWIND $relationships as rel
            MATCH (s:Code {repo_id: $repo_id, file_path: rel.source})
            MATCH (t:Code {repo_id: $repo_id, file_path: rel.target})
            MERGE (s)-[r:rel.type]->(t)
            """
            run_query(query, {
                "repo_id": repo_id,
                "relationships": relationships
            })
            
            await graph_sync.invalidate_projection(repo_id)
            await graph_sync.ensure_projection(repo_id)

    @handle_errors(error_types=DatabaseError)
    def close(self):
        """Close Neo4j connection."""
        if self.driver:
            self.driver.close()
            logging.info("Neo4j driver closed.")

    def create_code_node(self, properties: dict) -> None:
        """Create or update a Code node in Neo4j"""
        cypher = """
        MERGE (c:Code {repo_id: $repo_id, file_path: $file_path})
        SET c += $properties,
            c.updated_at = timestamp()
        """
        with self.driver.session() as session:
            session.run(cypher, properties=properties)

    def create_doc_node(self, properties: dict) -> None:
        """Create or update a Documentation node in Neo4j"""
        try:
            with self.driver.session() as session:
                session.execute_write(self._create_or_update_doc_node, properties)
        except Exception as e:
            log(f"Error storing Documentation node in Neo4j: {e}", level="error")

    @staticmethod
    def _create_or_update_doc_node(tx, properties: dict):
        query = """
        MERGE (d:Documentation {repo_id: $repo_id, path: $path})
        SET d += $properties
        RETURN d
        """
        tx.run(query, properties=properties)

def create_schema_indexes_and_constraints():
    queries = [
        """CREATE CONSTRAINT code_unique_path IF NOT EXISTS 
           FOR (n:Code) REQUIRE (n.file_path, n.repo_id) IS UNIQUE""",
        """CREATE INDEX code_language_idx IF NOT EXISTS 
           FOR (n:Code) ON (n.language)""",
        """CREATE INDEX code_type_idx IF NOT EXISTS 
           FOR (n:Code) ON (n.type)""",
        """CREATE INDEX code_file_path_idx IF NOT EXISTS 
           FOR (n:Code) ON (n.file_path)""",
        """CREATE INDEX code_repo_id_idx IF NOT EXISTS 
           FOR (n:Code) ON (n.repo_id)""",
        """CREATE INDEX code_embedding_idx IF NOT EXISTS 
           FOR (n:Code) ON (n.embedding)""",
        """CREATE INDEX code_updated_at_idx IF NOT EXISTS 
           FOR (n:Code) ON (n.updated_at)"""
    ]
    for q in queries:
        try:
            run_query(q)
        except Exception as e:
            log(f"Error executing query: {q.strip()} - {e}", level="error")

def setup_graph_projections():
    count_query = "MATCH (n:Code) RETURN count(n) AS count"
    try:
        result = run_query(count_query)
        count = result[0].get("count", 0) if result else 0
        if count == 0:
            log("No Code nodes found; skipping graph projection.", level="warn")
            return
    except Exception as e:
        log(f"Error checking Code nodes count: {e}", level="error")
        return

    projection_query = """
    CALL gds.graph.project.cypher(
        'code-dependency-graph',
        'MATCH (n:Code) RETURN id(n) AS id, labels(n) AS labels, properties(n) AS properties',
        'MATCH (n:Code)-[r:CALLS|DEPENDS_ON|IMPORTS|CONTAINS]->(m:Code) RETURN id(n) AS source, id(m) AS target, type(r) AS type, properties(r) AS properties',
        { validateRelationships: false }
    )
    """
    try:
        run_query(projection_query)
        log("Successfully created graph projection 'code-dependency-graph'", level="debug")
    except Exception as e:
        log(f"Error creating graph projection: {e}", level="error")

@handle_async_errors(error_types=DatabaseError, default_return=False)
async def auto_reinvoke_projection_once(repo_id: int) -> bool:
    """Checks for Code nodes and invokes graph projection once if available."""
    async with AsyncErrorBoundary("graph projection", error_types=DatabaseError):
        result = run_query(
            "MATCH (n:Code) WHERE n.repo_id = $repo_id RETURN count(n) AS count",
            {"repo_id": repo_id}
        )
        code_count = result[0].get("count", 0) if result else 0
        
        if code_count > 0:
            log(f"Found {code_count} Code nodes. Ensuring graph projection.", level="info")
            return await graph_sync.ensure_projection(repo_id)
        else:
            log("No Code nodes found; skipping projection.", level="warn")
            return False 