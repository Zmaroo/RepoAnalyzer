"""[4.2] Code understanding and analysis capabilities.

Flow:
1. Analysis Operations:
   - Codebase analysis
   - Code context retrieval
   - Embedding management

2. Integration Points:
   - GraphSync [6.3]: Graph projections
   - SearchEngine [5.0]: Code search
   - CodeEmbedder [3.1]: Code embeddings

3. Error Handling:
   - ProcessingError: Analysis operations
   - DatabaseError: Storage operations
"""

from typing import Dict, List, Optional, Any
from transformers import AutoTokenizer, AutoModel
import torch
import numpy as np
from utils.logger import log
from db.neo4j_ops import run_query
from db.psql import query
from utils.error_handling import (
    handle_errors,
    handle_async_errors,
    ProcessingError,
    DatabaseError,
    ErrorBoundary,
    AsyncErrorBoundary,
    ErrorSeverity
)
from parsers.models import (
    FileType,
    FileClassification,
)
from parsers.types import (
    ParserResult,
    ExtractedFeatures
)
from config import ParserConfig
from embedding.embedding_models import code_embedder
from db.graph_sync import get_graph_sync
import os
# Remove direct imports from semantic.search - we'll import as needed
# from semantic.search import search_code, search_engine

class CodeUnderstanding:
    """[4.2.1] Code understanding and analysis capabilities."""
    
    def __init__(self):
        with ErrorBoundary("model initialization", error_types=ProcessingError, severity=ErrorSeverity.CRITICAL):
            self.embedder = code_embedder
            
            # Skip the language data path check during initialization
            # We'll check it when the methods that need it are called
            # This helps with testing and avoids initialization errors
            log("CodeUnderstanding initialized", level="info")
    
    @handle_async_errors(error_types=(ProcessingError, DatabaseError))
    async def analyze_codebase(self, repo_id: int) -> Dict[str, Any]:
        """[4.2.2] Analyze codebase structure and relationships."""
        async with AsyncErrorBoundary("codebase analysis", severity=ErrorSeverity.ERROR):
            try:
                # Import locally to avoid circular dependencies
                from semantic.search import search_code
                
                # Query for repository files
                files_query = """
                SELECT file_path, language FROM code_files 
                WHERE repo_id = $1
                """
                files = await query(files_query, [repo_id])
                
                # Get graph sync coordinator
                graph_sync = await get_graph_sync()
                
                # Ensure code projection exists
                await graph_sync.ensure_projection(repo_id)
                
                # Get community structure using Neo4j GDS
                community_query = """
                CALL gds.louvain.stream('code-repo-' || $repo_id)
                YIELD nodeId, communityId
                WITH gds.util.asNode(nodeId) AS node, communityId
                RETURN collect({
                    file_path: node.file_path,
                    community: communityId
                }) AS communities
                """
                communities = await run_query(community_query, {"repo_id": repo_id})
                
                # Get central components using Neo4j GDS
                centrality_query = """
                CALL gds.pageRank.stream('code-repo-' || $repo_id)
                YIELD nodeId, score
                WITH gds.util.asNode(nodeId) AS node, score
                WHERE score > 0.1
                RETURN collect({
                    file_path: node.file_path,
                    centrality: score
                }) AS central_components
                """
                central_components = await run_query(centrality_query, {"repo_id": repo_id})
                
                # Get embeddings
                embeddings_query = """
                    SELECT file_path, embedding 
                    FROM code_snippets 
                    WHERE repo_id = %s AND embedding IS NOT NULL
                """
                code_embeddings = await query(embeddings_query, (repo_id,))
                
                return {
                    "communities": communities[0]["communities"] if communities else [],
                    "central_components": central_components[0]["central_components"] if central_components else [],
                    "embedded_files": len(code_embeddings) if code_embeddings else 0
                }
            except Exception as e:
                raise ProcessingError(f"Error in analyze_codebase: {e}")
    
    @handle_async_errors(error_types=(ProcessingError, DatabaseError))
    async def get_code_context(self, file_path: str, repo_id: int) -> Dict[str, Any]:
        """[4.2.3] Retrieve context for a specific file."""
        async with AsyncErrorBoundary(operation_name="code context retrieval", severity=ErrorSeverity.ERROR):
            # Get file content
            file_query = """
            SELECT file_content FROM code_files 
            WHERE repo_id = $1 AND file_path = $2
            """
            file_result = await query(file_query, [repo_id, file_path])
            
            if not file_result:
                return {"error": f"File not found: {file_path}"}
                
            content = file_result[0]["file_content"]
            
            # Get similar files
            # Import locally to avoid circular dependencies
            from semantic.search import search_code
            similar_files = await search_code(
                content[:1000],  # Just use first 1000 chars as query
                repo_id=repo_id, 
                limit=5
            )
            
            # Get graph-based relationships
            deps_query = """
            MATCH (n:Code {file_path: $file_path, repo_id: $repo_id})-[r]-(m:Code)
            RETURN type(r) as relationship_type,
                   m.file_path as related_file,
                   m.type as component_type
            """
            relationships = await run_query(deps_query, {
                'file_path': file_path,
                'repo_id': repo_id
            })
            
            return {
                "relationships": relationships,
                "similar_files": similar_files
            }
    
    @handle_async_errors(error_types=ProcessingError)
    async def update_embeddings(
        self,
        file_path: str,
        repo_id: int,
        code_content: str
    ) -> None:
        """Update both graph and content embeddings."""
        async with AsyncErrorBoundary("embedding update", severity=ErrorSeverity.ERROR):
            # Update content embedding using GraphCodeBERT
            embedding = await self.embedder.embed_async(code_content)
            update_query = """
                UPDATE code_snippets 
                SET embedding = %s 
                WHERE repo_id = %s AND file_path = %s
            """
            await query(update_query, (embedding.tolist(), repo_id, file_path))
            
            # Update graph projection
            graph_sync = await get_graph_sync()
            await graph_sync.invalidate_projection(repo_id)
            await graph_sync.ensure_projection(repo_id)
    
    @handle_errors(error_types=ProcessingError)
    def cleanup(self) -> None:
        """Clean up resources."""
        pass  # No cleanup needed anymore since we don't hold Neo4jProjections instance

# Do not create global instance until implementation is ready
code_understanding = None 