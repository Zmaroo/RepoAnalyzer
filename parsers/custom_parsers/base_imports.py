"""Base imports for custom parsers."""

from typing import Dict, List, Any, Optional, Set, Type, TYPE_CHECKING, Union, Tuple
import asyncio
from parsers.base_parser import BaseParser
from parsers.types import (
    FileType, ParserType, PatternCategory,
    AICapability, AIContext, AIProcessingResult,
    AIConfidenceMetrics, InteractionType
)
from parsers.models import (
    FileClassification,
    PatternType,
    PatternMatch,
    PatternDefinition,
    QueryPattern,
    BaseNodeDict,
    AsciidocNodeDict,
    MarkdownNodeDict,
    HtmlNodeDict,
    XmlNodeDict,
    YamlNodeDict,
    JsonNodeDict,
    TomlNodeDict,
    IniNodeDict,
    EnvNodeDict,
    EditorconfigNodeDict,
    GraphQLNodeDict,
    CobaltNodeDict,
    NimNodeDict,
    OcamlNodeDict,
    PlaintextNodeDict,
    RstNodeDict,
    AIPatternResult
)
from utils.logger import log
from utils.error_handling import (
    handle_errors,
    handle_async_errors,
    AsyncErrorBoundary,
    ProcessingError,
    ParsingError,
    ErrorSeverity
)
from utils.shutdown import register_shutdown_handler
from utils.cache import cache_coordinator, UnifiedCache
from utils.health_monitor import global_health_monitor
from parsers.pattern_processor import PatternProcessor
from parsers.ai_pattern_processor import AIPatternProcessor
from parsers.parser_interfaces import AIParserInterface

class CustomParserMixin:
    """Mixin class providing common functionality for custom parsers."""
    
    def __init__(self):
        """Initialize custom parser mixin."""
        self._cache = None
        self._lock = asyncio.Lock()
        self._pending_tasks: Set[asyncio.Task] = set()
        self._initialized = False
        self._ai_processor = None
        self._pattern_processor = None
        self._pattern_memory: Dict[str, float] = {}
        self._interaction_history: List[Dict[str, Any]] = []
        self._capabilities = {
            AICapability.CODE_UNDERSTANDING,
            AICapability.CODE_GENERATION,
            AICapability.CODE_MODIFICATION,
            AICapability.CODE_REVIEW,
            AICapability.DOCUMENTATION,
            AICapability.LEARNING
        }
    
    async def _initialize_cache(self, parser_name: str):
        """Initialize cache for custom parser."""
        if not self._cache:
            self._cache = UnifiedCache(f"custom_parser_{parser_name}")
            await cache_coordinator.register_cache(self._cache)
    
    async def _check_parse_cache(self, source_code: str) -> Optional[Dict[str, Any]]:
        """Check if parse result is cached."""
        if not self._cache:
            return None
            
        import hashlib
        source_hash = hashlib.md5(source_code.encode('utf8')).hexdigest()
        cache_key = f"parse_{self.language_id}_{source_hash}"
        
        return await self._cache.get(cache_key)
    
    async def _store_parse_result(self, source_code: str, result: Dict[str, Any]):
        """Store parse result in cache."""
        if not self._cache:
            return
            
        import hashlib
        source_hash = hashlib.md5(source_code.encode('utf8')).hexdigest()
        cache_key = f"parse_{self.language_id}_{source_hash}"
        
        await self._cache.set(cache_key, result)
    
    async def _check_features_cache(self, ast: Dict[str, Any], source_code: str) -> Optional[Dict[str, Any]]:
        """Check if features are cached."""
        if not self._cache:
            return None
            
        import hashlib
        ast_hash = hashlib.md5(str(ast).encode('utf8')).hexdigest()
        source_hash = hashlib.md5(source_code.encode('utf8')).hexdigest()
        cache_key = f"features_{self.language_id}_{ast_hash}_{source_hash}"
        
        return await self._cache.get(cache_key)
    
    async def _store_features_in_cache(self, ast: Dict[str, Any], source_code: str, features: Dict[str, Any]):
        """Store features in cache."""
        if not self._cache:
            return
            
        import hashlib
        ast_hash = hashlib.md5(str(ast).encode('utf8')).hexdigest()
        source_hash = hashlib.md5(source_code.encode('utf8')).hexdigest()
        cache_key = f"features_{self.language_id}_{ast_hash}_{source_hash}"
        
        await self._cache.set(cache_key, features)
    
    async def _cleanup_cache(self):
        """Clean up cache resources."""
        if self._cache:
            await cache_coordinator.unregister_cache(self._cache)
            self._cache = None
            
        # Clean up any pending tasks
        if self._pending_tasks:
            for task in self._pending_tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*self._pending_tasks, return_exceptions=True)
            self._pending_tasks.clear()
            
        self._initialized = False 