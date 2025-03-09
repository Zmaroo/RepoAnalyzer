"""Language support utilities for RepoAnalyzer.

This module provides utilities for managing language support, including
language detection, normalization, and parser selection.
"""

from typing import Dict, Any, List, Optional, Union, Set
import asyncio
from tree_sitter_language_pack import get_binding, get_language, get_parser, SupportedLanguage
from parsers.types import (
    FileType, FeatureCategory, ParserType, Documentation, ComplexityMetrics,
    ExtractedFeatures, PatternCategory, PatternPurpose,
    AICapability, AIContext, AIProcessingResult, InteractionType, ConfidenceLevel
)
from parsers.models import QueryResult, FileClassification, PATTERN_CATEGORIES
from parsers.language_mapping import normalize_language_name
from parsers.custom_parsers import CUSTOM_PARSER_CLASSES
from utils.logger import log
from utils.error_handling import AsyncErrorBoundary, handle_async_errors, ProcessingError
from utils.shutdown import register_shutdown_handler
from utils.cache import UnifiedCache, cache_coordinator, get_current_request_cache
from utils.health_monitor import ComponentStatus, global_health_monitor
from utils.async_runner import submit_async_task, cleanup_tasks
import time
import psutil
import statistics
from dataclasses import dataclass, field

@dataclass
class LanguageHealthMetrics:
    """Health metrics for language support."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    avg_response_time: float = 0.0
    response_times: List[float] = field(default_factory=list)
    error_counts: Dict[str, int] = field(default_factory=dict)
    parser_stats: Dict[str, Dict[str, Any]] = field(default_factory=dict)

class LanguageSupport:
    """Language support manager."""
    
    def __init__(self):
        """Initialize language support."""
        self._initialized = False
        self._cache = None
        self._lock = asyncio.Lock()
        self._health_metrics = LanguageHealthMetrics()
        self._health_check_interval = 300  # 5 minutes
        self._last_health_check = time.time()
        self._health_thresholds = {
            "error_rate": 0.1,  # 10% error rate threshold
            "response_time": 1.0,  # 1 second response time threshold
            "cache_hit_rate": 0.7  # 70% cache hit rate threshold
        }
        register_shutdown_handler(self.cleanup)
    
    async def ensure_initialized(self):
        """Ensure the language support is initialized."""
        if not self._initialized:
            raise ProcessingError("Language support not initialized. Use create() to initialize.")
        return True
    
    @classmethod
    async def create(cls) -> 'LanguageSupport':
        """Create and initialize a language support instance."""
        instance = cls()
        try:
            async with AsyncErrorBoundary("language_support_initialization"):
                # Initialize health monitoring first
                await global_health_monitor.update_component_status(
                    "language_support",
                    ComponentStatus.INITIALIZING,
                    details={"stage": "starting"}
                )
                
                # Initialize cache
                instance._cache = UnifiedCache("language_support")
                await cache_coordinator.register_cache(instance._cache)
                
                # Register shutdown handler
                register_shutdown_handler(instance.cleanup)
                
                instance._initialized = True
                await log("Language support initialized", level="info")
                
                # Update final health status
                await global_health_monitor.update_component_status(
                    "language_support",
                    ComponentStatus.HEALTHY,
                    details={"stage": "complete"}
                )
                
                return instance
        except Exception as e:
            await log(f"Error initializing language support: {e}", level="error")
            await global_health_monitor.update_component_status(
                "language_support",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"initialization_error": str(e)}
            )
            # Cleanup on initialization failure
            cleanup_task = submit_async_task(instance.cleanup())
            await asyncio.wrap_future(cleanup_task)
            raise ProcessingError(f"Failed to initialize language support: {e}")
    
    async def get_supported_languages(self) -> Set[str]:
        """Get all supported languages."""
        if not self._initialized:
            await self.ensure_initialized()
        
        # Check cache first
        cache_key = "supported_languages"
        cached_languages = await self._cache.get(cache_key)
        if cached_languages:
            return set(cached_languages)
        
        # Get languages from tree-sitter and custom parsers
        languages = set(SupportedLanguage.__args__) | set(CUSTOM_PARSER_CLASSES.keys())
        
        # Cache languages
        await self._cache.set(cache_key, list(languages))
        
        return languages
    
    async def get_parser_type(self, language_id: str) -> ParserType:
        """Get parser type for a language."""
        if not self._initialized:
            await self.ensure_initialized()
        
        async with self._lock:
            # Check request cache first
            request_cache = get_current_request_cache()
            if request_cache:
                cache_key = f"parser_type:{language_id}"
                cached_type = await request_cache.get(cache_key)
                if cached_type:
                    return ParserType(cached_type)
            
            # Check global cache
            cache_key = f"parser_type:{language_id}"
            cached_type = await self._cache.get(cache_key)
            if cached_type:
                # Store in request cache if available
                if request_cache:
                    await request_cache.set(cache_key, cached_type)
                return ParserType(cached_type)
            
            # Normalize language ID
            normalized = normalize_language_name(language_id)
            
            # Check custom parsers first
            if normalized in CUSTOM_PARSER_CLASSES:
                parser_type = ParserType.CUSTOM
            # Then check tree-sitter support
            elif normalized in SupportedLanguage.__args__:
                parser_type = ParserType.TREE_SITTER
            else:
                parser_type = ParserType.UNKNOWN
            
            # Cache parser type
            await self._cache.set(cache_key, parser_type.value)
            if request_cache:
                await request_cache.set(cache_key, parser_type.value)
            
            return parser_type
    
    async def get_file_type(self, language_id: str) -> FileType:
        """Get file type for a language."""
        if not self._initialized:
            await self.ensure_initialized()
        
        # Check cache first
        cache_key = f"file_type:{language_id}"
        cached_type = await self._cache.get(cache_key)
        if cached_type:
            return FileType(cached_type)
        
        # Normalize language ID
        normalized = normalize_language_name(language_id)
        
        # Default to CODE for supported languages
        if normalized in CUSTOM_PARSER_CLASSES or normalized in SupportedLanguage.__args__:
            file_type = FileType.CODE
        else:
            file_type = FileType.UNKNOWN
        
        # Cache file type
        await self._cache.set(cache_key, file_type.value)
        
        return file_type
    
    async def get_ai_capabilities(self, language_id: str) -> Set[AICapability]:
        """Get AI capabilities for a language."""
        if not self._initialized:
            await self.ensure_initialized()
        
        # Check cache first
        cache_key = f"ai_capabilities:{language_id}"
        cached_capabilities = await self._cache.get(cache_key)
        if cached_capabilities:
            return {AICapability(c) for c in cached_capabilities}
        
        # Normalize language ID
        normalized = normalize_language_name(language_id)
        
        # Get capabilities based on parser type
        parser_type = await self.get_parser_type(normalized)
        
        if parser_type == ParserType.CUSTOM:
            capabilities = {
                AICapability.CODE_UNDERSTANDING,
                AICapability.CODE_GENERATION,
                AICapability.CODE_MODIFICATION,
                AICapability.CODE_REVIEW,
                AICapability.DOCUMENTATION,
                AICapability.LEARNING
            }
        elif parser_type == ParserType.TREE_SITTER:
            capabilities = {
                AICapability.CODE_UNDERSTANDING,
                AICapability.CODE_GENERATION,
                AICapability.CODE_MODIFICATION,
                AICapability.CODE_REVIEW,
                AICapability.DOCUMENTATION
            }
        else:
            capabilities = set()
        
        # Cache capabilities
        await self._cache.set(cache_key, [c.value for c in capabilities])
        
        return capabilities
    
    async def _check_health(self) -> Dict[str, Any]:
        """Comprehensive health check of language support system."""
        try:
            current_time = time.time()
            
            # Only run health check at configured intervals
            if current_time - self._last_health_check < self._health_check_interval:
                return self._last_health_status
                
            self._last_health_check = current_time
            
            # Calculate metrics
            total_requests = self._health_metrics.total_requests
            if total_requests > 0:
                error_rate = self._health_metrics.failed_requests / total_requests
                success_rate = self._health_metrics.successful_requests / total_requests
                cache_hit_rate = (
                    self._health_metrics.cache_hits /
                    (self._health_metrics.cache_hits + self._health_metrics.cache_misses)
                    if (self._health_metrics.cache_hits + self._health_metrics.cache_misses) > 0
                    else 0
                )
            else:
                error_rate = success_rate = cache_hit_rate = 0
            
            # Get memory usage
            process = psutil.Process()
            memory_info = process.memory_info()
            
            # Check parser health
            parser_health = {}
            for language_id, stats in self._health_metrics.parser_stats.items():
                parser_type = await self.get_parser_type(language_id)
                parser_health[language_id] = {
                    "type": parser_type.value,
                    "status": "healthy" if stats.get("error_rate", 0) < self._health_thresholds["error_rate"] else "degraded",
                    "error_rate": stats.get("error_rate", 0),
                    "avg_response_time": stats.get("avg_response_time", 0)
                }
            
            # Determine overall status
            status = ComponentStatus.HEALTHY
            status_reasons = []
            
            if error_rate > self._health_thresholds["error_rate"]:
                status = ComponentStatus.DEGRADED
                status_reasons.append(f"High error rate: {error_rate:.2%}")
            
            if (self._health_metrics.response_times and
                statistics.mean(self._health_metrics.response_times) > self._health_thresholds["response_time"]):
                status = ComponentStatus.DEGRADED
                status_reasons.append("Slow response times")
            
            if cache_hit_rate < self._health_thresholds["cache_hit_rate"]:
                status = ComponentStatus.DEGRADED
                status_reasons.append(f"Low cache hit rate: {cache_hit_rate:.2%}")
            
            # Create health report
            health_report = {
                "status": status.value,
                "timestamp": current_time,
                "metrics": {
                    "total_requests": total_requests,
                    "error_rate": error_rate,
                    "success_rate": success_rate,
                    "cache_hit_rate": cache_hit_rate,
                    "avg_response_time": statistics.mean(self._health_metrics.response_times) if self._health_metrics.response_times else 0,
                    "memory_usage": memory_info.rss
                },
                "parser_health": parser_health,
                "status_reasons": status_reasons,
                "error_distribution": dict(self._health_metrics.error_counts)
            }
            
            # Store last health status
            self._last_health_status = health_report
            
            # Update global health monitor
            await global_health_monitor.update_component_status(
                "language_support",
                status,
                details=health_report
            )
            
            return health_report
            
        except Exception as e:
            await log(f"Error in health check: {e}", level="error")
            return {
                "status": ComponentStatus.UNHEALTHY.value,
                "error": str(e),
                "timestamp": time.time()
            }

    async def _update_health_metrics(
        self,
        success: bool,
        response_time: float,
        language_id: Optional[str] = None,
        error: Optional[Exception] = None
    ) -> None:
        """Update health metrics."""
        try:
            self._health_metrics.total_requests += 1
            if success:
                self._health_metrics.successful_requests += 1
            else:
                self._health_metrics.failed_requests += 1
                if error:
                    error_type = type(error).__name__
                    self._health_metrics.error_counts[error_type] = (
                        self._health_metrics.error_counts.get(error_type, 0) + 1
                    )
            
            self._health_metrics.response_times.append(response_time)
            self._health_metrics.avg_response_time = (
                sum(self._health_metrics.response_times) /
                len(self._health_metrics.response_times)
            )
            
            if language_id:
                if language_id not in self._health_metrics.parser_stats:
                    self._health_metrics.parser_stats[language_id] = {
                        "total_requests": 0,
                        "successful_requests": 0,
                        "failed_requests": 0,
                        "response_times": []
                    }
                
                stats = self._health_metrics.parser_stats[language_id]
                stats["total_requests"] += 1
                if success:
                    stats["successful_requests"] += 1
                else:
                    stats["failed_requests"] += 1
                stats["response_times"].append(response_time)
                stats["avg_response_time"] = (
                    sum(stats["response_times"]) /
                    len(stats["response_times"])
                )
                stats["error_rate"] = (
                    stats["failed_requests"] /
                    stats["total_requests"]
                )
            
        except Exception as e:
            await log(f"Error updating health metrics: {e}", level="error")

    async def cleanup(self):
        """Clean up language support resources."""
        try:
            if not self._initialized:
                return
                
            # Update status
            await global_health_monitor.update_component_status(
                "language_support",
                ComponentStatus.SHUTTING_DOWN,
                details={"stage": "starting"}
            )
            
            # Clean up cache
            if self._cache:
                await cache_coordinator.unregister_cache("language_support")
                self._cache = None
            
            # Let async_runner handle remaining tasks
            cleanup_tasks()
            
            self._initialized = False
            await log("Language support cleaned up", level="info")
            
            # Update final status
            await global_health_monitor.update_component_status(
                "language_support",
                ComponentStatus.SHUTDOWN,
                details={"cleanup": "successful"}
            )
        except Exception as e:
            await log(f"Error cleaning up language support: {e}", level="error")
            await global_health_monitor.update_component_status(
                "language_support",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"cleanup_error": str(e)}
            )
            raise ProcessingError(f"Failed to cleanup language support: {e}")

# Create singleton instance
language_support = None

async def get_language_support() -> LanguageSupport:
    """Get or create the language support singleton instance."""
    global language_support
    if language_support is None:
        language_support = await LanguageSupport.create()
    return language_support

# Export public interfaces
__all__ = [
    'LanguageSupport',
    'get_language_support',
    'language_support'
] 