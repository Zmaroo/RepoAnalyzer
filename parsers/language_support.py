"""[1.0] Language support registry and utilities."""

from typing import Dict, Optional, Set, Tuple, List, Any
import asyncio
import os
from abc import ABC, abstractmethod
from parsers.parser_interfaces import BaseParserInterface, ParserRegistryInterface, AIParserInterface
from parsers.models import FileClassification, LanguageFeatures, FileMetadata
from parsers.types import (
    ParserType, FileType, AICapability, AIContext, AIProcessingResult,
    InteractionType, ConfidenceLevel
)
from parsers.language_mapping import (
    TREE_SITTER_LANGUAGES,
    CUSTOM_PARSER_LANGUAGES,
    normalize_language_name,
    get_parser_type,
    get_file_type,
    get_fallback_parser_type,
    get_language_features,
    get_suggested_alternatives,
    get_complete_language_info
)
from utils.logger import log
from utils.error_handling import AsyncErrorBoundary, ErrorSeverity, handle_async_errors, ProcessingError, ErrorAudit
from utils.shutdown import register_shutdown_handler
from utils.cache import UnifiedCache, cache_coordinator, cache_metrics
from utils.cache_analytics import get_cache_analytics, CacheAnalytics
from utils.request_cache import cached_in_request, request_cache_context, get_current_request_cache
from utils.health_monitor import global_health_monitor, ComponentStatus, monitor_operation
from db.transaction import transaction_scope
from dataclasses import dataclass, field
import time
import psutil

@dataclass
class ParserAvailability:
    """[1.1] Information about available parsers for a language."""
    has_custom_parser: bool
    has_tree_sitter: bool
    preferred_type: ParserType
    file_type: FileType
    fallback_type: Optional[ParserType] = None
    ai_capabilities: Set[AICapability] = field(default_factory=set)

async def get_parser_availability(language: str) -> ParserAvailability:
    """[1.2] Get information about available parsers for a language."""
    normalized = await normalize_language_name(language)
    
    # Get comprehensive language info
    language_info = await get_complete_language_info(normalized)
    
    # Import here to avoid circular imports
    from parsers.custom_parsers import CUSTOM_PARSER_CLASSES
    
    has_custom = normalized in CUSTOM_PARSER_CLASSES
    has_tree_sitter = language_info["tree_sitter_available"]
    
    return ParserAvailability(
        has_custom_parser=has_custom,
        has_tree_sitter=has_tree_sitter,
        preferred_type=language_info["parser_type"],
        file_type=language_info["file_type"],
        fallback_type=language_info.get("fallback_parser_type"),
        ai_capabilities=language_info["ai_capabilities"]
    )

async def get_language_by_extension(file_path: str) -> Optional[LanguageFeatures]:
    """Get language features for a file extension or path."""
    basename = os.path.basename(file_path)
    
    async with AsyncErrorBoundary(f"get_language_for_path_{basename}", error_types=(Exception,)):
        # Use the language mapping module to detect language
        from parsers.language_mapping import detect_language_from_filename
        language = await detect_language_from_filename(basename)
        
        if language:
            return await get_language_features(language)
    
    return None

async def get_extensions_for_language(language: str) -> Set[str]:
    """Get all file extensions associated with a language."""
    async with AsyncErrorBoundary(f"get_extensions_for_{language}", error_types=(Exception,)):
        from parsers.language_mapping import get_extensions_for_language as get_exts
        return get_exts(language)
    
    return set()

class LanguageRegistry(ParserRegistryInterface):
    """[1.3] Registry for language parsers."""
    
    def __init__(self):
        self._parsers: Dict[str, BaseParserInterface] = {}
        self._fallback_parsers: Dict[str, BaseParserInterface] = {}
        self._ai_parsers: Dict[str, AIParserInterface] = {}
        self._initialized = False
        self._pending_tasks: Set[asyncio.Task] = set()
        self._cache = None
        self._warmup_complete = False
        self._metrics = {
            "total_registrations": 0,
            "successful_registrations": 0,
            "failed_registrations": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "registration_times": []
        }
        register_shutdown_handler(self.cleanup)
    
    @handle_async_errors(error_types=(Exception,))
    async def initialize(self):
        """[1.3.1] Initialize language registry resources."""
        if not self._initialized:
            try:
                async with AsyncErrorBoundary("language registry initialization"):
                    # Initialize cache
                    self._cache = UnifiedCache("language_registry")
                    await cache_coordinator.register_cache(self._cache)
                    
                    # Initialize cache analytics
                    analytics = await get_cache_analytics()
                    analytics.register_warmup_function(
                        "language_registry",
                        self._warmup_cache
                    )
                    await analytics.optimize_ttl_values()
                    
                    # Initialize error analysis
                    await ErrorAudit.analyze_codebase(os.path.dirname(__file__))
                    
                    # Register with health monitor
                    global_health_monitor.register_component(
                        "language_registry",
                        health_check=self._check_health
                    )
                    
                    # Start warmup task
                    warmup_task = asyncio.create_task(self._warmup_caches())
                    self._pending_tasks.add(warmup_task)
                    
                    # Initialize parsers for commonly used languages
                    common_languages = {"python", "javascript", "typescript", "java", "cpp"}
                    for language in common_languages:
                        if language in TREE_SITTER_LANGUAGES or language in CUSTOM_PARSER_LANGUAGES:
                            parser_info = get_parser_info_for_language(language)
                            classification = FileClassification(
                                language_id=language,
                                parser_type=parser_info["parser_type"],
                                file_type=parser_info["file_type"]
                            )
                            task = asyncio.create_task(self._create_parser(
                                language, 
                                classification.parser_type,
                                classification.file_type
                            ))
                            self._pending_tasks.add(task)
                            try:
                                parser = await task
                                if parser:
                                    self._parsers[language] = parser
                                    # Initialize AI parser if supported
                                    if isinstance(parser, AIParserInterface):
                                        self._ai_parsers[language] = parser
                            finally:
                                self._pending_tasks.remove(task)
                    
                    self._initialized = True
                    log("Language registry initialized", level="info")
            except Exception as e:
                log(f"Error initializing language registry: {e}", level="error")
                raise

    async def _warmup_caches(self):
        """Warm up caches with frequently used languages."""
        try:
            # Get frequently used languages
            async with transaction_scope() as txn:
                languages = await txn.fetch("""
                    SELECT language_id, usage_count
                    FROM language_usage_stats
                    WHERE usage_count > 10
                    ORDER BY usage_count DESC
                    LIMIT 100
                """)
                
                # Warm up language cache
                for language in languages:
                    await self._warmup_cache([language["language_id"]])
                    
            self._warmup_complete = True
            await log("Language registry cache warmup complete", level="info")
        except Exception as e:
            await log(f"Error warming up caches: {e}", level="error")

    async def _warmup_cache(self, keys: List[str]) -> Dict[str, Any]:
        """Warmup function for language registry cache."""
        results = {}
        for key in keys:
            try:
                language = await self._get_language_info(key)
                if language:
                    results[key] = language
            except Exception as e:
                await log(f"Error warming up language {key}: {e}", level="warning")
        return results

    async def _check_health(self) -> Dict[str, Any]:
        """Health check for language registry."""
        # Get error audit data
        error_report = await ErrorAudit.get_error_report()
        
        # Get cache analytics
        analytics = await get_cache_analytics()
        cache_stats = await analytics.get_metrics()
        
        # Get resource usage
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        
        # Calculate average registration time
        avg_registration_time = sum(self._metrics["registration_times"]) / len(self._metrics["registration_times"]) if self._metrics["registration_times"] else 0
        
        # Calculate health status
        status = ComponentStatus.HEALTHY
        details = {
            "metrics": {
                "total_registrations": self._metrics["total_registrations"],
                "success_rate": self._metrics["successful_registrations"] / self._metrics["total_registrations"] if self._metrics["total_registrations"] > 0 else 0,
                "cache_hit_rate": self._metrics["cache_hits"] / (self._metrics["cache_hits"] + self._metrics["cache_misses"]) if (self._metrics["cache_hits"] + self._metrics["cache_misses"]) > 0 else 0,
                "avg_registration_time": avg_registration_time
            },
            "cache_stats": {
                "hit_rates": cache_stats.get("hit_rates", {}),
                "memory_usage": cache_stats.get("memory_usage", {}),
                "eviction_rates": cache_stats.get("eviction_rates", {})
            },
            "error_stats": {
                "total_errors": error_report.get("total_errors", 0),
                "error_rate": error_report.get("error_rate", 0),
                "top_errors": error_report.get("top_error_locations", [])[:3]
            },
            "resource_usage": {
                "memory_rss": memory_info.rss,
                "memory_vms": memory_info.vms,
                "cpu_percent": process.cpu_percent(),
                "thread_count": len(process.threads())
            },
            "warmup_status": {
                "complete": self._warmup_complete,
                "cache_ready": self._warmup_complete and self._cache is not None
            }
        }
        
        # Check for degraded conditions
        if details["metrics"]["success_rate"] < 0.8:  # Less than 80% success rate
            status = ComponentStatus.DEGRADED
            details["reason"] = "Low registration success rate"
        elif error_report.get("error_rate", 0) > 0.1:  # More than 10% error rate
            status = ComponentStatus.DEGRADED
            details["reason"] = "High error rate"
        elif details["resource_usage"]["cpu_percent"] > 80:  # High CPU usage
            status = ComponentStatus.DEGRADED
            details["reason"] = "High CPU usage"
        elif avg_registration_time > 1.0:  # Average registration time > 1 second
            status = ComponentStatus.DEGRADED
            details["reason"] = "High registration times"
        elif not self._warmup_complete:  # Cache not ready
            status = ComponentStatus.DEGRADED
            details["reason"] = "Cache warmup incomplete"
            
        return {
            "status": status,
            "details": details
        }

    async def cleanup(self):
        """[1.3.5] Clean up language registry resources."""
        try:
            if not self._initialized:
                return
                
            # Clean up all parsers
            for parser in self._parsers.values():
                await parser.cleanup()
            self._parsers.clear()
            
            # Clean up fallback parsers
            for parser in self._fallback_parsers.values():
                await parser.cleanup()
            self._fallback_parsers.clear()
            
            # Clean up AI parsers (may overlap with other parsers)
            self._ai_parsers.clear()
            
            # Clean up cache
            if self._cache:
                await self._cache.clear_async()
                await cache_coordinator.unregister_cache("language_registry")
            
            # Save error analysis
            await ErrorAudit.save_report()
            
            # Save cache analytics
            analytics = await get_cache_analytics()
            await analytics.save_metrics_history(self._cache.get_metrics())
            
            # Save metrics to database
            async with transaction_scope() as txn:
                await txn.execute("""
                    INSERT INTO language_registry_metrics (
                        timestamp, total_registrations,
                        successful_registrations, failed_registrations,
                        cache_hits, cache_misses, avg_registration_time
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                """, (
                    time.time(),
                    self._metrics["total_registrations"],
                    self._metrics["successful_registrations"],
                    self._metrics["failed_registrations"],
                    self._metrics["cache_hits"],
                    self._metrics["cache_misses"],
                    sum(self._metrics["registration_times"]) / len(self._metrics["registration_times"]) if self._metrics["registration_times"] else 0
                ))
            
            # Cancel all pending tasks
            if self._pending_tasks:
                for task in self._pending_tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                self._pending_tasks.clear()
            
            # Unregister from health monitor
            global_health_monitor.unregister_component("language_registry")
            
            self._initialized = False
            log("Language registry cleaned up", level="info")
        except Exception as e:
            log(f"Error cleaning up language registry: {e}", level="error")
            raise ProcessingError(f"Failed to cleanup language registry: {e}")

    @handle_async_errors(error_types=(Exception,))
    async def get_parser(self, classification: FileClassification) -> Optional[BaseParserInterface]:
        """[1.3.2] Get the appropriate parser for a file classification."""
        if not self._initialized:
            await self.initialize()
            
        language = classification.language_id
        
        async with AsyncErrorBoundary(f"get_parser_{language}", error_types=(Exception,)):
            # Try to get an existing parser first
            if language in self._parsers:
                return self._parsers.get(language)
                
            # Create a parser if it doesn't exist
            task = asyncio.create_task(self._create_parser(
                language, 
                classification.parser_type,
                classification.file_type
            ))
            self._pending_tasks.add(task)
            try:
                parser = await task
                if parser:
                    self._parsers[language] = parser
                    # Initialize AI parser if supported
                    if isinstance(parser, AIParserInterface):
                        self._ai_parsers[language] = parser
                    return parser
            finally:
                self._pending_tasks.remove(task)
            
            # If no parser could be created with specified type, try fallback
            parser_info = get_parser_info_for_language(language)
            fallback_type = parser_info.get("fallback_parser_type")
            
            if fallback_type not in [ParserType.UNKNOWN, None]:
                # Check if we already have a fallback parser
                fallback_key = f"{language}_{fallback_type.name}"
                if fallback_key in self._fallback_parsers:
                    return self._fallback_parsers[fallback_key]
                    
                # Try to create a fallback parser
                task = asyncio.create_task(self._create_parser(
                    language,
                    fallback_type,
                    classification.file_type
                ))
                self._pending_tasks.add(task)
                try:
                    fallback_parser = await task
                    if fallback_parser:
                        self._fallback_parsers[fallback_key] = fallback_parser
                        # Initialize AI parser if supported
                        if isinstance(fallback_parser, AIParserInterface):
                            self._ai_parsers[f"{language}_fallback"] = fallback_parser
                        log(f"Using fallback parser type {fallback_type} for {language}", level="info")
                        return fallback_parser
                finally:
                    self._pending_tasks.remove(task)
            
            # Try language alternatives as last resort
            for alt_language in get_suggested_alternatives(language):
                alt_parser_info = get_parser_info_for_language(alt_language)
                task = asyncio.create_task(self.get_parser(FileClassification(
                    file_path=classification.file_path,
                    language_id=alt_language,
                    parser_type=alt_parser_info["parser_type"],
                    file_type=alt_parser_info["file_type"]
                )))
                self._pending_tasks.add(task)
                try:
                    alt_parser = await task
                    if alt_parser:
                        log(f"Using alternative language {alt_language} parser for {language}", level="info")
                        return alt_parser
                finally:
                    self._pending_tasks.remove(task)
        
        return None

    async def get_ai_parser(self, language: str) -> Optional[AIParserInterface]:
        """[1.3.3] Get an AI-capable parser for a language."""
        if not self._initialized:
            await self.initialize()
            
        # Check if we already have an AI parser for this language
        if language in self._ai_parsers:
            return self._ai_parsers[language]
            
        # Try to get a regular parser and check if it supports AI
        parser_info = get_parser_info_for_language(language)
        classification = FileClassification(
            language_id=language,
            parser_type=parser_info["parser_type"],
            file_type=parser_info["file_type"]
        )
        
        parser = await self.get_parser(classification)
        if isinstance(parser, AIParserInterface):
            self._ai_parsers[language] = parser
            return parser
            
        return None

    async def process_with_ai(
        self,
        language: str,
        source_code: str,
        context: AIContext
    ) -> AIProcessingResult:
        """[1.3.4] Process source code with AI assistance."""
        parser = await self.get_ai_parser(language)
        if not parser:
            return AIProcessingResult(
                success=False,
                response=f"No AI-capable parser available for {language}"
            )
            
        return await parser.process_with_ai(source_code, context)

    async def _create_parser(self, language: str, parser_type: ParserType, file_type: FileType) -> Optional[BaseParserInterface]:
        """Create a new parser instance of the specified type."""
        async with AsyncErrorBoundary(f"create_parser_{language}_{parser_type.name}", error_types=(Exception,)):
            # Import here to avoid circular imports
            from parsers.tree_sitter_parser import TreeSitterParser
            from parsers.custom_parsers import CUSTOM_PARSER_CLASSES
            
            # Use the new parser info function to make decisions
            parser_info = get_parser_info_for_language(language)
            
            # Always prioritize custom parsers for languages that have them
            if parser_info.get("custom_parser_available", False):
                parser_cls = CUSTOM_PARSER_CLASSES.get(language)
                if parser_cls:
                    log(f"Using custom parser for {language} (prioritized over tree-sitter)", level="debug")
                    parser = parser_cls(language, file_type)
                    await parser.initialize()
                    return parser
            
            # If no custom parser or not a custom parser language, follow the requested type
            if parser_type == ParserType.TREE_SITTER and parser_info.get("tree_sitter_available", False):
                parser = TreeSitterParser(language, file_type)
                await parser.initialize()
                return parser
            elif parser_type == ParserType.CUSTOM and language in CUSTOM_PARSER_CLASSES:
                parser_cls = CUSTOM_PARSER_CLASSES.get(language)
                if parser_cls:
                    parser = parser_cls(language, file_type)
                    await parser.initialize()
                    return parser
        
        return None

    def get_supported_languages(self) -> Dict[str, ParserType]:
        """Get all supported languages and their parser types."""
        from parsers.language_mapping import get_supported_languages as get_langs
        return get_langs()

# Global instance
language_registry = LanguageRegistry() 

class AIParserInterface(ABC):
    """Abstract base class for AI-capable parsers."""
    
    @abstractmethod
    async def process_deep_learning(
        self,
        source_code: str,
        context: AIContext,
        repositories: List[int]
    ) -> AIProcessingResult:
        """Process with deep learning capabilities."""
        pass

    @abstractmethod
    async def learn_from_repositories(
        self,
        repo_ids: List[int]
    ) -> Dict[str, Any]:
        """Learn patterns from multiple repositories."""
        pass 