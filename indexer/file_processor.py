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
"""

from typing import Optional, Dict
from tree_sitter_language_pack import SupportedLanguage
from indexer.file_utils import get_file_classification
from parsers.types import FileType, ParserType
from parsers.language_support import language_registry
from parsers.unified_parser import unified_parser
from parsers.pattern_processor import pattern_processor
from db.upsert_ops import upsert_code_snippet, upsert_doc
from indexer.file_utils import get_relative_path, is_processable_file
from utils.logger import log
from utils.error_handling import (
    handle_async_errors,
    ProcessingError,
    AsyncErrorBoundary,
    DatabaseError
)
import aiofiles
from utils.async_runner import get_loop
from indexer.async_utils import async_read_file
import asyncio
from embedding.embedding_models import code_embedder, doc_embedder

class FileProcessor:
    """[2.1] Coordinates file processing and database storage."""
    
    def __init__(self):
        self._language_registry = language_registry  # USES: parsers/language_support.py
        self._pattern_processor = pattern_processor  # Use the global pattern processor instance
        self._loop = get_loop()  # Get managed event loop
        self._semaphore = asyncio.Semaphore(10)  # Limit concurrent file operations
    
    async def process_file(self, file_path: str, repo_id: int, base_path: str) -> Optional[Dict]:
        """[2.2] Process a single file using the managed event loop."""
        async with self._semaphore:  # Control concurrent operations
            try:
                content = await async_read_file(file_path)
                if content is None:
                    return None
                    
                # Get relative path for storage
                rel_path = get_relative_path(file_path, base_path)
                
                # Process based on file type
                classification = get_file_classification(file_path)
                if not classification:
                    return None
                    
                if classification.file_type == FileType.CODE:
                    await self._process_code_file(repo_id, rel_path, content, classification)
                elif classification.file_type == FileType.DOC:
                    await self._process_doc_file(repo_id, rel_path, content, classification)
                else:
                    log(f"Skipping file {rel_path} with type {classification.file_type}", level="debug")
                    
            except Exception as e:
                log(f"Error in file processor: {e}", level="error")
                return None
    
    async def _process_code_file(self, repo_id: int, rel_path: str, content: str, classification) -> None:
        """[2.3] Process and store code file with embeddings."""
        try:
            # Parse file
            parse_result = await unified_parser.parse_file(rel_path, content, classification)
            if not parse_result:
                log(f"Failed to parse file: {rel_path}", level="warning")
                return
                
            # Get patterns for the file if needed for feature extraction
            patterns = self._pattern_processor.get_patterns_for_file(classification)
            
            # Generate embedding
            embedding = await code_embedder.embed_async(content)
            
            # Store with embedding
            await upsert_code_snippet({
                'repo_id': repo_id,
                'file_path': rel_path,
                'content': content,
                'language': classification.language_id,
                'ast': parse_result.ast,
                'enriched_features': parse_result.features,
                'embedding': embedding.tolist() if embedding is not None else None
            })
        except Exception as e:
            log(f"Error processing code file {rel_path}: {e}", level="error")
    
    async def _process_doc_file(self, repo_id: int, rel_path: str, content: str, classification) -> None:
        """[2.4] Process and store documentation file with embeddings."""
        try:
            # Generate embedding
            embedding = await doc_embedder.embed_async(content)
            
            doc_type = classification.language_id
            
            await upsert_doc(
                repo_id=repo_id,
                file_path=rel_path,
                content=content,
                doc_type=doc_type,
                embedding=embedding.tolist() if embedding is not None else None
            )
        except Exception as e:
            log(f"Error processing doc file {rel_path}: {e}", level="error")

    def clear_cache(self):
        """Clear all caches"""
        # Each parser manages its own cache
        pass 