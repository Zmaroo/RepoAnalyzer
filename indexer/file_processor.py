"""File processing coordination."""

from typing import Optional, Dict
from parsers.language_support import language_registry
from parsers.file_classification import FileType, get_file_classification
from parsers.unified_parser import unified_parser
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

class FileProcessor:
    """Coordinates file processing and database storage."""
    
    def __init__(self):
        self._language_registry = language_registry
    
    @handle_async_errors(error_types=(ProcessingError, DatabaseError))
    async def process_file(
        self,
        file_path: str,
        repo_id: int,
        base_path: str
    ) -> Optional[Dict]:
        """Process a single file with error handling."""
        
        async with AsyncErrorBoundary("file reading"):
            if not is_processable_file(file_path):
                return None
                
            try:
                async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                    content = await f.read()
            except UnicodeDecodeError:
                log(f"Binary or invalid encoding in file: {file_path}", level="debug")
                return None
        
        classification = get_file_classification(file_path)
        if not classification:
            return None
            
        rel_path = get_relative_path(file_path, base_path)
        
        async with AsyncErrorBoundary("file processing", error_types=ProcessingError):
            if classification.file_type == FileType.CODE:
                await self._process_code_file(repo_id, rel_path, content)
            elif classification.file_type == FileType.DOC:
                await self._process_doc_file(repo_id, rel_path, content)
    
    @handle_async_errors(error_types=DatabaseError)
    async def _process_code_file(
        self,
        repo_id: int,
        rel_path: str,
        content: str
    ) -> None:
        """Process and store code file."""
        parse_result = await unified_parser.parse_file(rel_path, content)
        if not parse_result:
            return
            
        await upsert_code_snippet({
            'repo_id': repo_id,
            'file_path': rel_path,
            'content': content,
            'language': parse_result.language,
            'ast': parse_result.ast,
            'enriched_features': parse_result.features
        })
    
    @handle_async_errors(error_types=DatabaseError)
    async def _process_doc_file(
        self,
        repo_id: int,
        rel_path: str,
        content: str
    ) -> None:
        """Process and store documentation file."""
        await upsert_doc(
            repo_id=repo_id,
            file_path=rel_path,
            content=content,
            doc_type='markdown' if rel_path.endswith('.md') else 'text'
        )

    def clear_cache(self):
        """Clear all caches"""
        # Each parser manages its own cache
        pass 