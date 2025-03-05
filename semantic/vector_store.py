"""[5.2] Vector store for similarity search.

Flow:
1. Search Operations:
   - Code similarity search
   - Documentation similarity search
   - Combined search results

2. Integration Points:
   - PostgreSQL vector operations
   - Embedding models
   - Cache management

3. Error Handling:
   - ProcessingError: Search operations
   - DatabaseError: Storage operations
"""

import asyncio
from typing import List, Dict, Optional, Set, Any
import numpy as np
from utils.logger import log
from utils.cache import UnifiedCache, cache_coordinator
from utils.error_handling import (
    handle_async_errors,
    ProcessingError,
    DatabaseError,
    AsyncErrorBoundary,
    ErrorSeverity
)
from utils.shutdown import register_shutdown_handler
from db.psql import query
from embedding.embedding_models import code_embedder, doc_embedder

class VectorStore:
    """[5.2.1] Vector store implementation using PostgreSQL."""
    
    def __init__(self):
        """Private constructor - use create() instead."""
        self._initialized = False
        self._pending_tasks: Set[asyncio.Task] = set()
        self._lock = asyncio.Lock()
        self._cache = None
        self.code_embedder = None
        self.doc_embedder = None
    
    async def ensure_initialized(self):
        """Ensure the instance is properly initialized before use."""
        if not self._initialized:
            raise ProcessingError("VectorStore not initialized. Use create() to initialize.")
        if not self.code_embedder:
            raise ProcessingError("Code embedder not initialized")
        if not self.doc_embedder:
            raise ProcessingError("Document embedder not initialized")
        if not self._cache:
            raise ProcessingError("Cache not initialized")
        return True
    
    @classmethod
    async def create(cls) -> 'VectorStore':
        """Async factory method to create and initialize a VectorStore instance."""
        instance = cls()
        try:
            async with AsyncErrorBoundary(
                operation_name="vector store initialization",
                error_types=ProcessingError,
                severity=ErrorSeverity.CRITICAL
            ):
                # Initialize embedders
                instance.code_embedder = code_embedder
                instance.doc_embedder = doc_embedder
                
                # Initialize cache
                instance._cache = UnifiedCache("vector_store", ttl=3600)
                await cache_coordinator.register_cache("vector_store", instance._cache)
                
                # Register shutdown handler
                register_shutdown_handler(instance.cleanup)
                
                # Initialize health monitoring
                from utils.health_monitor import global_health_monitor
                global_health_monitor.register_component("vector_store")
                
                instance._initialized = True
                await log("Vector store initialized", level="info")
                return instance
        except Exception as e:
            await log(f"Error initializing vector store: {e}", level="error")
            # Cleanup on initialization failure
            await instance.cleanup()
            raise ProcessingError(f"Failed to initialize vector store: {e}")
    
    def _to_pgvector(self, embedding: List[float]) -> str:
        """Convert embedding to PostgreSQL vector literal."""
        return f"[{','.join(str(x) for x in embedding)}]"
    
    @handle_async_errors(error_types=(ProcessingError, DatabaseError))
    async def search_code(
        self,
        query: str,
        repo_id: Optional[int] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Search code using vector similarity."""
        if not self._initialized:
            await self.ensure_initialized()
            
        async with AsyncErrorBoundary("code search", severity=ErrorSeverity.ERROR):
            # Generate query embedding
            query_embedding = await self.code_embedder.embed_async(query)
            if query_embedding is None:
                return []
            
            # Create cache key
            cache_key = f"code_search:{hash(query)}:{repo_id}:{limit}"
            
            # Check cache
            task = asyncio.create_task(self._cache.get_async(cache_key))
            self._pending_tasks.add(task)
            try:
                cached = await task
                if cached is not None:
                    return cached
            finally:
                self._pending_tasks.remove(task)
            
            # Construct search query
            vector_literal = self._to_pgvector(query_embedding.tolist())
            base_sql = """
            SELECT cs.file_path,
                   cs.ast->>'content' as content,
                   cs.embedding <=> $1::vector AS similarity
            FROM code_snippets cs
            """
            params = [vector_literal]
            
            if repo_id is not None:
                base_sql += " WHERE cs.repo_id = $2"
                params.append(repo_id)
            
            base_sql += " ORDER BY similarity ASC LIMIT $3"
            params.append(limit)
            
            # Execute search
            task = asyncio.create_task(query(base_sql, tuple(params)))
            self._pending_tasks.add(task)
            try:
                results = await task
            finally:
                self._pending_tasks.remove(task)
            
            # Cache results
            task = asyncio.create_task(self._cache.set_async(cache_key, results))
            self._pending_tasks.add(task)
            try:
                await task
            finally:
                self._pending_tasks.remove(task)
            
            return results
    
    @handle_async_errors(error_types=(ProcessingError, DatabaseError))
    async def search_docs(
        self,
        query: str,
        repo_id: Optional[int] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Search documentation using vector similarity."""
        if not self._initialized:
            await self.ensure_initialized()
            
        async with AsyncErrorBoundary("doc search", severity=ErrorSeverity.ERROR):
            # Generate query embedding
            query_embedding = await self.doc_embedder.embed_async(query)
            if query_embedding is None:
                return []
            
            # Create cache key
            cache_key = f"doc_search:{hash(query)}:{repo_id}:{limit}"
            
            # Check cache
            task = asyncio.create_task(self._cache.get_async(cache_key))
            self._pending_tasks.add(task)
            try:
                cached = await task
                if cached is not None:
                    return cached
            finally:
                self._pending_tasks.remove(task)
            
            # Construct search query
            vector_literal = self._to_pgvector(query_embedding.tolist())
            base_sql = """
            SELECT rd.file_path,
                   rd.content,
                   rd.doc_type,
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
            
            base_sql += " ORDER BY similarity ASC LIMIT $3"
            params.append(limit)
            
            # Execute search
            task = asyncio.create_task(query(base_sql, tuple(params)))
            self._pending_tasks.add(task)
            try:
                results = await task
            finally:
                self._pending_tasks.remove(task)
            
            # Cache results
            task = asyncio.create_task(self._cache.set_async(cache_key, results))
            self._pending_tasks.add(task)
            try:
                await task
            finally:
                self._pending_tasks.remove(task)
            
            return results
    
    @handle_async_errors(error_types=(ProcessingError, DatabaseError))
    async def search(
        self,
        query: str,
        search_type: str = "all",
        repo_id: Optional[int] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Combined search across code and documentation."""
        if not self._initialized:
            await self.ensure_initialized()
            
        async with AsyncErrorBoundary("combined search", severity=ErrorSeverity.ERROR):
            tasks = []
            
            if search_type in ["all", "code"]:
                task = asyncio.create_task(self.search_code(query, repo_id, limit))
                self._pending_tasks.add(task)
                tasks.append(("code", task))
            
            if search_type in ["all", "docs"]:
                task = asyncio.create_task(self.search_docs(query, repo_id, limit))
                self._pending_tasks.add(task)
                tasks.append(("docs", task))
            
            results = []
            try:
                for search_type, task in tasks:
                    try:
                        search_results = await task
                        for result in search_results:
                            result["type"] = search_type
                        results.extend(search_results)
                    except Exception as e:
                        await log(f"Error in {search_type} search: {e}", level="error")
            finally:
                for _, task in tasks:
                    self._pending_tasks.remove(task)
            
            # Sort combined results by similarity
            results.sort(key=lambda x: x["similarity"])
            return results[:limit]
    
    async def cleanup(self):
        """Clean up vector store resources."""
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
            
            # Clean up cache
            if self._cache:
                await cache_coordinator.unregister_cache("vector_store")
                self._cache = None
            
            # Unregister from health monitoring
            from utils.health_monitor import global_health_monitor
            global_health_monitor.unregister_component("vector_store")
            
            self._initialized = False
            await log("Vector store cleaned up", level="info")
        except Exception as e:
            await log(f"Error cleaning up vector store: {e}", level="error")
            raise ProcessingError(f"Failed to cleanup vector store: {e}")

# Global instance
_vector_store = None

async def get_vector_store() -> VectorStore:
    """Get the vector store instance."""
    global _vector_store
    if not _vector_store:
        _vector_store = await VectorStore.create()
    return _vector_store 