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

from typing import Dict, List, Optional, Any, Set
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
    AsyncErrorBoundary,
    ErrorSeverity
)
from utils.shutdown import register_shutdown_handler
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
from ai_tools.graph_capabilities import GraphAnalysis
import os
import asyncio
# Remove direct imports from semantic.search - we'll import as needed
# from semantic.search import search_code, search_engine

class CodeUnderstanding:
    """[4.2.1] Code understanding and analysis capabilities."""
    
    def __init__(self):
        """Private constructor - use create() instead."""
        self.graph_analysis = None
        self.code_embedder = None
        self._pending_tasks: Set[asyncio.Task] = set()
        self._initialized = False
        self._lock = asyncio.Lock()
    
    async def ensure_initialized(self):
        """Ensure the instance is properly initialized before use."""
        if not self._initialized:
            raise ProcessingError("CodeUnderstanding instance not initialized. Use create() to initialize.")
        if not self.graph_analysis:
            raise ProcessingError("Graph analysis not initialized")
        if not self.code_embedder:
            raise ProcessingError("Code embedder not initialized")
        return True

    @classmethod
    async def create(cls) -> 'CodeUnderstanding':
        """Async factory method to create and initialize a CodeUnderstanding instance."""
        instance = cls()
        try:
            async with AsyncErrorBoundary(
                operation_name="code understanding initialization",
                error_types=ProcessingError,
                severity=ErrorSeverity.CRITICAL
            ):
                # Initialize required components
                instance.graph_analysis = await GraphAnalysis.create()
                instance.code_embedder = code_embedder
                
                # Register shutdown handler
                register_shutdown_handler(instance.cleanup)
                
                # Initialize health monitoring
                from utils.health_monitor import global_health_monitor
                global_health_monitor.register_component("code_understanding")
                
                instance._initialized = True
                await log("Code understanding initialized", level="info")
                return instance
        except Exception as e:
            await log(f"Error initializing code understanding: {e}", level="error")
            # Cleanup on initialization failure
            await instance.cleanup()
            raise ProcessingError(f"Failed to initialize code understanding: {e}")
    
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
                task = asyncio.create_task(query(files_query, [repo_id]))
                self._pending_tasks.add(task)
                try:
                    files = await task
                finally:
                    self._pending_tasks.remove(task)
                
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
                task = asyncio.create_task(run_query(community_query, {"repo_id": repo_id}))
                self._pending_tasks.add(task)
                try:
                    communities = await task
                finally:
                    self._pending_tasks.remove(task)
                
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
                task = asyncio.create_task(run_query(centrality_query, {"repo_id": repo_id}))
                self._pending_tasks.add(task)
                try:
                    central_components = await task
                finally:
                    self._pending_tasks.remove(task)
                
                # Get embeddings
                embeddings_query = """
                    SELECT file_path, embedding 
                    FROM code_snippets 
                    WHERE repo_id = %s AND embedding IS NOT NULL
                """
                task = asyncio.create_task(query(embeddings_query, (repo_id,)))
                self._pending_tasks.add(task)
                try:
                    code_embeddings = await task
                finally:
                    self._pending_tasks.remove(task)
                
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
            embedding = await self.code_embedder.embed_async(code_content)
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
    
    async def cleanup(self):
        """Clean up code understanding resources."""
        try:
            if not self._initialized:
                return
                
            # Cancel all pending tasks
            if self._pending_tasks:
                for task in self._pending_tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                self._pending_tasks.clear()
            
            # Clean up graph analysis
            if self.graph_analysis:
                await self.graph_analysis.cleanup()
            
            # Unregister from health monitoring
            from utils.health_monitor import global_health_monitor
            global_health_monitor.unregister_component("code_understanding")
            
            self._initialized = False
            await log("Code understanding cleaned up", level="info")
        except Exception as e:
            await log(f"Error cleaning up code understanding: {e}", level="error")
            raise ProcessingError(f"Failed to cleanup code understanding: {e}")

# Do not create global instance until implementation is ready
code_understanding = None 