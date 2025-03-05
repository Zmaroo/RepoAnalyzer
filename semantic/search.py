"""[5.0] Unified search functionality using embeddings and vector search.

Flow:
1. Search Capabilities:
   - Code search with vector similarity
   - Doc search with vector similarity
   - Graph-enhanced results
   
2. Integration Points:
   - Uses embeddings stored by FileProcessor
   - Uses graph analysis for enhanced results
   - Provides backward compatibility APIs

3. Search Pipeline:
   - Query embedding generation
   - Vector similarity search
   - Result enhancement and ranking
"""

from db.psql import query
from typing import List, Dict, Optional, Set
import torch
from utils.logger import log
from utils.cache import cache_coordinator
from embedding.embedding_models import code_embedder, doc_embedder
from ai_tools.graph_capabilities import graph_analysis
from parsers.models import (
    FileType,
    FileClassification
)
from parsers.types import ParserResult, ExtractedFeatures
from utils.error_handling import (
    handle_async_errors,
    handle_errors,
    ProcessingError,
    DatabaseError,
    AsyncErrorBoundary,
    ErrorBoundary
)
from utils.async_runner import submit_async_task
from utils.app_init import register_shutdown_handler
import asyncio

class SearchEngine:
    """[5.1] Handles all search operations combining vector and graph-based search."""
    
    def __init__(self):
        self.code_embedder = code_embedder
        self.doc_embedder = doc_embedder
        self._initialized = False
        self._pending_tasks: Set[asyncio.Future] = set()
        register_shutdown_handler(self.cleanup)
    
    @handle_async_errors(error_types=(Exception,))
    async def initialize(self):
        """Initialize search engine resources."""
        if not self._initialized:
            try:
                async with AsyncErrorBoundary("search_engine_initialization"):
                    # Initialize embedders
                    future = submit_async_task(self.code_embedder.initialize())
                    self._pending_tasks.add(future)
                    try:
                        await asyncio.wrap_future(future)
                    finally:
                        self._pending_tasks.remove(future)
                    
                    future = submit_async_task(self.doc_embedder.initialize())
                    self._pending_tasks.add(future)
                    try:
                        await asyncio.wrap_future(future)
                    finally:
                        self._pending_tasks.remove(future)
                    
                    self._initialized = True
                    log("Search engine initialized", level="info")
            except Exception as e:
                log(f"Error initializing search engine: {e}", level="error")
                raise
    
    @handle_async_errors(error_types=(ProcessingError, DatabaseError))
    async def search_code(
        self,
        query_text: str,
        repo_id: Optional[int] = None,
        limit: int = 5,
        include_similar: bool = True
    ) -> List[Dict]:
        """Search code using vector similarity."""
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary("search_code"):
            # Get query embedding
            future = submit_async_task(self.code_embedder.embed_async(query_text))
            self._pending_tasks.add(future)
            try:
                query_embedding = await asyncio.wrap_future(future)
            finally:
                self._pending_tasks.remove(future)
                
            vector_literal = self._to_pgvector(query_embedding.tolist())
            base_sql = """
            SELECT cs.id, cs.repo_id, cs.file_path, cs.ast,
                   cs.embedding <=> $1::vector AS similarity
            FROM code_snippets cs
            """
            params = [vector_literal]
            if repo_id is not None:
                base_sql += " WHERE cs.repo_id = $2"
                params.append(repo_id)
            base_sql += " ORDER BY similarity ASC LIMIT $3;"
            params.append(limit)
            
            # Execute query
            future = submit_async_task(query(base_sql, tuple(params)))
            self._pending_tasks.add(future)
            try:
                vector_results = await asyncio.wrap_future(future)
            finally:
                self._pending_tasks.remove(future)
            
            if not include_similar or not vector_results:
                return vector_results
            
            # Enhance results with similar components and metrics
            enhancement_tasks = []
            for result in vector_results:
                future = submit_async_task(self._enhance_result(result))
                self._pending_tasks.add(future)
                enhancement_tasks.append(future)
            
            try:
                enhanced_results = await asyncio.gather(*[
                    asyncio.wrap_future(f) for f in enhancement_tasks
                ])
            finally:
                for task in enhancement_tasks:
                    self._pending_tasks.remove(task)
            
            return enhanced_results
    
    async def _enhance_result(self, result: Dict) -> Dict:
        """Enhance a search result with similar components and metrics."""
        async with AsyncErrorBoundary("enhance_result"):
            # Find similar components
            future = submit_async_task(
                graph_analysis.find_similar_components(
                    file_path=result['file_path'],
                    repo_id=result['repo_id'],
                    similarity_cutoff=0.8
                )
            )
            self._pending_tasks.add(future)
            try:
                similar_components = await asyncio.wrap_future(future)
            finally:
                self._pending_tasks.remove(future)
            
            # Get code metrics
            future = submit_async_task(
                graph_analysis.get_code_metrics(
                    repo_id=result['repo_id'],
                    file_path=result['file_path']
                )
            )
            self._pending_tasks.add(future)
            try:
                code_metrics = await asyncio.wrap_future(future)
            finally:
                self._pending_tasks.remove(future)
            
            result['similar_components'] = similar_components
            result['code_metrics'] = code_metrics
            return result
    
    @handle_async_errors(error_types=(ProcessingError, DatabaseError))
    async def search_docs(
        self,
        query_text: str,
        repo_id: Optional[int] = None,
        limit: int = 5
    ) -> List[Dict]:
        """Search documentation using vector similarity."""
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary("search_docs"):
            # Get query embedding
            future = submit_async_task(self.doc_embedder.embed_async(query_text))
            self._pending_tasks.add(future)
            try:
                query_embedding = await asyncio.wrap_future(future)
            finally:
                self._pending_tasks.remove(future)
                
            vector_literal = self._to_pgvector(query_embedding.tolist())
            base_sql = """
            SELECT rd.id, rd.file_path, rd.content, rd.doc_type,
                   rd.embedding <=> $1::vector AS similarity
            FROM repo_docs rd
            """
            params = [vector_literal]
            if repo_id is not None:
                base_sql += " WHERE rd.repo_id = $2"
                params.append(repo_id)
            base_sql += " ORDER BY similarity ASC LIMIT $3;"
            params.append(limit)
            
            # Execute query
            future = submit_async_task(query(base_sql, tuple(params)))
            self._pending_tasks.add(future)
            try:
                return await asyncio.wrap_future(future)
            finally:
                self._pending_tasks.remove(future)
    
    @handle_async_errors(error_types=(ProcessingError, DatabaseError))
    async def get_repo_docs(self, repo_id: int) -> List[Dict]:
        """Get all documents for a repository."""
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary("get_repo_docs"):
            sql = """
            SELECT rd.* FROM repo_docs rd
            JOIN repo_doc_relations rdr ON rd.id = rdr.doc_id
            WHERE rdr.repo_id = %s
            """
            future = submit_async_task(query(sql, (repo_id,)))
            self._pending_tasks.add(future)
            try:
                return await asyncio.wrap_future(future)
            finally:
                self._pending_tasks.remove(future)
    
    @handle_async_errors(error_types=(ProcessingError, DatabaseError))
    async def create_doc_cluster(
        self,
        docs: List[Dict],
        cluster_name: str
    ) -> Dict:
        """Create a document cluster."""
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary("create_doc_cluster"):
            sql = """
            INSERT INTO doc_clusters (name, docs)
            VALUES (%s, %s)
            RETURNING id
            """
            future = submit_async_task(query(sql, (cluster_name, docs)))
            self._pending_tasks.add(future)
            try:
                result = await asyncio.wrap_future(future)
                return {"id": result[0]["id"], "name": cluster_name}
            finally:
                self._pending_tasks.remove(future)
    
    @handle_async_errors(error_types=(ProcessingError, DatabaseError))
    async def update_doc_version(
        self,
        doc_id: int,
        new_content: str
    ) -> Dict:
        """Update document version."""
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary("update_doc_version"):
            sql = """
            UPDATE repo_docs
            SET content = %s,
                updated_at = NOW()
            WHERE id = %s
            RETURNING id, file_path, content
            """
            future = submit_async_task(query(sql, (new_content, doc_id)))
            self._pending_tasks.add(future)
            try:
                return await asyncio.wrap_future(future)
            finally:
                self._pending_tasks.remove(future)
    
    @handle_async_errors(error_types=(ProcessingError, DatabaseError))
    async def search_patterns(
        self,
        query_text: str,
        repo_id: Optional[int] = None,
        pattern_type: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict]:
        """Search for learned patterns matching the query."""
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary("search_patterns"):
            # Get query embedding
            future = submit_async_task(self.code_embedder.embed_async(query_text))
            self._pending_tasks.add(future)
            try:
                query_embedding = await asyncio.wrap_future(future)
            finally:
                self._pending_tasks.remove(future)
                
            vector_literal = self._to_pgvector(query_embedding.tolist())
            
            base_sql = """
            SELECT cp.id, cp.pattern_type, cp.content, cp.confidence,
                   cp.repo_id, cp.language, cp.example_usage,
                   cp.embedding <=> $1::vector AS similarity
            FROM code_patterns cp
            """
            params = [vector_literal]
            conditions = []
            
            if repo_id is not None:
                conditions.append("cp.repo_id = $2")
                params.append(repo_id)
            
            if pattern_type is not None:
                conditions.append(f"cp.pattern_type = ${len(params) + 1}")
                params.append(pattern_type)
            
            if conditions:
                base_sql += " WHERE " + " AND ".join(conditions)
            
            base_sql += " ORDER BY similarity ASC LIMIT $" + str(len(params) + 1)
            params.append(limit)
            
            # Execute query
            future = submit_async_task(query(base_sql, tuple(params)))
            self._pending_tasks.add(future)
            try:
                return await asyncio.wrap_future(future)
            finally:
                self._pending_tasks.remove(future)
    
    @handle_async_errors(error_types=(ProcessingError, DatabaseError))
    async def get_repository_patterns(
        self,
        repo_id: int,
        pattern_type: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """Get patterns from a specific reference repository."""
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary("get_repository_patterns"):
            sql = """
            SELECT cp.id, cp.pattern_type, cp.content, cp.confidence,
                   cp.language, cp.example_usage
            FROM code_patterns cp
            WHERE cp.repo_id = $1
            """
            params = [repo_id]
            
            if pattern_type is not None:
                sql += " AND cp.pattern_type = $2"
                params.append(pattern_type)
            
            sql += " ORDER BY cp.confidence DESC LIMIT $" + str(len(params) + 1)
            params.append(limit)
            
            # Execute query
            future = submit_async_task(query(sql, tuple(params)))
            self._pending_tasks.add(future)
            try:
                return await asyncio.wrap_future(future)
            finally:
                self._pending_tasks.remove(future)
    
    def _to_pgvector(self, embedding: list) -> str:
        """Convert list to PostgreSQL vector literal."""
        return " ".join(map(str, embedding))
    
    async def cleanup(self):
        """Clean up search engine resources."""
        try:
            # Cancel and clean up any pending tasks
            if self._pending_tasks:
                for task in self._pending_tasks:
                    task.cancel()
                await asyncio.gather(*[asyncio.wrap_future(f) for f in self._pending_tasks], return_exceptions=True)
                self._pending_tasks.clear()
            
            self._initialized = False
            log("Search engine cleaned up", level="info")
        except Exception as e:
            log(f"Error cleaning up search engine: {e}", level="error")

# Global instance
search_engine = SearchEngine()

# Register cleanup handler
register_shutdown_handler(search_engine.cleanup)

# Convenience functions for backward compatibility
async def search_code(*args, **kwargs) -> List[Dict]:
    return await search_engine.search_code(*args, **kwargs)

async def search_docs(*args, **kwargs) -> List[Dict]:
    return await search_engine.search_docs(*args, **kwargs)

@handle_async_errors(error_types=(ProcessingError, DatabaseError))
async def search_docs_common(query_embedding: torch.Tensor, repo_id: Optional[int] = None, limit: int = 5) -> List[Dict]:
    """Common document search functionality using embeddings."""
    if not search_engine._initialized:
        await search_engine.initialize()
        
    async with AsyncErrorBoundary("search_docs_common"):
        vector_literal = search_engine._to_pgvector(query_embedding.tolist())
        
        base_sql = """
        SELECT rd.id, rd.file_path, rd.content, rd.doc_type,
               rd.embedding <=> $1::vector AS similarity
        FROM repo_docs rd
        """
        params = [vector_literal]
        if repo_id is not None:
            base_sql += """
            JOIN repo_doc_relations rdr ON rd.id = rdr.doc_id
            WHERE rdr.repo_id = $2
            """
            params.append(repo_id)
        base_sql += " ORDER BY similarity ASC LIMIT $3;"
        params.append(limit)
        
        future = submit_async_task(query(base_sql, tuple(params)))
        search_engine._pending_tasks.add(future)
        try:
            return await asyncio.wrap_future(future)
        finally:
            search_engine._pending_tasks.remove(future)