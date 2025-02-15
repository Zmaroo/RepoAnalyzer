import os
from indexer.file_config import CODE_EXTENSIONS, DOC_EXTENSIONS
from indexer.common_indexer import async_index_files, index_file_async
from utils.logger import log
from parsers.file_parser import process_file
from db.neo4j_tools import Neo4jTools
from db.neo4j_projections import Neo4jProjections
from typing import Dict, Any
import asyncio

async def async_index_repository(repo_path: str, repo_id: int) -> None:
    """Enhanced repository indexing with Neo4j graph projections and analysis."""
    log(f"Indexing repository [{repo_id}] at: {repo_path}")
    
    # Initialize Neo4j tools and projections
    neo4j = Neo4jTools()
    projections = Neo4jProjections()
    
    try:
        # Process and index code files using the unified async_index_files from common_indexer.
        await async_index_files(
            repo_path, 
            repo_id, 
            CODE_EXTENSIONS,
            process_file,
            lambda file_path, content: index_code_file(neo4j, repo_id, file_path, content),
            "code",
            wrap_sync=True
        )
        
        # Create code dependency projection
        graph_name = f"code_dep_{repo_id}"
        projection_result = projections.create_code_dependency_projection(graph_name)
        
        if projection_result:
            log(f"Created graph projection with {projection_result.get('nodes', 0)} nodes and "
                f"{projection_result.get('rels', 0)} relationships")
            
            # Run community detection
            communities = projections.run_community_detection(graph_name)
            if communities:
                log(f"Identified {len(set(c['community'] for c in communities))} code communities")
            
            # Run centrality analysis
            central_components = projections.run_centrality_analysis(graph_name)
            if central_components:
                log(f"Identified {len(central_components)} central code components")
                
    finally:
        neo4j.close()

def index_code_file(neo4j: Neo4jTools, repo_id: int, file_path: str, content: Dict[str, Any]) -> None:
    """Index a code file in Neo4j with enhanced metadata."""
    node_props = {
        'file_path': file_path,
        'repo_id': repo_id,
        'language': content['language'],
        'type': 'file',  # Base type – can be enhanced with AST analysis.
        'name': os.path.basename(file_path),
        'ast_data': content['ast_data'],
        'complexity': content['complexity'],
        'lines_of_code': content['lines_of_code'],
        'documentation': content['documentation']
    }
    
    neo4j.create_code_node(node_props)
    
    # TODO: Analyze imports and create relationships
    # This would involve parsing the AST to find import statements
    # and creating appropriate relationships

# Asynchronously index documentation files (using an async file reader)
async def async_index_files(repo_path: str, repo_id: int, extensions: list, async_read_file, upsert_doc, doc_type: str) -> None:
    # Implementation of async_index_files function
    pass 

async def async_index_code(repo_id: int, base_path: str):
    """
    Asynchronously indexes code files in the repository.
    
    This function:
      - Uses the common indexing logic to process files that have extensions in CODE_EXTENSIONS.
      - Ensures that all code indexing is handled asynchronously.
    """
    # Example: iterate over files and index them asynchronously.
    # (Replace the placeholder logic below with real file discovery & indexing.)
    code_files = []  # Assume we have code to list files filtering by CODE_EXTENSIONS.
    for file_path in code_files:
        await index_file_async(file_path, repo_id, base_path)
    return

async def async_index_docs(repo_id: int, base_path: str):
    """
    Asynchronously indexes documentation files in the repository.
    
    This function:
      - Filters files against DOC_EXTENSIONS.
      - Uses the same common indexing logic but names this function distinctly
        (e.g., async_index_docs) to avoid duplicating symbols like async_index_files.
    """
    doc_files = []  # Replace with actual logic to list files filtering by DOC_EXTENSIONS.
    for file_path in doc_files:
        await index_file_async(file_path, repo_id, base_path)
    return 