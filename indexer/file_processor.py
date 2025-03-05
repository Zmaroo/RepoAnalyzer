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
from indexer.file_utils import get_file_classification
from parsers.types import FileType, ParserType
from parsers.language_support import language_registry
from parsers.unified_parser import unified_parser
from parsers.pattern_processor import pattern_processor
from parsers.language_mapping import get_suggested_alternatives
from db.upsert_ops import upsert_code_snippet, upsert_doc
from db.transaction import transaction_scope
from indexer.file_utils import get_relative_path, is_processable_file
from utils.logger import log
from utils.error_handling import (
    handle_async_errors,
    ProcessingError,
    AsyncErrorBoundary,
    DatabaseError,
    ErrorSeverity
)
import aiofiles
from utils.async_runner import get_loop, submit_async_task, cleanup_tasks
from indexer.common import async_read_file
import asyncio
from embedding.embedding_models import code_embedder, doc_embedder
from utils.request_cache import cached_in_request
from parsers.file_classification import classify_file
from parsers.models import FileClassification
from utils.app_init import register_shutdown_handler

class FileProcessor:
    """[2.1] Coordinates file processing and database storage."""
    
    def __init__(self):
        self._language_registry = language_registry
        self._pattern_processor = pattern_processor
        self._loop = get_loop()
        self._semaphore = asyncio.Semaphore(10)
        self._processed_files = 0
        self._failed_files = 0
        self._pending_tasks: Set[asyncio.Future] = set()
        self._initialized = False
        register_shutdown_handler(self.cleanup)
    
    async def initialize(self):
        """Initialize the processor."""
        if not self._initialized:
            try:
                # Initialize any processor-specific resources
                self._initialized = True
                log("FileProcessor initialized", level="info")
            except Exception as e:
                log(f"Error initializing FileProcessor: {e}", level="error")
                raise
    
    @handle_async_errors(error_types=(ProcessingError, DatabaseError))
    async def process_file(self, file_path: str, repo_id: int, base_path: str) -> Optional[Dict]:
        """[2.2] Process a single file using the managed event loop."""
        if not self._initialized:
            await self.initialize()
            
        async with self._semaphore:
            try:
                # Use cached file reader to avoid redundant I/O
                content = await cached_read_file(file_path)
                if content is None:
                    self._failed_files += 1
                    log(f"Could not read file content: {file_path}", level="warning")
                    return None
                    
                # Get relative path for storage
                rel_path = get_relative_path(file_path, base_path)
                
                # Process based on file type
                classification = await cached_classify_file(file_path)
                if not classification:
                    log(f"Could not classify file: {file_path}", level="debug")
                    return None
                    
                async with transaction_scope() as txn:
                    await txn.track_repo_change(repo_id)
                    
                    if classification.file_type == FileType.CODE:
                        result = await self._process_code_file(repo_id, rel_path, content, classification)
                    elif classification.file_type == FileType.DOC:
                        result = await self._process_doc_file(repo_id, rel_path, content, classification)
                    else:
                        log(f"Skipping file {rel_path} with type {classification.file_type}", level="debug")
                        return None
                    
                    if result:
                        self._processed_files += 1
                        return result
                    else:
                        self._failed_files += 1
                        return None
                    
            except Exception as e:
                self._failed_files += 1
                log(f"Error in file processor: {e}", level="error")
                return None
            finally:
                # Clean up any pending tasks
                if self._pending_tasks:
                    await asyncio.gather(*[asyncio.wrap_future(f) for f in self._pending_tasks], return_exceptions=True)
                    self._pending_tasks.clear()
    
    @handle_async_errors(error_types=(ProcessingError, DatabaseError))
    async def _process_code_file(self, repo_id: int, rel_path: str, content: str, classification) -> Optional[Dict]:
        """[2.3] Process and store code file with embeddings."""
        async with AsyncErrorBoundary(f"processing code file {rel_path}", severity=ErrorSeverity.ERROR):
            try:
                # Parse file
                async with AsyncErrorBoundary(f"Error parsing {rel_path}", severity=ErrorSeverity.ERROR):
                    parse_result = await cached_parse_file(rel_path, content, classification)
                    if not parse_result:
                        # Try alternative language if primary parsing fails
                        for alt_language in get_suggested_alternatives(classification.language_id):
                            log(f"Trying alternative language {alt_language} for {rel_path}", level="debug")
                            alt_classification = FileClassification(
                                file_type=classification.file_type,
                                language_id=alt_language,
                                parser_type=classification.parser_type,
                                file_path=classification.file_path,
                                is_binary=classification.is_binary
                            )
                            parse_result = await unified_parser.parse_file(rel_path, content)
                            if parse_result:
                                log(f"Successfully parsed {rel_path} as {alt_language}", level="info")
                                break
                
                    if not parse_result:
                        log(f"Failed to parse file: {rel_path}", level="warning")
                        return None
                
                # Get patterns for the file if needed for feature extraction
                patterns = await cached_get_patterns(classification)
                
                # Generate embedding
                async with AsyncErrorBoundary(f"Error generating embedding for {rel_path}", severity=ErrorSeverity.ERROR):
                    embedding = await cached_embed_code(content)
                
                # Store with embedding
                async with AsyncErrorBoundary(f"Error storing {rel_path} in database", severity=ErrorSeverity.ERROR):
                    await upsert_code_snippet({
                        'repo_id': repo_id,
                        'file_path': rel_path,
                        'content': content,
                        'language': classification.language_id,
                        'ast': parse_result.ast,
                        'enriched_features': parse_result.features,
                        'embedding': embedding.tolist() if embedding is not None else None
                    })
                
                return {
                    'file_path': rel_path,
                    'language': classification.language_id,
                    'status': 'success'
                }
            except Exception as e:
                log(f"Error processing code file {rel_path}: {e}", level="error")
                return None
    
    @handle_async_errors(error_types=(ProcessingError, DatabaseError))
    async def _process_doc_file(self, repo_id: int, rel_path: str, content: str, classification) -> Optional[Dict]:
        """[2.4] Process and store documentation file with embeddings."""
        async with AsyncErrorBoundary(f"processing doc file {rel_path}", severity=ErrorSeverity.ERROR):
            try:
                # Generate embedding
                async with AsyncErrorBoundary(f"Error generating embedding for doc {rel_path}", severity=ErrorSeverity.ERROR):
                    embedding = await cached_embed_doc(content)
                
                doc_type = classification.language_id
                
                async with AsyncErrorBoundary(f"Error storing doc {rel_path} in database", severity=ErrorSeverity.ERROR):
                    await upsert_doc(
                        repo_id=repo_id,
                        file_path=rel_path,
                        content=content,
                        doc_type=doc_type,
                        embedding=embedding.tolist() if embedding is not None else None
                    )
                
                return {
                    'file_path': rel_path,
                    'doc_type': doc_type,
                    'status': 'success'
                }
            except Exception as e:
                log(f"Error processing doc file {rel_path}: {e}", level="error")
                return None

    def get_stats(self) -> Dict[str, int]:
        """Get processing statistics."""
        return {
            'processed_files': self._processed_files,
            'failed_files': self._failed_files
        }

    async def cleanup(self):
        """Clean up all resources."""
        try:
            # Clear caches
            self.clear_cache()
            
            # Cancel and clean up any pending tasks
            if self._pending_tasks:
                for task in self._pending_tasks:
                    task.cancel()
                await asyncio.gather(*[asyncio.wrap_future(f) for f in self._pending_tasks], return_exceptions=True)
                self._pending_tasks.clear()
            
            self._initialized = False
            log("FileProcessor cleaned up", level="info")
        except Exception as e:
            log(f"Error cleaning up FileProcessor: {e}", level="error")
    
    def clear_cache(self):
        """Clear all caches"""
        # Each parser manages its own cache
        pass


# Cache-enabled utility functions

@cached_in_request
async def cached_read_file(file_path: str) -> Optional[str]:
    """Cached version of async_read_file to avoid redundant file I/O."""
    return await async_read_file(file_path)

@cached_in_request
async def cached_classify_file(file_path: str):
    """Cached file classification to avoid redundant classification."""
    return get_file_classification(file_path)

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