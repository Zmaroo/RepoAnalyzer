"""Neo4j operations."""

from typing import Dict, Any, Optional, List
from db.connection import driver
from db.transaction import transaction_scope
from config import neo4j_config
from utils.logger import log
from db.graph_sync import graph_sync
from utils.error_handling import (
    handle_errors,
    handle_async_errors,
    DatabaseError,
    ErrorBoundary,
    AsyncErrorBoundary,
    Neo4jError,
    TransactionError
)
from parsers.types import (
    ExtractedFeatures,
    FeatureCategory
)
import logging

# You can add a logging statement to confirm the connection
log(f"Connected to Neo4j Desktop at {neo4j_config.uri} using database '{neo4j_config.database}'", level="info")

async def run_query(query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Run a Neo4j query and return results."""
    async with driver.session() as session:
        result = await session.run(query, params or {})
        return [record.data() for record in await result.fetch()]

class Neo4jTools:
    """[6.2.1] Neo4j database operations coordinator."""
    
    def __init__(self, config=neo4j_config):
        self.config = config
        with ErrorBoundary("Neo4j tools initialization", error_types=DatabaseError):
            self.driver = driver
        logging.info("Neo4j driver initialized with URI: %s and Database: %s", config.uri, config.database)

    @handle_async_errors(error_types=(Neo4jError, TransactionError))
    async def store_code_node(self, code_data: dict) -> None:
        """[6.2.2] Store code node with transaction coordination."""
        async with AsyncErrorBoundary("Neo4j node storage", error_types=(Neo4jError, TransactionError)):
            async with transaction_scope() as txn:
                try:
                    query = """
                    MERGE (n:Code {repo_id: $repo_id, file_path: $file_path})
                    SET n += $properties
                    """
                    await txn.neo4j_transaction.run(query, {
                        "repo_id": code_data["repo_id"],
                        "file_path": code_data["file_path"],
                        "properties": code_data
                    })
                    
                    log("Stored code node", level="debug", context={
                        "operation": "store_code_node",
                        "repo_id": code_data["repo_id"],
                        "file_path": code_data["file_path"]
                    })
                    
                except Exception as e:
                    raise Neo4jError(f"Failed to store code node: {str(e)}")
    
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
            await run_query(query, {
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

    @handle_async_errors(error_types=DatabaseError)
    async def store_node_with_features(
        self,
        repo_id: int,
        file_path: str,
        ast: dict,
        features: ExtractedFeatures
    ) -> None:
        """[6.2.3] Store node with all its features and relationships."""
        # Create base node
        query = """
        MERGE (n:Content {repo_id: $repo_id, file_path: $file_path})
        SET n += $properties
        """
        
        # Properties from all feature categories
        properties = {
            "repo_id": repo_id,
            "file_path": file_path,
            "ast": ast,
            "syntax_features": features.get_category(FeatureCategory.SYNTAX),
            "semantic_features": features.get_category(FeatureCategory.SEMANTICS),
            "doc_features": features.get_category(FeatureCategory.DOCUMENTATION),
            "structural_features": features.get_category(FeatureCategory.STRUCTURE)
        }
        
        await run_query(query, properties)
        await self.create_feature_relationships(repo_id, file_path, features)

    @handle_async_errors(error_types=DatabaseError)
    async def store_pattern_node(self, pattern_data: dict) -> None:
        """[6.2.6] Store code pattern node for reference repository learning."""
        async with AsyncErrorBoundary("Neo4j pattern node storage", error_types=(Neo4jError, TransactionError)):
            # Create pattern node
            query = """
            MERGE (p:Pattern {
                repo_id: $repo_id, 
                pattern_id: $pattern_id,
                pattern_type: $pattern_type
            })
            SET p += $properties,
                p.updated_at = timestamp()
            """
            
            await run_query(query, {
                "repo_id": pattern_data["repo_id"],
                "pattern_id": pattern_data["pattern_id"],
                "pattern_type": pattern_data["pattern_type"],
                "properties": pattern_data
            })
            
            # If this is a code pattern, create relationship to relevant code
            if pattern_data.get("file_path") and pattern_data.get("pattern_type") == "code_structure":
                rel_query = """
                MATCH (p:Pattern {repo_id: $repo_id, pattern_id: $pattern_id})
                MATCH (c:Code {repo_id: $repo_id, file_path: $file_path})
                MERGE (p)-[r:EXTRACTED_FROM]->(c)
                """
                
                await run_query(rel_query, {
                    "repo_id": pattern_data["repo_id"],
                    "pattern_id": pattern_data["pattern_id"],
                    "file_path": pattern_data["file_path"]
                })
            
            log("Stored pattern node", level="debug", context={
                "operation": "store_pattern_node",
                "repo_id": pattern_data["repo_id"],
                "pattern_id": pattern_data["pattern_id"],
                "pattern_type": pattern_data["pattern_type"]
            })

    @handle_async_errors(error_types=DatabaseError)
    async def link_patterns_to_repository(self, repo_id: int, pattern_ids: List[int], is_reference: bool = True) -> None:
        """[6.2.7] Link patterns to a repository with appropriate relationship type."""
        rel_type = "REFERENCE_PATTERN" if is_reference else "APPLIED_PATTERN"
        
        query = """
        MATCH (r:Repository {id: $repo_id})
        MATCH (p:Pattern {pattern_id: $pattern_id})
        MERGE (r)-[rel:%s]->(p)
        """ % rel_type
        
        for pattern_id in pattern_ids:
            await run_query(query, {
                "repo_id": repo_id,
                "pattern_id": pattern_id
            })

    @handle_async_errors(error_types=DatabaseError)
    async def find_similar_patterns(self, repo_id: int, file_path: str, limit: int = 5) -> List[Dict[str, Any]]:
        """[6.2.8] Find patterns similar to a given file."""
        # Get language of the file
        lang_query = """
        MATCH (c:Code {repo_id: $repo_id, file_path: $file_path})
        RETURN c.language as language
        """
        
        lang_result = await run_query(lang_query, {
            "repo_id": repo_id,
            "file_path": file_path
        })
        
        if not lang_result:
            return []
        
        language = lang_result[0].get("language")
        
        # Find patterns of the same language
        patterns_query = """
        MATCH (p:Pattern)
        WHERE p.language = $language AND p.pattern_type = 'code_structure'
        RETURN p.pattern_id as pattern_id, p.repo_id as repo_id, 
               p.language as language, p.file_path as file_path,
               p.elements as elements, p.sample as sample
        LIMIT $limit
        """
        
        return await run_query(patterns_query, {
            "language": language,
            "limit": limit
        })

def create_schema_indexes_and_constraints():
    """[6.2.4] Initialize Neo4j schema and constraints."""
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
           FOR (n:Code) ON (n.updated_at)""",
        """CREATE CONSTRAINT pattern_unique_id IF NOT EXISTS 
           FOR (p:Pattern) REQUIRE (p.pattern_id, p.repo_id) IS UNIQUE""",
        """CREATE INDEX pattern_type_idx IF NOT EXISTS 
           FOR (p:Pattern) ON (p.pattern_type)""",
        """CREATE INDEX pattern_language_idx IF NOT EXISTS 
           FOR (p:Pattern) ON (p.language)""",
        """CREATE INDEX pattern_repo_id_idx IF NOT EXISTS 
           FOR (p:Pattern) ON (p.repo_id)"""
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

    # Add pattern projection
    pattern_projection_query = """
    CALL gds.graph.project.cypher(
        'pattern-code-graph',
        'MATCH (n) WHERE n:Pattern OR n:Code RETURN id(n) AS id, labels(n) AS labels, properties(n) AS properties',
        'MATCH (n:Pattern)-[r:EXTRACTED_FROM]->(m:Code) RETURN id(n) AS source, id(m) AS target, type(r) AS type, properties(r) AS properties
         UNION
         MATCH (n:Repository)-[r:REFERENCE_PATTERN|APPLIED_PATTERN]->(m:Pattern) RETURN id(n) AS source, id(m) AS target, type(r) AS type, properties(r) AS properties',
        { validateRelationships: false }
    )
    """
    try:
        run_query(pattern_projection_query)
        log("Successfully created graph projection 'pattern-code-graph'", level="debug")
    except Exception as e:
        log(f"Error creating pattern graph projection: {e}", level="error")

@handle_async_errors(error_types=DatabaseError, default_return=False)
async def auto_reinvoke_projection_once(repo_id: int) -> bool:
    """[6.2.5] Checks for Code nodes and invokes graph projection once if available."""
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

class Neo4jProjections:
    """[6.2.9] Neo4j graph projections and algorithms for pattern analysis."""
    
    @handle_async_errors(error_types=DatabaseError)
    async def create_code_dependency_projection(self, graph_name: str) -> None:
        """Create a graph projection for code dependencies."""
        query = """
        CALL gds.graph.project.cypher(
            $graph_name,
            'MATCH (n:Code) RETURN id(n) AS id, labels(n) AS labels, properties(n) AS properties',
            'MATCH (n:Code)-[r:CALLS|DEPENDS_ON|IMPORTS|CONTAINS]->(m:Code) RETURN id(n) AS source, id(m) AS target, type(r) AS type, properties(r) AS properties',
            { validateRelationships: false }
        )
        """
        await run_query(query, {"graph_name": graph_name})
    
    @handle_async_errors(error_types=DatabaseError)
    async def create_pattern_projection(self, graph_name: str) -> None:
        """Create a graph projection including patterns and their relationships."""
        query = """
        CALL gds.graph.project.cypher(
            $graph_name,
            'MATCH (n) WHERE n:Pattern OR n:Code OR n:Repository RETURN id(n) AS id, labels(n) AS labels, properties(n) AS properties',
            'MATCH (n)-[r:EXTRACTED_FROM|REFERENCE_PATTERN|APPLIED_PATTERN]->(m) RETURN id(n) AS source, id(m) AS target, type(r) AS type, properties(r) AS properties',
            { validateRelationships: false }
        )
        """
        await run_query(query, {"graph_name": graph_name})
    
    @handle_async_errors(error_types=DatabaseError)
    async def run_pattern_similarity(self, graph_name: str) -> List[Dict[str, Any]]:
        """Run similarity algorithm to identify similar patterns."""
        query = """
        CALL gds.nodeSimilarity.stream($graph_name)
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
        return await run_query(query, {"graph_name": graph_name})
    
    @handle_async_errors(error_types=DatabaseError)
    async def find_pattern_clusters(self, graph_name: str) -> List[Dict[str, Any]]:
        """Find clusters of similar patterns using community detection."""
        query = """
        CALL gds.louvain.stream($graph_name)
        YIELD nodeId, communityId
        WITH gds.util.asNode(nodeId) AS node, communityId
        WHERE node:Pattern
        RETURN communityId, 
               collect(node.pattern_id) AS patterns,
               collect(node.pattern_type) AS pattern_types,
               count(*) AS cluster_size
        ORDER BY cluster_size DESC
        """
        return await run_query(query, {"graph_name": graph_name})
    
    @handle_async_errors(error_types=DatabaseError)
    async def get_component_dependencies(self, graph_name: str) -> List[Dict[str, Any]]:
        """Get dependencies between top-level components."""
        query = """
        MATCH (c1:Code)-[:IMPORTS|CALLS|DEPENDS_ON]->(c2:Code)
        WITH split(c1.file_path, '/')[0] AS comp1, 
             split(c2.file_path, '/')[0] AS comp2, 
             count(*) AS weight
        WHERE comp1 <> comp2
        RETURN comp1 AS source_component, 
               comp2 AS target_component, 
               weight
        ORDER BY weight DESC
        """
        return await run_query(query, {})
    
    @handle_async_errors(error_types=DatabaseError)
    async def recommend_patterns_for_file(self, repo_id: int, file_path: str, limit: int = 5) -> List[Dict[str, Any]]:
        """[6.2.10] Recommend patterns for a given file based on similarity."""
        # First get the language and structure of the file
        file_query = """
        MATCH (c:Code {repo_id: $repo_id, file_path: $file_path})
        RETURN c.language AS language, c.ast AS ast
        """
        file_result = await run_query(file_query, {"repo_id": repo_id, "file_path": file_path})
        
        if not file_result:
            return []
        
        language = file_result[0].get("language")
        
        # Find patterns of the same language
        patterns_query = """
        MATCH (p:Pattern)
        WHERE p.language = $language AND p.pattern_type = 'code_structure'
        RETURN p.pattern_id AS pattern_id, 
               p.repo_id AS repo_id, 
               p.language AS language, 
               p.file_path AS file_path,
               p.elements AS elements, 
               p.sample AS sample,
               p.pattern_type AS pattern_type
        LIMIT $limit
        """
        
        return await run_query(patterns_query, {"language": language, "limit": limit}) 