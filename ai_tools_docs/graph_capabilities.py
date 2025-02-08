"""
Neo4j Graph Analysis Capabilities

This module documents the available graph analysis tools and capabilities
that can be used to analyze code repositories.

Available Methods:
1. analyze_code_structure(repo_id: int) -> Dict[str, Any]
   - Performs comprehensive code structure analysis
   - Returns communities, central components, complexity metrics, and dependency stats

2. find_similar_code(file_path: str, repo_id: int, limit: int = 5) -> List[Dict]
   - Finds similar code components using node2vec embeddings
   - Returns list of similar components with similarity scores

3. trace_code_flow(entry_point: str, repo_id: int) -> List[Dict]
   - Traces code flow from an entry point
   - Returns list of code paths and relationships

4. get_code_metrics(repo_id: int) -> Dict[str, Any]
   - Gets comprehensive code metrics
   - Returns dictionary of various code metrics

Example Usage:

from ai_tools.graph_capabilities import GraphAnalysisCapabilities

# Initialize capabilities
graph_analysis = GraphAnalysisCapabilities()

try:
    # Analyze code structure
    structure = graph_analysis.analyze_code_structure(repo_id=1)
    
    # Find similar code
    similar = graph_analysis.find_similar_code(
        file_path="path/to/file.py",
        repo_id=1,
        limit=5
    )
    
    # Get code metrics
    metrics = graph_analysis.get_code_metrics(repo_id=1)
    
finally:
    # Always close connections
    graph_analysis.close()

Graph Schema:
- Nodes:
  - Label: Code
  - Properties:
    - file_path: str
    - repo_id: int
    - language: str
    - type: str (function, class, method, etc.)
    - name: str
    - ast_data: json
    - complexity: int
    - lines_of_code: int
    - documentation: str
    - embedding: list[float]

- Relationships:
  - CALLS: Function calls between components
  - IMPORTS: Import relationships
  - CONTAINS: Nested component relationships
  - DEPENDS_ON: General dependencies
"""

# This file is purely for documentation purposes
# The actual implementation is in ai_tools/graph_capabilities.py