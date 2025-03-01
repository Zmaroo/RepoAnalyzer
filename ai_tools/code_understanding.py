"""[4.2] Code understanding and analysis capabilities.

Flow:
1. Analysis Operations:
   - Codebase analysis
   - Code context retrieval
   - Embedding management

2. Integration Points:
   - Neo4jProjections [6.2]: Graph operations
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
from db.neo4j_ops import Neo4jProjections
from utils.error_handling import handle_errors, handle_async_errors, ProcessingError, DatabaseError, ErrorBoundary, AsyncErrorBoundary
from parsers.models import FileType, FileClassification
from parsers.types import ParserResult, ExtractedFeatures
from config import ParserConfig
from embedding.embedding_models import code_embedder
import os
import asyncio


class CodeUnderstanding:
    """[4.2.1] Code understanding and analysis capabilities."""

    def __init__(self):
        with ErrorBoundary(error_types=ProcessingError, operation_name=
            'model initialization'):
            self.graph_projections = Neo4jProjections()
            self.embedder = code_embedder
            log('CodeUnderstanding initialized', level='info')

    @handle_async_errors(error_types=(ProcessingError, DatabaseError))
    async def analyze_codebase(self, repo_id: int) ->Dict[str, Any]:
        """[4.2.2] Analyze codebase structure and relationships."""
        async with AsyncErrorBoundary(operation_name='codebase analysis'):
            try:
                from semantic.search import search_code
                files_query = """
                SELECT file_path, language FROM code_files 
                WHERE repo_id = $1
                """
                files = await query(files_query, [repo_id])
                graph_name = f'code-repo-{repo_id}'
                await self.graph_projections.create_code_dependency_projection(
                    graph_name)
                communities = (await self.graph_projections.
                    run_community_detection(graph_name))
                central_components = (await self.graph_projections.
                    run_centrality_analysis(graph_name))
                embeddings_query = """
                    SELECT file_path, embedding 
                    FROM code_snippets 
                    WHERE repo_id = %s AND embedding IS NOT NULL
                """
                code_embeddings = await query(embeddings_query, (repo_id,))
                return {'communities': communities, 'central_components':
                    central_components, 'embedded_files': len(
                    code_embeddings) if code_embeddings else 0}
            except Exception as e:
                raise ProcessingError(f'Error in analyze_codebase: {e}')

    @handle_async_errors(error_types=(ProcessingError, DatabaseError))
    async def get_code_context(self, file_path: str, repo_id: int) ->Dict[
        str, Any]:
        """[4.2.3] Retrieve context for a specific file."""
        async with AsyncErrorBoundary(operation_name='code context retrieval'):
            file_query = """
            SELECT file_content FROM code_files 
            WHERE repo_id = $1 AND file_path = $2
            """
            file_result = await query(file_query, [repo_id, file_path])
            if not file_result:
                return {'error': f'File not found: {file_path}'}
            content = file_result[0]['file_content']
            from semantic.search import search_code
            similar_files = await search_code(content[:1000], repo_id=
                repo_id, limit=5)
            deps_query = """
            MATCH (n:Code {file_path: $file_path, repo_id: $repo_id})-[r]-(m:Code)
            RETURN type(r) as relationship_type,
                   m.file_path as related_file,
                   m.type as component_type
            """
            relationships = await run_query(deps_query, {'file_path':
                file_path, 'repo_id': repo_id})
            return {'relationships': relationships, 'similar_files':
                similar_files}

    @handle_async_errors(error_types=ProcessingError)
    async def update_embeddings(self, file_path: str, repo_id: int,
        code_content: str) ->None:
        """Update both graph and content embeddings."""
        async with AsyncErrorBoundary(operation_name='embedding update'):
            embedding = await self.embedder.embed_async(code_content)
            update_query = """
                UPDATE code_snippets 
                SET embedding = %s 
                WHERE repo_id = %s AND file_path = %s
            """
            await query(update_query, (embedding.tolist(), repo_id, file_path))
            graph_name = f'code-repo-{repo_id}'
            await self.graph_projections.create_code_dependency_projection(
                graph_name)

    @handle_errors(error_types=ProcessingError)
    def cleanup(self) ->None:
        """Clean up resources."""
        with ErrorBoundary(operation_name='model cleanup'):
            try:
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                if loop.is_running():
                    asyncio.create_task(self.graph_projections.close())
                    log('Graph projections cleanup scheduled', level='info')
                else:
                    loop.run_until_complete(self.graph_projections.close())
            except Exception as e:
                log(f'Error closing graph projections: {e}', level='error')


code_understanding = CodeUnderstanding()
