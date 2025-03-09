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
from parsers.types import (
    FileType,
    ParserResult,
    ExtractedFeatures,
    ParserType
)
from parsers.models import FileClassification
from parsers.language_mapping import normalize_language_name
from tree_sitter_language_pack import get_binding, get_language, get_parser, SupportedLanguage
from utils.error_handling import (
    handle_async_errors,
    handle_errors,
    ProcessingError,
    DatabaseError,
    AsyncErrorBoundary
)
from utils.shutdown import register_shutdown_handler
import asyncio
import os

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
    
    async def _get_language_for_file(self, file_path: str) -> Optional[str]:
        """Get normalized language name for a file."""
        _, ext = os.path.splitext(file_path)
        if not ext:
            return None
            
        try:
            language = normalize_language_name(ext[1:].lower())
            if language in SupportedLanguage.__args__:
                return language
        except:
            pass
        return None
    
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

    @handle_async_errors(error_types=ProcessingError)
    async def search_code(self, query: str, language: Optional[str] = None, **kwargs) -> List[Dict[str, Any]]:
        """Search code using vector similarity."""
        if not self._initialized:
            await self.ensure_initialized()
            
        try:
            # If language is provided, normalize it
            if language:
                language = normalize_language_name(language)
                if language not in SupportedLanguage.__args__:
                    language = None
            
            # Get query embedding
            query_embedding = await code_embedder.embed_code(
                query,
                language or "unknown",
                context={"is_query": True}
            )
            
            # Search vector store
            results = await self._vector_store.search_code(
                query_embedding,
                language=language,
                **kwargs
            )
            
            # Enhance results with tree-sitter parsing
            enhanced_results = []
            for result in results:
                file_path = result.get("file")
                if not file_path:
                    continue
                    
                # Get language for file
                file_language = await self._get_language_for_file(file_path)
                if not file_language:
                    enhanced_results.append(result)
                    continue
                    
                # Get parser for language
                parser = get_parser(file_language)
                if not parser:
                    enhanced_results.append(result)
                    continue
                    
                # Parse snippet
                snippet = result.get("snippet", "")
                if not snippet:
                    enhanced_results.append(result)
                    continue
                    
                tree = parser.parse(bytes(snippet, "utf8"))
                if not tree:
                    enhanced_results.append(result)
                    continue
                    
                # Get unified parser
                unified = await get_unified_parser()
                
                # Extract features
                features = await unified.extract_features(tree, snippet, file_language)
                
                # Add features to result
                result["features"] = features.to_dict()
                enhanced_results.append(result)
            
            return enhanced_results
        except Exception as e:
            await log(f"Error searching code: {e}", level="error")
            return []

    @handle_async_errors(error_types=ProcessingError)
    async def search_docs(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """Search documentation using vector similarity."""
        if not self._initialized:
            await self.ensure_initialized()
            
        try:
            # Get query embedding
            query_embedding = await doc_embedder.embed_text(
                query,
                context={"is_query": True}
            )
            
            # Search vector store
            results = await self._vector_store.search_docs(
                query_embedding,
                **kwargs
            )
            
            # Enhance results with tree-sitter parsing for code blocks
            enhanced_results = []
            for result in results:
                # Extract code blocks from doc content
                code_blocks = self._extract_code_blocks(result.get("content", ""))
                
                # Process each code block
                processed_blocks = []
                for block in code_blocks:
                    language = block.get("language")
                    if not language:
                        processed_blocks.append(block)
                        continue
                        
                    # Normalize language
                    language = normalize_language_name(language)
                    if language not in SupportedLanguage.__args__:
                        processed_blocks.append(block)
                        continue
                        
                    # Get parser for language
                    parser = get_parser(language)
                    if not parser:
                        processed_blocks.append(block)
                        continue
                        
                    # Parse code block
                    tree = parser.parse(bytes(block["content"], "utf8"))
                    if not tree:
                        processed_blocks.append(block)
                        continue
                        
                    # Get unified parser
                    unified = await get_unified_parser()
                    
                    # Extract features
                    features = await unified.extract_features(tree, block["content"], language)
                    
                    # Add features to block
                    block["features"] = features.to_dict()
                    processed_blocks.append(block)
                
                # Add processed blocks to result
                result["code_blocks"] = processed_blocks
                enhanced_results.append(result)
            
            return enhanced_results
        except Exception as e:
            await log(f"Error searching docs: {e}", level="error")
            return []

    def _extract_code_blocks(self, content: str) -> List[Dict[str, Any]]:
        """Extract code blocks from markdown content."""
        import re
        
        code_blocks = []
        pattern = r"```(\w+)?\n(.*?)\n```"
        matches = re.finditer(pattern, content, re.DOTALL)
        
        for match in matches:
            language = match.group(1) or "text"
            code = match.group(2)
            code_blocks.append({
                "language": language,
                "content": code
            })
        
        return code_blocks

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