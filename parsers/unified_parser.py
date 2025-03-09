"""Unified parser that handles both tree-sitter and custom parsers.

This module provides a unified interface for parsing source code using either
tree-sitter-language-pack or custom parsers, depending on availability and precedence.
"""

import asyncio
from typing import Dict, Any, List, Optional, Union, Tuple, Set
from tree_sitter_language_pack import get_binding, get_language, get_parser, SupportedLanguage
from parsers.types import (
    FileType, FeatureCategory, ParserType, Documentation, ComplexityMetrics,
    ExtractedFeatures, PatternCategory, PatternPurpose,
    AICapability, AIContext, AIProcessingResult, InteractionType, ConfidenceLevel
)
from parsers.models import QueryResult, FileClassification, PATTERN_CATEGORIES
from parsers.language_mapping import normalize_language_name, get_parser_type
from parsers.custom_parsers import CUSTOM_PARSER_CLASSES
from parsers.parser_interfaces import BaseParser, TreeSitterParser, CustomParser
from utils.logger import log
from utils.error_handling import AsyncErrorBoundary, handle_async_errors, ProcessingError
from utils.shutdown import register_shutdown_handler
from utils.cache import UnifiedCache, cache_coordinator
from utils.health_monitor import ComponentStatus, global_health_monitor
from utils.async_runner import submit_async_task, cleanup_tasks
from utils.request_cache import request_cache_context, cached_in_request
from utils.error_handling import ErrorAudit
import traceback
import time

class UnifiedParser:
    """Unified parser that handles both tree-sitter and custom parsers."""
    
    def __init__(self):
        """Initialize unified parser."""
        self._initialized = False
        self._cache = UnifiedCache("unified_parser")
        self._ast_cache = UnifiedCache("unified_parser_ast")
        self._pattern_cache = UnifiedCache("unified_parser_patterns")
        self._parsers: Dict[str, BaseParser] = {}
        self._pending_tasks: Set[asyncio.Task] = set()
        self._lock = asyncio.Lock()
        self._error_recovery_stats = {}
        self._recovery_strategies = {}
        self._error_patterns = {}
        self._recovery_learning_enabled = True
        register_shutdown_handler(self.cleanup)
    
    async def ensure_initialized(self):
        """Ensure the parser is initialized."""
        if not self._initialized:
            raise ProcessingError("Unified parser not initialized. Use create() to initialize.")
        return True
    
    @classmethod
    async def create(cls) -> 'UnifiedParser':
        """Create and initialize a unified parser instance."""
        instance = cls()
        try:
            async with AsyncErrorBoundary("unified_parser_initialization"):
                # Initialize health monitoring first
                await global_health_monitor.update_component_status(
                    "unified_parser",
                    ComponentStatus.INITIALIZING,
                    details={"stage": "starting"}
                )
                
                # Initialize cache
                instance._cache = UnifiedCache("unified_parser")
                await cache_coordinator.register_cache(instance._cache)
                
                # Register shutdown handler
                register_shutdown_handler(instance.cleanup)
                
                instance._initialized = True
                await log("Unified parser initialized", level="info")
                
                # Update final health status
                await global_health_monitor.update_component_status(
                    "unified_parser",
                    ComponentStatus.HEALTHY,
                    details={"stage": "complete"}
                )
                
                return instance
        except Exception as e:
            await log(f"Error initializing unified parser: {e}", level="error")
            await global_health_monitor.update_component_status(
                "unified_parser",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"initialization_error": str(e)}
            )
            # Cleanup on initialization failure
            cleanup_task = submit_async_task(instance.cleanup())
            await asyncio.wrap_future(cleanup_task)
            raise ProcessingError(f"Failed to initialize unified parser: {e}")
    
    @cached_in_request(lambda language_id, file_type: f"parser:{language_id}:{file_type.value}")
    async def get_parser(self, language_id: str, file_type: FileType) -> BaseParser:
        """Get a parser for a specific language and file type."""
        if not self._initialized:
            await self.ensure_initialized()
        
        async with self._lock:
            # Check cache first
            cache_key = f"parser:{language_id}:{file_type.value}"
            cached_parser = await self._cache.get(cache_key)
            if cached_parser:
                return cached_parser
            
            # Get parser type
            parser_type, normalized_lang = await get_parser_type(language_id)
            
            try:
                # Try custom parser first (they take precedence)
                if parser_type == ParserType.CUSTOM:
                    parser = await CustomParser.create(normalized_lang, file_type)
                    await self._cache.set(cache_key, parser)
                    self._parsers[cache_key] = parser
                    await log(f"Using custom parser for {language_id}", level="info")
                    return parser
                
                # Fallback to tree-sitter parser
                if parser_type == ParserType.TREE_SITTER:
                    parser = await TreeSitterParser.create(normalized_lang, file_type)
                    await self._cache.set(cache_key, parser)
                    self._parsers[cache_key] = parser
                    await log(f"Using tree-sitter parser for {language_id}", level="info")
                    return parser
                
                raise ProcessingError(f"No parser available for {language_id}")
                
            except Exception as e:
                await log(f"Error creating parser for {language_id}: {e}", level="error")
                raise ProcessingError(f"Failed to create parser for {language_id}: {e}")
    
    async def _analyze_error(self, error: Exception, context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze error and context to determine best recovery strategy."""
        error_info = {
            "type": type(error).__name__,
            "message": str(error),
            "traceback": traceback.format_exc(),
            "context": context,
            "timestamp": time.time()
        }
        
        # Generate error pattern key
        error_key = f"{error_info['type']}:{context.get('language_id')}:{context.get('file_type', 'unknown')}"
        
        # Update error patterns
        if error_key not in self._error_patterns:
            self._error_patterns[error_key] = {
                "occurrences": 0,
                "successful_recoveries": 0,
                "failed_recoveries": 0,
                "recovery_times": []
            }
        
        self._error_patterns[error_key]["occurrences"] += 1
        
        return {
            "error_key": error_key,
            "error_info": error_info
        }

    async def _get_recovery_strategy(
        self,
        error_analysis: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Get best recovery strategy based on error analysis and past performance."""
        error_key = error_analysis["error_key"]
        
        if error_key in self._recovery_strategies:
            strategies = self._recovery_strategies[error_key]
            
            # Sort strategies by success rate
            sorted_strategies = sorted(
                strategies.items(),
                key=lambda x: x[1]["success_rate"],
                reverse=True
            )
            
            # Return best strategy with success rate above threshold
            for strategy_name, stats in sorted_strategies:
                if stats["success_rate"] > 0.3:  # 30% success rate threshold
                    return {
                        "name": strategy_name,
                        "steps": stats["steps"],
                        "success_rate": stats["success_rate"]
                    }
        
        # No good strategy found, return default
        return {
            "name": "default",
            "steps": ["fallback_parser", "basic_features"],
            "success_rate": 0.0
        }

    async def _update_recovery_stats(
        self,
        error_key: str,
        strategy_name: str,
        success: bool,
        recovery_time: float
    ) -> None:
        """Update recovery strategy statistics."""
        if not self._recovery_learning_enabled:
            return
            
        if error_key not in self._recovery_strategies:
            self._recovery_strategies[error_key] = {}
            
        if strategy_name not in self._recovery_strategies[error_key]:
            self._recovery_strategies[error_key][strategy_name] = {
                "uses": 0,
                "successes": 0,
                "avg_time": 0.0,
                "success_rate": 0.0
            }
            
        stats = self._recovery_strategies[error_key][strategy_name]
        stats["uses"] += 1
        if success:
            stats["successes"] += 1
            
        # Update moving averages
        stats["avg_time"] = (
            (stats["avg_time"] * (stats["uses"] - 1) + recovery_time)
            / stats["uses"]
        )
        stats["success_rate"] = stats["successes"] / stats["uses"]

    async def recover_from_parsing_error(
        self,
        error: Exception,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Smart error recovery based on error type and context."""
        start_time = time.time()
        
        try:
            # Analyze error
            error_analysis = await self._analyze_error(error, context)
            error_key = error_analysis["error_key"]
            
            # Get recovery strategy
            strategy = await self._get_recovery_strategy(error_analysis, context)
            
            result = None
            for step in strategy["steps"]:
                try:
                    if step == "fallback_parser":
                        # Try fallback parser
                        if context.get("parser_type") == ParserType.CUSTOM:
                            fallback_parser = await TreeSitterParser.create(
                                context["language_id"],
                                context["file_type"]
                            )
                            result = await fallback_parser.parse(context["source_code"])
                    elif step == "basic_features":
                        # Extract basic features
                        result = await self._extract_basic_features(context["source_code"])
                    
                    if result:
                        break
                except Exception as e:
                    await log(f"Recovery step {step} failed: {e}", level="warning")
                    continue
            
            recovery_time = time.time() - start_time
            success = result is not None
            
            # Update recovery stats
            await self._update_recovery_stats(
                error_key,
                strategy["name"],
                success,
                recovery_time
            )
            
            if success:
                await log(
                    f"Successfully recovered from {error_key} using strategy {strategy['name']}",
                    level="info",
                    context={
                        "recovery_time": recovery_time,
                        "strategy": strategy["name"]
                    }
                )
                return result
            else:
                await log(
                    f"Failed to recover from {error_key}",
                    level="warning",
                    context={
                        "recovery_time": recovery_time,
                        "strategy": strategy["name"]
                    }
                )
                return {}
                
        except Exception as e:
            await log(f"Error in recovery process: {e}", level="error")
            return {}

    async def get_recovery_performance_report(self) -> Dict[str, Any]:
        """Get a report of error recovery performance."""
        return {
            "error_patterns": self._error_patterns,
            "recovery_strategies": self._recovery_strategies,
            "top_performing_strategies": sorted(
                [
                    {
                        "error_type": error_key,
                        "strategy": strategy_name,
                        "success_rate": stats["success_rate"],
                        "avg_time": stats["avg_time"],
                        "uses": stats["uses"]
                    }
                    for error_key, strategies in self._recovery_strategies.items()
                    for strategy_name, stats in strategies.items()
                ],
                key=lambda x: x["success_rate"],
                reverse=True
            )[:10],
            "error_distribution": {
                error_key: stats["occurrences"]
                for error_key, stats in self._error_patterns.items()
            }
        }

    @cached_in_request
    async def parse(self, source_code: str, language_id: str, file_type: FileType):
        """Parse with request-level caching."""
        async with request_cache_context() as cache:
            # Check cache first
            cache_key = f"parse:{language_id}:{hash(source_code)}"
            cached_result = await self._ast_cache.get(cache_key)
            if cached_result:
                return cached_result
                
            # Parse and cache result
            result = await self._parse_impl(source_code, language_id, file_type)
            await self._ast_cache.set(cache_key, result)
            return result
    
    async def _parse_impl(self, source_code: str, language_id: str, file_type: FileType) -> Dict[str, Any]:
        """Parse source code using the appropriate parser."""
        if not self._initialized:
            await self.ensure_initialized()
        
        async with request_cache_context() as cache:
            try:
                # Get parser
                parser = await self.get_parser(language_id, file_type)
                
                # Get parser type for pattern loading
                parser_type, normalized_lang = await get_parser_type(language_id)
                
                # Create context for error recovery
                context = {
                    "language_id": language_id,
                    "file_type": file_type,
                    "parser_type": parser_type,
                    "source_code": source_code
                }
                
                # Parse source code with error recovery
                try:
                    ast = await parser.parse(source_code)
                except Exception as e:
                    # Log original error
                    await log(f"Primary parser failed for {language_id}: {e}", level="warning")
                    
                    # Attempt recovery
                    recovery_result = await self.recover_from_parsing_error(e, context)
                    if recovery_result:
                        ast = recovery_result
                    else:
                        raise ProcessingError(f"All parsing attempts failed for {language_id}")
                
                # Get pattern processor instance
                from parsers.pattern_processor import pattern_processor
                
                # Extract features with error recovery
                try:
                    features = await parser.extract_features(
                        ast,
                        source_code,
                        pattern_processor=pattern_processor,
                        parser_type=parser_type
                    )
                except Exception as e:
                    await log(f"Feature extraction failed: {e}", level="warning")
                    # Attempt recovery for feature extraction
                    recovery_result = await self.recover_from_parsing_error(
                        e,
                        {**context, "ast": ast}
                    )
                    features = recovery_result or await self._extract_basic_features(source_code)
                
                # Cache the result for this request
                result = {
                    "ast": ast,
                    "features": features,
                    "parser_type": parser_type.value,
                    "language_id": normalized_lang
                }
                await cache.set(f"parse_result:{language_id}:{hash(source_code)}", result)
                
                # Update health metrics
                await global_health_monitor.update_component_status(
                    "unified_parser",
                    ComponentStatus.HEALTHY,
                    details={
                        "language": language_id,
                        "parser_type": parser_type.value,
                        "features_extracted": len(features) if features else 0
                    }
                )
                
                return result
                
            except Exception as e:
                await log(f"Error parsing source code: {e}", level="error")
                # Update health status
                await global_health_monitor.update_component_status(
                    "unified_parser",
                    ComponentStatus.DEGRADED,
                    error=True,
                    details={
                        "language": language_id,
                        "error": str(e)
                    }
                )
                # Return minimal result instead of empty dict
                return {
                    "ast": {"type": "error", "error": str(e)},
                    "features": await self._extract_basic_features(source_code),
                    "parser_type": "unknown",
                    "language_id": language_id
                }
    
    async def _extract_basic_features(self, source_code: str) -> Dict[str, Any]:
        """Extract basic features when full parsing fails."""
        features = {}
        try:
            # Basic line counting
            lines = source_code.splitlines()
            features["lines"] = {
                "total": len(lines),
                "code": len([l for l in lines if l.strip() and not l.strip().startswith(('#', '//', '/*'))]),
                "comment": len([l for l in lines if l.strip() and l.strip().startswith(('#', '//', '/*'))]),
                "blank": len([l for l in lines if not l.strip()])
            }
            
            # Basic complexity estimation
            features["complexity"] = {
                "cyclomatic": len([l for l in lines if any(kw in l for kw in ['if', 'for', 'while', 'case'])]),
                "nesting": max([len(l) - len(l.lstrip()) for l in lines]) // 4 if lines else 0
            }
            
            return features
        except Exception as e:
            await log(f"Basic feature extraction failed: {e}", level="error")
            return {}
    
    async def cleanup(self):
        """Clean up unified parser resources."""
        try:
            if not self._initialized:
                return
                
            # Update status
            await global_health_monitor.update_component_status(
                "unified_parser",
                ComponentStatus.SHUTTING_DOWN,
                details={"stage": "starting"}
            )
            
            async with self._lock:
                # Clean up parsers
                for parser_key, parser in self._parsers.items():
                    try:
                        await parser.cleanup()
                    except Exception as e:
                        await log(f"Error cleaning up parser {parser_key}: {e}", level="error")
                self._parsers.clear()
                
                # Clean up cache
                if self._cache:
                    try:
                        await cache_coordinator.unregister_cache("unified_parser")
                        self._cache = None
                    except Exception as e:
                        await log(f"Error cleaning up cache: {e}", level="error")
                
                # Cancel pending tasks
                if self._pending_tasks:
                    for task in self._pending_tasks:
                        if not task.done():
                            task.cancel()
                    await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                    self._pending_tasks.clear()
            
            # Let async_runner handle remaining tasks
            cleanup_tasks()
            
            self._initialized = False
            await log("Unified parser cleaned up", level="info")
            
            # Update final status
            await global_health_monitor.update_component_status(
                "unified_parser",
                ComponentStatus.SHUTDOWN,
                details={"cleanup": "successful"}
            )
        except Exception as e:
            await log(f"Error cleaning up unified parser: {e}", level="error")
            await global_health_monitor.update_component_status(
                "unified_parser",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"cleanup_error": str(e)}
            )
            raise ProcessingError(f"Failed to cleanup unified parser: {e}")

    async def _cleanup_caches(self):
        """Clean up all caches."""
        await cache_coordinator.unregister_cache("unified_parser")
        await cache_coordinator.unregister_cache("unified_parser_ast")
        await cache_coordinator.unregister_cache("unified_parser_patterns")

# Create singleton instance
unified_parser = None

async def get_unified_parser() -> UnifiedParser:
    """Get or create the unified parser singleton instance."""
    global unified_parser
    if unified_parser is None:
        unified_parser = await UnifiedParser.create()
    return unified_parser

# Export public interfaces
__all__ = [
    'UnifiedParser',
    'get_unified_parser',
    'unified_parser'
] 