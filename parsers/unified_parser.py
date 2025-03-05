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

from typing import Optional, Set, Dict, Any
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
from utils.error_handling import handle_async_errors, ParsingError, AsyncErrorBoundary, ErrorSeverity, ProcessingError
from utils.encoding import encode_query_pattern
from utils.logger import log
from utils.cache import cache_coordinator, UnifiedCache
from utils.shutdown import register_shutdown_handler
from db.transaction import transaction_scope
from db.upsert_ops import coordinator as upsert_coordinator
from utils.health_monitor import global_health_monitor

class UnifiedParser:
    """Unified parsing interface."""
    
    def __init__(self):
        """Private constructor - use create() instead."""
        self._initialized = False
        self._pending_tasks: Set[asyncio.Task] = set()
        self._lock = asyncio.Lock()
        self._cache = None
        self._component_states = {
            'language_registry': False,
            'upsert_coordinator': False,
            'cache_coordinator': False
        }
    
    async def ensure_initialized(self):
        """Ensure the instance is properly initialized before use."""
        if not self._initialized:
            raise ProcessingError("UnifiedParser instance not initialized. Use create() to initialize.")
        return True
    
    @classmethod
    async def create(cls) -> 'UnifiedParser':
        """Async factory method to create and initialize a UnifiedParser instance."""
        instance = cls()
        try:
            async with AsyncErrorBoundary(
                operation_name="unified parser initialization",
                error_types=ProcessingError,
                severity=ErrorSeverity.CRITICAL
            ):
                # Initialize cache
                instance._cache = UnifiedCache("unified_parser")
                await cache_coordinator.register_cache(instance._cache)
                
                # Initialize components with proper error handling
                components = [
                    ('cache_coordinator', cache_coordinator.initialize()),
                    ('upsert_coordinator', upsert_coordinator.initialize()),
                    ('language_registry', language_registry.initialize())
                ]
                
                for component_name, init_coro in components:
                    try:
                        task = asyncio.create_task(init_coro)
                        instance._pending_tasks.add(task)
                        try:
                            await task
                            instance._component_states[component_name] = True
                        finally:
                            instance._pending_tasks.remove(task)
                    except Exception as e:
                        await log(f"Error initializing {component_name}: {e}", level="error")
                        raise ProcessingError(f"Failed to initialize {component_name}: {e}")
                
                # Register shutdown handler
                register_shutdown_handler(instance.cleanup)
                
                # Initialize health monitoring
                global_health_monitor.register_component("unified_parser")
                
                instance._initialized = True
                await log("Unified parser initialized", level="info")
                return instance
        except Exception as e:
            await log(f"Error initializing unified parser: {e}", level="error")
            # Cleanup on initialization failure
            await instance.cleanup()
            raise ProcessingError(f"Failed to initialize unified parser: {e}")
    
    @handle_async_errors(error_types=(ProcessingError,))
    async def parse_file(self, file_path: str, content: str) -> Optional[ParserResult]:
        """Parse a file and extract features."""
        if not self._initialized:
            await self.ensure_initialized()
        
        async with self._lock:
            # Check cache first
            cache_key = f"parse_result_{file_path}"
            if self._cache:
                cached_result = await self._cache.get(cache_key)
                if cached_result:
                    return ParserResult(**cached_result)
            
            try:
                # Create task for language detection
                detect_task = asyncio.create_task(detect_language(file_path, content))
                self._pending_tasks.add(detect_task)
                try:
                    language_id = await detect_task
                finally:
                    self._pending_tasks.remove(detect_task)
                
                if not language_id:
                    return None
                
                # Get parser for language
                parser = await language_registry.get_parser(language_id)
                if not parser:
                    return None
                
                # Parse content
                task = asyncio.create_task(parser.parse(content))
                self._pending_tasks.add(task)
                try:
                    result = await task
                finally:
                    self._pending_tasks.remove(task)
                
                # Cache result
                if self._cache and result:
                    await self._cache.set(cache_key, asdict(result))
                
                return result
            except Exception as e:
                await log(f"Error parsing file {file_path}: {e}", level="error")
                raise ProcessingError(f"Failed to parse file {file_path}: {e}")
    
    async def cleanup(self):
        """Clean up parser resources."""
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
            cleanup_order = [
                ('language_registry', language_registry),
                ('upsert_coordinator', upsert_coordinator),
                ('cache_coordinator', cache_coordinator)
            ]
            
            for component_name, component in cleanup_order:
                if self._component_states.get(component_name):
                    try:
                        await component.cleanup()
                        self._component_states[component_name] = False
                    except Exception as e:
                        await log(f"Error cleaning up {component_name}: {e}", level="error")
            
            # Cleanup cache
            if self._cache:
                await cache_coordinator.unregister_cache(self._cache)
                self._cache = None
            
            # Unregister from health monitoring
            global_health_monitor.unregister_component("unified_parser")
            
            self._initialized = False
            await log("Unified parser cleaned up", level="info")
        except Exception as e:
            await log(f"Error cleaning up unified parser: {e}", level="error")
            raise ProcessingError(f"Failed to cleanup unified parser: {e}")

# Global instance
_unified_parser = None

async def get_unified_parser() -> UnifiedParser:
    """Get the global unified parser instance."""
    global _unified_parser
    if not _unified_parser:
        _unified_parser = await UnifiedParser.create()
    return _unified_parser 