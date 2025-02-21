"""Unified parsing interface."""

from typing import Optional, Dict, Any
from parsers.base_parser import ParserResult
from parsers.language_support import language_registry
from parsers.models import FileInfo
from parsers.file_classification import get_file_classification
from utils.logger import log
from utils.cache import parser_cache
from utils.error_handling import (
    handle_async_errors,
    ParsingError,
    AsyncErrorBoundary
)

class UnifiedParser:
    """Main parser interface for all file types."""
    
    def __init__(self):
        self._language_registry = language_registry
    
    @handle_async_errors(error_types=(ParsingError, Exception))
    async def parse_file(self, file_path: str, content: str) -> Optional[ParserResult]:
        """Parse any file using appropriate parser with caching."""
        cache_key = f"{file_path}:{hash(content)}"
        
        # Try to get from cache
        cached_result = await parser_cache.get_async(cache_key)
        if cached_result:
            return ParserResult(**cached_result)
        
        async with AsyncErrorBoundary("file parsing", error_types=ParsingError):
            # Get file classification and language info
            classification = get_file_classification(file_path)
            if not classification:
                log(f"No classification found for {file_path}", level="debug")
                return None
            
            # Get language info and appropriate parser
            language_info = self._language_registry.get_language_info(file_path)
            if not language_info.is_supported:
                log(f"Language not supported for {file_path}", level="debug")
                return None
            
            # Get parser and parse
            parser = self._language_registry.get_parser(language_info)
            if not parser:
                log(f"No parser available for {file_path}", level="debug")
                return None
            
            result = parser.parse(content)
            
            # Cache the result
            await parser_cache.set_async(cache_key, result.dict())
            
            return result

# Global instance
unified_parser = UnifiedParser() 