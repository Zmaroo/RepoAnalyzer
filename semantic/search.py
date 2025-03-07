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
from typing import List, Dict, Optional, Set, Any
import torch
from utils.logger import log, ErrorSeverity
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
    AsyncErrorBoundary
)
from utils.shutdown import register_shutdown_handler
import asyncio

class SearchEngine:
    """[5.1] Handles all search operations combining vector and graph-based search."""
    
    def __init__(self):
        """Private constructor - use create() instead."""
        self._initialized = False
        self._pending_tasks: Set[asyncio.Task] = set()
        self._lock = asyncio.Lock()
        self._graph_sync = None
        self._vector_store = None
        self._search_config = None
        self._cache = None
    
    async def ensure_initialized(self):
        """Ensure the instance is properly initialized before use."""
        if not self._initialized:
            raise ProcessingError("SearchEngine not initialized. Use create() to initialize.")
        if not self._graph_sync:
            raise ProcessingError("Graph sync not initialized")
        if not self._vector_store:
            raise ProcessingError("Vector store not initialized")
        if not self._cache:
            raise ProcessingError("Cache not initialized")
        return True
    
    @classmethod
    async def create(cls, config: Optional[Dict[str, Any]] = None) -> 'SearchEngine':
        """Async factory method to create and initialize a SearchEngine instance."""
        instance = cls()
        try:
            async with AsyncErrorBoundary(
                operation_name="search engine initialization",
                error_types=ProcessingError,
                severity=ErrorSeverity.CRITICAL
            ):
                # Initialize components
                from db.graph_sync import GraphSync
                instance._graph_sync = await GraphSync.create()
                
                from semantic.vector_store import VectorStore
                instance._vector_store = await VectorStore.create()
                
                # Initialize cache
                from utils.cache import UnifiedCache, cache_coordinator
                instance._cache = UnifiedCache("search_results", ttl=3600)
                await cache_coordinator.register_cache("search_results", instance._cache)
                
                # Set search configuration
                instance._search_config = config or {}
                
                # Register shutdown handler
                register_shutdown_handler(instance.cleanup)
                
                # Initialize health monitoring
                from utils.health_monitor import global_health_monitor
                global_health_monitor.register_component("search_engine")
                
                instance._initialized = True
                await log("Search engine initialized", level="info")
                return instance
        except Exception as e:
            await log(f"Error initializing search engine: {e}", level="error")
            # Cleanup on initialization failure
            await instance.cleanup()
            raise ProcessingError(f"Failed to initialize search engine: {e}")
    
    @handle_async_errors(error_types=ProcessingError)
    async def search(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """Perform a search operation."""
        if not self._initialized:
            await self.ensure_initialized()
            
        async with self._lock:
            cache_key = f"search:{hash(query)}:{hash(str(kwargs))}"
            
            # Check cache
            task = asyncio.create_task(self._cache.get_async(cache_key))
            self._pending_tasks.add(task)
            try:
                cached = await task
                if cached is not None:
                    return cached
            finally:
                self._pending_tasks.remove(task)
            
            # Perform search
            vector_task = asyncio.create_task(self._vector_store.search(query, **kwargs))
            graph_task = asyncio.create_task(self._graph_sync.search(query, **kwargs))
            
            self._pending_tasks.update({vector_task, graph_task})
            
            try:
                vector_results, graph_results = await asyncio.gather(vector_task, graph_task)
            finally:
                self._pending_tasks.difference_update({vector_task, graph_task})
            
            # Combine and rank results
            results = await self._combine_results(vector_results, graph_results)
            
            # Cache results
            task = asyncio.create_task(self._cache.set_async(cache_key, results))
            self._pending_tasks.add(task)
            try:
                await task
            finally:
                self._pending_tasks.remove(task)
            
            return results
    
    async def _combine_results(self, vector_results: List[Dict], graph_results: List[Dict]) -> List[Dict]:
        """Combine and rank search results."""
        combined = []
        seen = set()
        
        # Process vector results first (they usually have better relevance)
        for result in vector_results:
            key = (result.get("file"), result.get("line"))
            if key not in seen:
                seen.add(key)
                combined.append(result)
        
        # Add unique graph results
        for result in graph_results:
            key = (result.get("file"), result.get("line"))
            if key not in seen:
                seen.add(key)
                combined.append(result)
        
        return combined
    
    async def cleanup(self):
        """Clean up search engine resources."""
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
            
            # Cleanup components in reverse initialization order
            if self._cache:
                await cache_coordinator.unregister_cache("search_results")
                self._cache = None
            
            if self._vector_store:
                await self._vector_store.cleanup()
            
            if self._graph_sync:
                await self._graph_sync.cleanup()
            
            # Unregister from health monitoring
            from utils.health_monitor import global_health_monitor
            global_health_monitor.unregister_component("search_engine")
            
            self._initialized = False
            await log("Search engine cleaned up", level="info")
        except Exception as e:
            await log(f"Error cleaning up search engine: {e}", level="error")
            raise ProcessingError(f"Failed to cleanup search engine: {e}")

# Global instance
_search_engine = None

# Export with proper async handling
async def get_search_engine(config: Optional[Dict[str, Any]] = None) -> SearchEngine:
    """Get the search engine instance.
    
    Args:
        config: Optional search engine configuration
    
    Returns:
        SearchEngine: The singleton search engine instance
    """
    global _search_engine
    if not _search_engine:
        _search_engine = await SearchEngine.create(config)
    return _search_engine

# Convenience functions for backward compatibility
async def search_code(*args, **kwargs) -> List[Dict]:
    """Search code using vector similarity."""
    engine = await get_search_engine()
    return await engine.search_code(*args, **kwargs)

async def search_docs(*args, **kwargs) -> List[Dict]:
    """Search documentation using vector similarity."""
    engine = await get_search_engine()
    return await engine.search_docs(*args, **kwargs)

async def search_graph(*args, **kwargs) -> List[Dict]:
    """Search using graph analysis."""
    engine = await get_search_engine()
    return await engine.search_graph(*args, **kwargs)

@handle_async_errors(error_types=(ProcessingError, DatabaseError))
async def search_docs_common(query_embedding: torch.Tensor, repo_id: Optional[int] = None, limit: int = 5) -> List[Dict]:
    """Common document search functionality using embeddings."""
    if not _search_engine._initialized:
        await _search_engine.initialize()
        
    async with AsyncErrorBoundary("search_docs_common"):
        vector_literal = _search_engine._to_pgvector(query_embedding.tolist())
        
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
        
        task = asyncio.create_task(query(base_sql, tuple(params)))
        _search_engine._pending_tasks.add(task)
        try:
            return await task
        finally:
            _search_engine._pending_tasks.remove(task)