from neo4j import GraphDatabase
from utils.logger import log
from typing import Dict, List, Optional, Any
import json

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

    def create_code_node(self, properties: Dict[str, Any]) -> Optional[Dict]:
        """
        Creates a Code node with the given properties.
        
        Args:
            properties: Dictionary containing node properties including:
                - file_path: str
                - repo_id: int
                - language: str
                - type: str (function, class, method, etc.)
                - name: str
                - ast_data: dict
                - complexity: int
                - lines_of_code: int
                - documentation: str
        """
        query = """
        MERGE (n:Code {file_path: $file_path, repo_id: $repo_id})
        SET n += $properties
        RETURN n
        """
        try:
            # Convert ast_data to JSON string if present
            if 'ast_data' in properties:
                properties['ast_data'] = json.dumps(properties['ast_data'])
            
            result = self.run_query(query, {
                'file_path': properties['file_path'],
                'repo_id': properties['repo_id'],
                'properties': properties
            })
            return result[0] if result else None
        except Exception as e:
            log(f"Error creating code node: {e}", level="error")
            return None

    def create_code_relationship(
        self,
        from_path: str,
        to_path: str,
        repo_id: int,
        rel_type: str,
        properties: Optional[Dict] = None
    ) -> bool:
        """
        Creates a relationship between two Code nodes.
        
        Args:
            from_path: File path of the source node
            to_path: File path of the target node
            repo_id: Repository ID
            rel_type: Type of relationship (CALLS, IMPORTS, etc.)
            properties: Optional relationship properties
        """
        query = """
        MATCH (a:Code {file_path: $from_path, repo_id: $repo_id})
        MATCH (b:Code {file_path: $to_path, repo_id: $repo_id})
        MERGE (a)-[r:%s]->(b)
        SET r += $properties
        RETURN r
        """ % rel_type

        try:
            result = self.run_query(query, {
                'from_path': from_path,
                'to_path': to_path,
                'repo_id': repo_id,
                'properties': properties or {}
            })
            return bool(result)
        except Exception as e:
            log(f"Error creating relationship: {e}", level="error")
            return False

    def run_node2vec(self) -> List[Dict]:
        """
        Runs node2vec to generate embeddings for code components.
        Requires the Graph Data Science library.
        """
        query = """
        CALL gds.node2vec.write('code-dependency-graph', {
            writeProperty: 'embedding',
            embeddingDimension: 128,
            walkLength: 80,
            walksPerNode: 10
        })
        YIELD nodePropertiesWritten
        RETURN nodePropertiesWritten
        """
        return self.run_query(query)

    def find_similar_components(self, file_path: str, repo_id: int, limit: int = 5) -> List[Dict]:
        """
        Finds similar code components based on node2vec embeddings.
        """
        query = """
        MATCH (n:Code {file_path: $file_path, repo_id: $repo_id})
        MATCH (other:Code)
        WHERE other <> n AND other.repo_id = $repo_id
        WITH n, other, gds.similarity.cosine(n.embedding, other.embedding) AS similarity
        WHERE similarity > 0.7
        RETURN other.file_path AS similar_file, 
               other.type AS component_type,
               similarity
        ORDER BY similarity DESC
        LIMIT $limit
        """
        return self.run_query(query, {
            'file_path': file_path,
            'repo_id': repo_id,
            'limit': limit
        })

    def analyze_code_paths(self, start_path: str, repo_id: int) -> List[Dict]:
        """
        Analyzes code paths using APOC path finding.
        """
        query = """
        MATCH (start:Code {file_path: $start_path, repo_id: $repo_id})
        CALL apoc.path.expandConfig(start, {
            relationshipFilter: 'CALLS|DEPENDS_ON|IMPORTS',
            uniqueness: 'NODE_PATH',
            maxLevel: 10
        })
        YIELD path
        RETURN [node in nodes(path) | node.file_path] as code_path,
               length(path) as depth,
               [rel in relationships(path) | type(rel)] as relationships
        ORDER BY depth
        """
        return self.run_query(query, {
            'start_path': start_path,
            'repo_id': repo_id
        })

    def upsert_code_node(self, repo_id: int, file_path: str, ast: dict, embedding: list = None):
        """
        Creates/updates a Code node with essential properties for graph analysis.
        """
        query = """
        MERGE (n:Code {repo_id: $repo_id, file_path: $file_path})
        SET n += {
            language: $language,
            type: $type,
            complexity: $complexity,
            lines_of_code: $loc,
            last_updated: datetime()
        }
        RETURN n
        """
        # Extract key properties from AST
        properties = {
            'repo_id': repo_id,
            'file_path': file_path,
            'language': ast.get('language'),
            'type': ast.get('type'),
            'complexity': self.calculate_complexity(ast),
            'loc': ast.get('lines_of_code', 0)
        }
        return self.run_query(query, properties)

    def calculate_complexity(self, ast: dict) -> int:
        """Calculate cyclomatic complexity from AST dictionary."""
        complexity = 1  # Base complexity
        
        # Control flow patterns that increase complexity
        control_patterns = [
            'if_statement', 'while_statement', 'for_statement',
            'case_statement', 'catch_clause', '&&', '||'
        ]
        
        def traverse(node: dict):
            nonlocal complexity
            if isinstance(node, dict):
                if node.get('type') in control_patterns:
                    complexity += 1
                for child in node.get('children', []):
                    traverse(child)
        
        traverse(ast)
        return complexity

    def extract_structural_properties(self, ast_features: Dict) -> Dict:
        """Extract structural properties from categorized AST features."""
        properties = {}
        
        # Extract syntax features
        if "syntax" in ast_features:
            properties.update({
                "functions": len(ast_features["syntax"].get("function", [])),
                "classes": len(ast_features["syntax"].get("class", [])),
                "modules": len(ast_features["syntax"].get("module", []))
            })
        
        # Extract semantic features
        if "semantics" in ast_features:
            properties.update({
                "variables": len(ast_features["semantics"].get("variable", [])),
                "types": len(ast_features["semantics"].get("type", []))
            })
        
        # Extract documentation features
        if "documentation" in ast_features:
            properties.update({
                "has_documentation": bool(ast_features["documentation"]),
                "doc_count": len(ast_features["documentation"])
            })
        
        # Extract structural features
        if "structure" in ast_features:
            properties.update({
                "imports": len(ast_features["structure"].get("import", [])),
                "exports": len(ast_features["structure"].get("export", []))
            })
        
        return properties

    def upsert_doc(self, repo_id: int, file_path: str, content: str) -> None:
        """Upsert documentation node to Neo4j."""
        self.create_doc_node({
            'repo_id': repo_id,
            'file_path': file_path,
            'content': content,
            'type': 'documentation'
        })

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