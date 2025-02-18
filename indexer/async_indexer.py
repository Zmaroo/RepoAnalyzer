import os
from indexer.file_config import CODE_EXTENSIONS, DOC_EXTENSIONS
from indexer.common_indexer import async_index_files, index_file_async
from async_utils import async_get_files, async_process_index_file
from file_utils import read_text_file
from utils.logger import log
from parsers.file_parser import process_file
from db.neo4j_tools import Neo4jTools, upsert_doc
from db.neo4j_projections import Neo4jProjections
from typing import Dict, Any
import asyncio
from parsers.language_mapping import FileType, get_file_classification
from parsers.file_parser import FileProcessor

async def async_index_repository(repo_path: str, repo_id: int) -> None:
    """Enhanced active project indexing with improved error handling."""
    log(f"Starting active project indexing [{repo_id}] at: {repo_path}")
    
    neo4j = Neo4jTools()
    try:
        # Get files by FileType
        code_files = await async_get_files(repo_path, {FileType.CODE})
        doc_files = await async_get_files(repo_path, {FileType.DOC})
        
        total_files = len(code_files) + len(doc_files)
        processed_files = 0
        
        # Process code files
        processor = FileProcessor()
        for batch in [code_files[i:i+10] for i in range(0, len(code_files), 10)]:
            tasks = []
            for file_path in batch:
                tasks.append(async_process_index_file(
                    file_path=file_path,
                    base_path=repo_path,
                    repo_id=repo_id,
                    file_processor=processor.process_file,
                    index_function=neo4j.upsert_code_node,
                    file_type="active_code"
                ))
            await asyncio.gather(*tasks, return_exceptions=True)
            processed_files += len(batch)
            log(f"Progress: {processed_files}/{total_files} files processed")
            
        # Process documentation files similarly
        doc_batches = [doc_files[i:i+10] for i in range(0, len(doc_files), 10)]
        for batch in doc_batches:
            tasks = []
            for file_path in batch:
                tasks.append(async_process_index_file(
                    file_path=file_path,
                    base_path=repo_path,
                    repo_id=repo_id,
                    file_processor=read_text_file,
                    index_function=upsert_doc,
                    file_type="doc"
                ))
            await asyncio.gather(*tasks, return_exceptions=True)
            processed_files += len(batch)
            log(f"Progress: {processed_files}/{total_files} files processed")

        # Run graph analysis after indexing
        graph_name = f"repo_{repo_id}_graph"
        projections = Neo4jProjections()
        
        try:
            projections.create_code_dependency_projection(graph_name)
            log(f"Created graph projection for repository {repo_id}")
            
            communities = projections.run_community_detection(graph_name)
            if communities:
                log(f"Identified {len(set(c['community'] for c in communities))} code communities")
            
            central_components = projections.run_centrality_analysis(graph_name)
            if central_components:
                log(f"Identified {len(central_components)} central code components")
                
        except Exception as e:
            log(f"Graph analysis failed: {e}", level="error")
            
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