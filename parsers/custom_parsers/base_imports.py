"""Base imports for custom parsers.

This module provides base imports and mixin functionality for custom parsers
that handle languages not supported by tree-sitter.
"""

from typing import Dict, List, Any, Optional, Set, Type, TYPE_CHECKING, Union, Tuple
import asyncio
import time
from collections import Counter

from parsers.base_parser import BaseParser
from parsers.types import (
    FileType, ParserType, PatternCategory,
    AICapability, AIContext, AIProcessingResult,
    AIConfidenceMetrics, InteractionType, PatternType,
    Documentation, ComplexityMetrics, ExtractedFeatures,
    PatternPurpose, ConfidenceLevel, FeatureCategory,
    QueryPattern
)
from parsers.models import (
    FileClassification,
    BaseNodeDict,
    AsciidocNodeDict,
    CobaltNodeDict,
    EditorconfigNodeDict,
    EnvNodeDict,
    IniNodeDict,
    PlaintextNodeDict
)
from parsers.query_patterns.enhanced_patterns import (
    PatternContext, PatternPerformanceMetrics,
    AdaptivePattern, ResilientPattern, CrossProjectPatternLearner
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
from utils.health_monitor import global_health_monitor, ComponentStatus, monitor_operation
from parsers.parser_interfaces import AIParserInterface
from utils.cache_analytics import get_cache_analytics
from parsers.pattern_processor import PatternProcessor
from parsers.ai_pattern_processor import AIPatternProcessor

if TYPE_CHECKING:
    from parsers.pattern_processor import PatternProcessor
    from parsers.ai_pattern_processor import AIPatternProcessor

__all__ = [
    # Base classes
    'BaseParser',
    'CustomParserMixin',
    'EnhancedPatternMixin',
    
    # Types
    'FileType',
    'ParserType',
    'PatternType',
    'PatternCategory',
    'FeatureCategory',
    'QueryPattern',
    
    # AI related
    'AICapability',
    'AIContext',
    'AIProcessingResult',
    'AIConfidenceMetrics',
    'AIPatternProcessor',
    
    # Pattern related
    'PatternProcessor',
    'AdaptivePattern',
    'ResilientPattern',
    'PatternContext',
    'PatternPerformanceMetrics',
    'CrossProjectPatternLearner',
    
    # Documentation
    'Documentation',
    'ComplexityMetrics',
    
    # Node types
    'AsciidocNodeDict',
    'CobaltNodeDict',
    'EditorconfigNodeDict',
    'EnvNodeDict',
    'IniNodeDict',
    'PlaintextNodeDict',
    
    # Utils
    'ComponentStatus',
    'monitor_operation',
    'handle_errors',
    'handle_async_errors',
    'AsyncErrorBoundary',
    'ProcessingError',
    'ParsingError',
    'ErrorSeverity',
    'global_health_monitor',
    'register_shutdown_handler',
    'log',
    'UnifiedCache',
    'cache_coordinator',
    'get_cache_analytics',
    
    # Python types
    'Dict',
    'List',
    'Any',
    'Optional',
    'Set',
    'Tuple',
    'Counter',
    
    # Python modules
    'time',
    'asyncio',
]

class EnhancedPatternMixin:
    """Mixin providing enhanced pattern capabilities for custom parsers."""
    
    def __init__(self):
        """Initialize enhanced pattern mixin."""
        self._pattern_learner = None
        self._adaptive_patterns: Dict[str, AdaptivePattern] = {}
        self._resilient_patterns: Dict[str, ResilientPattern] = {}
        self._pattern_metrics = PatternPerformanceMetrics()
    
    async def _initialize_pattern_learner(self):
        """Initialize pattern learner."""
        if not self._pattern_learner:
            self._pattern_learner = CrossProjectPatternLearner()
            await self._pattern_learner.initialize()
    
    async def _process_with_enhanced_patterns(
        self,
        source_code: str,
        context: AIContext
    ) -> List[Dict[str, Any]]:
        """Process source code with enhanced patterns."""
        pattern_context = PatternContext(
            code_structure=context.code_structure if hasattr(context, 'code_structure') else {},
            language_stats=context.language_stats if hasattr(context, 'language_stats') else {},
            project_patterns=context.project_patterns if hasattr(context, 'project_patterns') else [],
            file_location=context.file_path if hasattr(context, 'file_path') else "",
            dependencies=set(context.dependencies) if hasattr(context, 'dependencies') else set(),
            recent_changes=context.recent_changes if hasattr(context, 'recent_changes') else [],
            parser_type=ParserType.CUSTOM
        )
        
        matches = []
        
        # Try adaptive patterns first
        for pattern in self._adaptive_patterns.values():
            try:
                pattern_matches = await pattern.matches(source_code, pattern_context)
                if pattern_matches:
                    matches.extend(pattern_matches)
            except Exception as e:
                await log(f"Error in adaptive pattern {pattern.name}: {e}", level="error")
        
        # Try resilient patterns if needed
        if not matches:
            for pattern in self._resilient_patterns.values():
                try:
                    pattern_matches = await pattern.matches(source_code, pattern_context)
                    if pattern_matches:
                        matches.extend(pattern_matches)
                except Exception as e:
                    await log(f"Error in resilient pattern {pattern.name}: {e}", level="error")
        
        return matches
    
    async def _learn_patterns_from_source(
        self,
        source_code: str,
        context: AIContext
    ) -> List[Dict[str, Any]]:
        """Learn patterns from source code."""
        await self._initialize_pattern_learner()
        
        pattern_context = PatternContext(
            code_structure=context.code_structure if hasattr(context, 'code_structure') else {},
            language_stats=context.language_stats if hasattr(context, 'language_stats') else {},
            project_patterns=context.project_patterns if hasattr(context, 'project_patterns') else [],
            file_location=context.file_path if hasattr(context, 'file_path') else "",
            dependencies=set(context.dependencies) if hasattr(context, 'dependencies') else set(),
            recent_changes=context.recent_changes if hasattr(context, 'recent_changes') else [],
            parser_type=ParserType.CUSTOM
        )
        
        return await self._pattern_learner.suggest_patterns(pattern_context)

class CustomParserMixin:
    """Mixin class providing common functionality for custom parsers.
    
    This mixin is used for languages not supported by tree-sitter.
    It provides caching, error handling, and AI processing capabilities.
    """
    
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
        
        # Initialize enhanced pattern support
        self._enhanced_patterns = EnhancedPatternMixin()
    
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

    async def _check_health(self) -> Dict[str, Any]:
        """Health check implementation."""
        metrics = {
            "total_parsed": self._metrics["total_parsed"],
            "successful_parses": self._metrics["successful_parses"],
            "failed_parses": self._metrics["failed_parses"],
            "cache_hits": self._metrics["cache_hits"],
            "cache_misses": self._metrics["cache_misses"],
            "avg_parse_time": (
                sum(self._metrics["parse_times"]) / len(self._metrics["parse_times"])
                if self._metrics["parse_times"] else 0
            )
        }
        
        # Calculate error rate
        total_ops = metrics["successful_parses"] + metrics["failed_parses"]
        error_rate = metrics["failed_parses"] / total_ops if total_ops > 0 else 0
        
        # Determine status based on error rate
        status = ComponentStatus.HEALTHY
        if error_rate > 0.1:  # More than 10% errors
            status = ComponentStatus.DEGRADED
        if error_rate > 0.3:  # More than 30% errors
            status = ComponentStatus.UNHEALTHY
            
        await global_health_monitor.update_component_status(
            f"parser_{self.language_id}",
            status,
            details={
                "metrics": metrics,
                "error_rate": error_rate
            }
        )
        
        return metrics 