"""Unified parsing interface.

Pipeline Stages:
1. File Classification & Parser Selection
   - Uses: parsers/file_classification.py -> get_file_classification()
     Returns: Optional[FileClassification]
   - Uses: parsers/language_support.py -> language_registry.get_parser()
     Returns: Optional[BaseParser]

2. Content Parsing
   - Uses: parsers/base_parser.py -> BaseParser.parse()
     Returns: Optional[ParserResult]

3. Feature Extraction
   - Uses: parsers/base_parser.py -> BaseParser._extract_category_features()
     Returns: ExtractedFeatures

4. Result Standardization
   - Returns: Optional[ParserResult]
"""

from typing import Optional, Set
import asyncio
from parsers.types import FileType, FeatureCategory, ParserType, ParserResult
from parsers.models import FileClassification, PATTERN_CATEGORIES
from dataclasses import asdict

from parsers.language_support import language_registry
from parsers.language_mapping import (
    detect_language, 
    get_parser_info_for_language, 
    get_complete_language_info
)
from utils.error_handling import handle_async_errors, ParsingError, AsyncErrorBoundary, ErrorSeverity
from utils.encoding import encode_query_pattern
from utils.logger import log
from utils.cache import cache_coordinator
from utils.app_init import register_shutdown_handler
from utils.async_runner import submit_async_task
from db.transaction import transaction_scope
from db.upsert_ops import coordinator as upsert_coordinator

class UnifiedParser:
    """Unified parsing interface."""
    
    def __init__(self):
        """Initialize the unified parser."""
        self._initialized = False
        self._pending_tasks: Set[asyncio.Future] = set()
        register_shutdown_handler(self.cleanup)
    
    @handle_async_errors(error_types=(Exception,))
    async def initialize(self):
        """Initialize parser resources."""
        if not self._initialized:
            try:
                async with AsyncErrorBoundary("unified_parser_initialization"):
                    # Initialize cache coordinator
                    future = submit_async_task(cache_coordinator.initialize())
                    self._pending_tasks.add(future)
                    try:
                        await asyncio.wrap_future(future)
                    finally:
                        self._pending_tasks.remove(future)
                    
                    # Initialize upsert coordinator
                    future = submit_async_task(upsert_coordinator.initialize())
                    self._pending_tasks.add(future)
                    try:
                        await asyncio.wrap_future(future)
                    finally:
                        self._pending_tasks.remove(future)
                    
                    # Initialize language registry
                    future = submit_async_task(language_registry.initialize())
                    self._pending_tasks.add(future)
                    try:
                        await asyncio.wrap_future(future)
                    finally:
                        self._pending_tasks.remove(future)
                    
                    self._initialized = True
                    log("Unified parser initialized", level="info")
            except Exception as e:
                log(f"Error initializing unified parser: {e}", level="error")
                raise
    
    @handle_async_errors(error_types=(ParsingError, Exception))
    async def parse_file(self, file_path: str, content: str) -> Optional[ParserResult]:
        """Parse file content using appropriate parser."""
        if not self._initialized:
            await self.initialize()
        
        # Check if the complete parsed result is already cached
        parse_cache_key = f"parse:{file_path}:{hash(content)}"
        
        future = submit_async_task(cache_coordinator.get_async(parse_cache_key))
        self._pending_tasks.add(future)
        try:
            cached_result = await asyncio.wrap_future(future)
            if cached_result:
                return ParserResult(**cached_result)
        finally:
            self._pending_tasks.remove(future)
        
        async with AsyncErrorBoundary(f"parse_file_{file_path}", error_types=(ParsingError, Exception)):
            # Use the improved language detection with confidence score
            future = submit_async_task(detect_language(file_path, content))
            self._pending_tasks.add(future)
            try:
                language_id, confidence = await asyncio.wrap_future(future)
            finally:
                self._pending_tasks.remove(future)
                
            if confidence < 0.6:
                log(f"Low confidence ({confidence:.2f}) language detection for {file_path}", level="warning")
            
            # Get comprehensive language and parser information
            future = submit_async_task(get_complete_language_info(language_id))
            self._pending_tasks.add(future)
            try:
                language_info = await asyncio.wrap_future(future)
            finally:
                self._pending_tasks.remove(future)
            
            # Create classification using the parser info
            classification = FileClassification(
                file_type=language_info["file_type"],
                language_id=language_info["canonical_name"],
                parser_type=language_info["parser_type"]
            )

            future = submit_async_task(language_registry.get_parser(classification))
            self._pending_tasks.add(future)
            try:
                parser = await asyncio.wrap_future(future)
            finally:
                self._pending_tasks.remove(future)
                
            if not parser:
                log(f"No parser found for language: {classification.language_id}", level="error")
                return None

            # Parse the file within a transaction scope
            async with transaction_scope() as txn:
                # Parse the content
                future = submit_async_task(parser.parse(content))
                self._pending_tasks.add(future)
                try:
                    parse_result = await asyncio.wrap_future(future)
                finally:
                    self._pending_tasks.remove(future)
                
                if not parse_result or not parse_result.success:
                    return None

                features = {}
                for category in FeatureCategory:
                    future = submit_async_task(parser._extract_category_features(
                        category=category,
                        ast=parse_result.ast,
                        source_code=content
                    ))
                    self._pending_tasks.add(future)
                    try:
                        category_features = await asyncio.wrap_future(future)
                        features[category.value] = category_features
                    finally:
                        self._pending_tasks.remove(future)

                result = ParserResult(
                    success=True,
                    ast=parse_result.ast,
                    features={
                        "syntax": features.get(FeatureCategory.SYNTAX.value, {}),
                        "semantics": features.get(FeatureCategory.SEMANTICS.value, {}),
                        "documentation": features.get(FeatureCategory.DOCUMENTATION.value, {}),
                        "structure": features.get(FeatureCategory.STRUCTURE.value, {})
                    },
                    documentation=features.get(FeatureCategory.DOCUMENTATION.value, {}),
                    complexity=features.get(FeatureCategory.SYNTAX.value, {}).get("metrics", {}),
                    statistics=parse_result.statistics
                )

                # Store the result in the database
                future = submit_async_task(upsert_coordinator.store_parsed_content(
                    repo_id=None,  # Will be set when associated with a repository
                    file_path=file_path,
                    ast=parse_result.ast,
                    features=features
                ))
                self._pending_tasks.add(future)
                try:
                    await asyncio.wrap_future(future)
                finally:
                    self._pending_tasks.remove(future)

                # Cache the complete parsed result
                cached_result = asdict(result)
                future = submit_async_task(cache_coordinator.set_async(parse_cache_key, cached_result))
                self._pending_tasks.add(future)
                try:
                    await asyncio.wrap_future(future)
                finally:
                    self._pending_tasks.remove(future)
                
                return result
        
        return None
    
    async def cleanup(self):
        """Clean up parser resources."""
        try:
            # Cancel and clean up any pending tasks
            if self._pending_tasks:
                for task in self._pending_tasks:
                    task.cancel()
                await asyncio.gather(*[asyncio.wrap_future(f) for f in self._pending_tasks], return_exceptions=True)
                self._pending_tasks.clear()
            
            self._initialized = False
            log("Unified parser cleaned up", level="info")
        except Exception as e:
            log(f"Error cleaning up unified parser: {e}", level="error")

# Global instance
unified_parser = UnifiedParser() 