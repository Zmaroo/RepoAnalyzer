"""[2.0] File processing coordination.

Flow:
1. File Processing:
   - Async file reading with encoding detection
   - Language detection and classification
   - Content parsing and feature extraction
   - Embedding generation
   
2. Storage:
   - Code files: AST, features, and embeddings
   - Doc files: Content and embeddings
   
3. Resource Management:
   - Concurrent operation limits
   - Proper error handling
   - Cache management
   - Request-level caching for improved performance
"""

from typing import Optional, Dict, List, Set, Tuple, Any
from tree_sitter_language_pack import SupportedLanguage
from indexer.file_utils import classify_file, get_relative_path, is_processable_file
from parsers.types import FileType, ParserType
from parsers.language_support import language_registry
from parsers.unified_parser import unified_parser
from parsers.pattern_processor import pattern_processor
from parsers.language_mapping import get_suggested_alternatives
from db.upsert_ops import UpsertCoordinator  # Use UpsertCoordinator for database operations
from db.transaction import transaction_scope
from utils.logger import log
from utils.error_handling import (
    handle_async_errors,
    ProcessingError,
    AsyncErrorBoundary,
    DatabaseError,
    ErrorSeverity
)
import aiofiles
import asyncio
from indexer.common import async_read_file
from embedding.embedding_models import code_embedder, doc_embedder
from utils.request_cache import cached_in_request
from parsers.file_classification import classify_file
from parsers.models import FileClassification
from utils.shutdown import register_shutdown_handler

# Initialize upsert coordinator
_upsert_coordinator = UpsertCoordinator()

class FileProcessor:
    """[2.1] Core file processing coordinator."""
    
    def __init__(self):
        """Private constructor - use create() instead."""
        self._initialized = False
        self._pending_tasks: Set[asyncio.Task] = set()
        self._unified_parser = None
        self._code_embedder = None
        self._doc_embedder = None
        self._upsert_coordinator = None
    
    async def ensure_initialized(self):
        """Ensure the instance is properly initialized before use."""
        if not self._initialized:
            raise ProcessingError("FileProcessor not initialized. Use create() to initialize.")
        return True
    
    @classmethod
    async def create(cls) -> 'FileProcessor':
        """Async factory method to create and initialize a FileProcessor instance."""
        instance = cls()
        try:
            async with AsyncErrorBoundary(
                operation_name="file processor initialization",
                error_types=ProcessingError,
                severity=ErrorSeverity.CRITICAL
            ):
                # Initialize required components
                from parsers.unified_parser import unified_parser
                from embedding.embedding_models import code_embedder, doc_embedder
                from db.upsert_ops import coordinator as upsert_coordinator
                
                # Initialize unified parser
                instance._unified_parser = await unified_parser.ensure_initialized()
                
                # Initialize embedders
                if not code_embedder or not doc_embedder:
                    await init_embedders()
                instance._code_embedder = code_embedder
                instance._doc_embedder = doc_embedder
                
                # Initialize upsert coordinator
                instance._upsert_coordinator = await upsert_coordinator.ensure_initialized()
                
                # Register shutdown handler
                register_shutdown_handler(instance.cleanup)
                
                # Initialize health monitoring
                from utils.health_monitor import global_health_monitor
                global_health_monitor.register_component("file_processor")
                
                instance._initialized = True
                await log("File processor initialized", level="info")
                return instance
        except Exception as e:
            await log(f"Error initializing file processor: {e}", level="error")
            # Cleanup on initialization failure
            await instance.cleanup()
            raise ProcessingError(f"Failed to initialize file processor: {e}")
    
    async def process_file(self, file_path: str, repo_id: int, repo_path: str) -> Optional[Dict]:
        """Process a single file for indexing."""
        if not self._initialized:
            await self.ensure_initialized()
            
        try:
            if not is_processable_file(file_path):
                await log(f"File not processable: {file_path}", level="debug")
                return None
                
            task = asyncio.create_task(self._process_single_file(file_path, repo_id, repo_path))
            self._pending_tasks.add(task)
            task.add_done_callback(lambda t: self._pending_tasks.remove(t) if t in self._pending_tasks else None)
            return await task
        except Exception as e:
            await log(f"Error processing file {file_path}: {e}", level="error")
            raise ProcessingError(f"Failed to process file {file_path}: {e}")
    
    async def cleanup(self):
        """Clean up all resources."""
        try:
            # Cancel all pending tasks
            if self._pending_tasks:
                for task in self._pending_tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                self._pending_tasks.clear()
            
            # Clean up components in reverse initialization order
            if self._upsert_coordinator:
                await self._upsert_coordinator.cleanup()
            if self._code_embedder:
                await self._code_embedder.cleanup()
            if self._doc_embedder:
                await self._doc_embedder.cleanup()
            if self._unified_parser:
                await self._unified_parser.cleanup()
            
            # Unregister from health monitoring
            from utils.health_monitor import global_health_monitor
            global_health_monitor.unregister_component("file_processor")
            
            self._initialized = False
            await log("File processor cleaned up", level="info")
        except Exception as e:
            await log(f"Error cleaning up file processor: {e}", level="error")
            raise ProcessingError(f"Failed to cleanup file processor: {e}")
    
    def clear_cache(self):
        """Clear all caches."""
        # Each parser manages its own cache
        pass

# Global instance
file_processor = None

async def get_file_processor() -> FileProcessor:
    """Get the global file processor instance."""
    global file_processor
    if not file_processor:
        file_processor = await FileProcessor.create()
    return file_processor

# Cache-enabled utility functions

@cached_in_request
async def cached_read_file(file_path: str) -> Optional[str]:
    """Cached version of async_read_file to avoid redundant file I/O."""
    return await async_read_file(file_path)

@cached_in_request
async def cached_classify_file(file_path: str):
    """Cached file classification to avoid redundant classification."""
    return await classify_file(file_path)

@cached_in_request
async def cached_parse_file(rel_path: str, content: str, classification=None):
    """Cached file parsing to avoid redundant parsing operations."""
    from parsers.types import ParserResult
    result = await unified_parser.parse_file(rel_path, content)
    
    # If the result is a dictionary without a 'success' property,
    # transform it into a proper ParserResult
    if isinstance(result, dict):
        if 'success' not in result:
            result = ParserResult(
                success=True,
                ast=result.get('ast', {}),
                features=result.get('features', {}),
                documentation=result.get('documentation', {}),
                complexity=result.get('complexity', {}),
                statistics=result.get('statistics', {})
            )
        else:
            # Convert dict with success to ParserResult
            result = ParserResult(
                success=result.get('success', True),
                ast=result.get('ast', {}),
                features=result.get('features', {}),
                documentation=result.get('documentation', {}),
                complexity=result.get('complexity', {}),
                statistics=result.get('statistics', {})
            )
    return result

@cached_in_request
async def cached_get_patterns(classification):
    """Cached pattern retrieval to avoid redundant pattern loading."""
    return pattern_processor.get_patterns_for_file(classification)

@cached_in_request
async def cached_embed_code(content: str):
    """Cached code embedding to avoid redundant embedding generation."""
    return await code_embedder.embed_async(content)

@cached_in_request
async def cached_embed_doc(content: str):
    """Cached documentation embedding to avoid redundant embedding generation."""
    return await doc_embedder.embed_async(content) 