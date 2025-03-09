"""Feature extraction implementations.

This module provides feature extraction capabilities using tree-sitter-language-pack
and custom parsers. It extracts code features like syntax, semantics, and documentation.
"""

from typing import Dict, Any, List, Optional, Union, Generator, Tuple, Callable, TypeVar, cast, Awaitable, Set
import asyncio
from tree_sitter_language_pack import get_binding, get_language, get_parser, SupportedLanguage
from parsers.types import (
    FileType, FeatureCategory, ParserType, Documentation, ComplexityMetrics,
    ExtractedFeatures, PatternCategory, PatternPurpose,
    AICapability, AIContext, AIProcessingResult, InteractionType, ConfidenceLevel
)
from parsers.models import (
    QueryResult, FileClassification, PATTERN_CATEGORIES,
    Documentation, ComplexityMetrics
)
from parsers.language_mapping import normalize_language_name
from parsers.custom_parsers import CUSTOM_PARSER_CLASSES
from utils.logger import log
from utils.error_handling import (
    AsyncErrorBoundary, 
    handle_async_errors, 
    ProcessingError,
    ErrorSeverity,
    ErrorAudit
)
from utils.shutdown import register_shutdown_handler
from utils.cache import UnifiedCache, cache_coordinator
from utils.health_monitor import ComponentStatus, global_health_monitor
from utils.async_runner import submit_async_task, cleanup_tasks
from utils.request_cache import cached_in_request, request_cache_context, get_current_request_cache
from utils.cache_analytics import get_cache_analytics
from db.transaction import transaction_scope
import time
import psutil
from dataclasses import dataclass, field

@dataclass
class CacheStats:
    """Cache statistics."""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    memory_usage: int = 0
    avg_access_time: float = 0.0
    access_times: List[float] = field(default_factory=list)

class BaseFeatureExtractor:
    """Base class for feature extraction."""
    
    def __init__(self):
        """Private constructor - use create() instead."""
        self._initialized = False
        self._pending_tasks: Set[asyncio.Task] = set()
        self._cache = None
        self._lock = asyncio.Lock()
        self._metrics = {
            "total_features": 0,
            "successful_extractions": 0,
            "failed_extractions": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "extraction_times": []
        }
        self._warmup_complete = False
        self._pattern_usage_stats = {}
        self._pattern_success_rates = {}
        self._adaptive_thresholds = {}
        self._learning_enabled = True
        self._context_stats = {}
        self._pattern_context_success = {}
        self._context_learning_enabled = True
        self._cache_stats = CacheStats()
        self._cache_config = {
            "max_size": 1000,  # Maximum number of cached items
            "max_memory": 100 * 1024 * 1024,  # 100MB max memory usage
            "ttl": 3600,  # 1 hour TTL
            "cleanup_interval": 300  # 5 minutes cleanup interval
        }
        self._last_cleanup = time.time()
        self._last_health_check = time.time()
        self._health_check_interval = 300  # 5 minutes
        register_shutdown_handler(self.cleanup)
    
    @classmethod
    async def create(cls, language_id: str, file_type: FileType) -> 'BaseFeatureExtractor':
        """Async factory method to create and initialize a feature extractor instance."""
        instance = cls()
        instance.language_id = language_id
        instance.file_type = file_type
        
        try:
            async with AsyncErrorBoundary(
                operation_name=f"feature_extractor_initialization_{language_id}",
                error_types=(ProcessingError,),
                severity=ErrorSeverity.CRITICAL
            ):
                # Initialize health monitoring first
                await global_health_monitor.update_component_status(
                    f"feature_extractor_{language_id}",
                    ComponentStatus.INITIALIZING,
                    details={
                        "stage": "starting",
                        "language": language_id,
                        "file_type": file_type.value
                    }
                )
                
                # Initialize cache
                instance._cache = UnifiedCache(f"feature_extractor_{language_id}")
                await cache_coordinator.register_cache(instance._cache)
                
                # Initialize cache analytics
                analytics = await get_cache_analytics()
                analytics.register_warmup_function(
                    f"feature_extractor_{language_id}",
                    instance._warmup_cache
                )
                
                # Start warmup task
                warmup_task = submit_async_task(instance._warmup_caches())
                instance._pending_tasks.add(warmup_task)
                
                # Register with error audit
                await ErrorAudit.register_component(
                    f"feature_extractor_{language_id}",
                    error_types=[ProcessingError],
                    severity=ErrorSeverity.ERROR
                )
                
                instance._initialized = True
                await log(
                    f"Feature extractor initialized for {language_id}",
                    level="info",
                    context={
                        "language": language_id,
                        "file_type": file_type.value,
                        "cache_initialized": instance._cache is not None,
                        "warmup_started": warmup_task is not None
                    }
                )
                
                # Update final status
                await global_health_monitor.update_component_status(
                    f"feature_extractor_{language_id}",
                    ComponentStatus.HEALTHY,
                    details={
                        "stage": "complete",
                        "language": language_id,
                        "file_type": file_type.value,
                        "cache_ready": True,
                        "warmup_started": True
                    }
                )
                
                return instance
        except Exception as e:
            await log(f"Error initializing feature extractor for {language_id}: {e}", level="error")
            await ErrorAudit.record_error(
                e,
                f"feature_extractor_initialization_{language_id}",
                ProcessingError,
                severity=ErrorSeverity.CRITICAL,
                context={
                    "language": language_id,
                    "file_type": file_type.value
                }
            )
            await global_health_monitor.update_component_status(
                f"feature_extractor_{language_id}",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={
                    "initialization_error": str(e),
                    "language": language_id,
                    "file_type": file_type.value
                }
            )
            # Cleanup on initialization failure
            cleanup_task = submit_async_task(instance.cleanup())
            await asyncio.wrap_future(cleanup_task)
            raise ProcessingError(f"Failed to initialize feature extractor for {language_id}: {e}")
    
    async def _warmup_caches(self):
        """Warm up caches with frequently used patterns."""
        try:
            # Get frequently used patterns
            async with transaction_scope() as txn:
                patterns = await txn.fetch("""
                    SELECT pattern_name, usage_count
                    FROM feature_extraction_stats
                    WHERE usage_count > 10
                    ORDER BY usage_count DESC
                    LIMIT 100
                """)
                
                # Warm up pattern cache
                for pattern in patterns:
                    await self._warmup_cache([pattern["pattern_name"]])
                    
            self._warmup_complete = True
            await log(f"{self.language_id} feature extractor cache warmup complete", level="info")
        except Exception as e:
            await log(f"Error warming up caches: {e}", level="error")
    
    async def _warmup_cache(self, keys: List[str]) -> Dict[str, Any]:
        """Warmup function for feature extractor cache."""
        results = {}
        for key in keys:
            try:
                pattern = await self._get_pattern(key)
                if pattern:
                    results[key] = pattern
            except Exception as e:
                await log(f"Error warming up pattern {key}: {e}", level="warning")
        return results
    
    async def _check_health(self) -> Dict[str, Any]:
        """Health check for feature extractor."""
        current_time = time.time()
        
        # Only run health check at configured intervals
        if current_time - self._last_health_check < self._health_check_interval:
            return self._last_health_status
            
        self._last_health_check = current_time
        
        try:
            # Get error audit data
            error_report = await ErrorAudit.get_error_report()
            
            # Get cache analytics
            analytics = await get_cache_analytics()
            cache_stats = await analytics.get_metrics()
            
            # Calculate average extraction time
            avg_extraction_time = (
                sum(self._metrics["extraction_times"]) / len(self._metrics["extraction_times"])
                if self._metrics["extraction_times"] else 0
            )
            
            # Calculate success rate
            total_ops = (
                self._metrics["successful_extractions"] +
                self._metrics["failed_extractions"]
            )
            success_rate = (
                self._metrics["successful_extractions"] / total_ops
                if total_ops > 0 else 1.0
            )
            
            # Calculate cache hit rate
            total_cache_ops = (
                self._metrics["cache_hits"] +
                self._metrics["cache_misses"]
            )
            cache_hit_rate = (
                self._metrics["cache_hits"] / total_cache_ops
                if total_cache_ops > 0 else 1.0
            )
            
            # Get memory usage
            process = psutil.Process()
            memory_info = process.memory_info()
            
            # Calculate health status
            status = ComponentStatus.HEALTHY
            status_reasons = []
            
            if success_rate < 0.8:  # Less than 80% success rate
                status = ComponentStatus.DEGRADED
                status_reasons.append(f"Low extraction success rate: {success_rate:.2%}")
            
            if cache_hit_rate < 0.7:  # Less than 70% cache hit rate
                status = ComponentStatus.DEGRADED
                status_reasons.append(f"Low cache hit rate: {cache_hit_rate:.2%}")
            
            if avg_extraction_time > 1.0:  # Average extraction time > 1 second
                status = ComponentStatus.DEGRADED
                status_reasons.append(f"High average extraction time: {avg_extraction_time:.2f}s")
            
            if error_report.get("error_rate", 0) > 0.1:  # More than 10% error rate
                status = ComponentStatus.DEGRADED
                status_reasons.append(f"High error rate: {error_report.get('error_rate', 0):.2%}")
            
            # Create health report
            health_report = {
                "status": status.value,
                "timestamp": current_time,
                "metrics": {
                    "total_features": self._metrics["total_features"],
                    "success_rate": success_rate,
                    "cache_hit_rate": cache_hit_rate,
                    "avg_extraction_time": avg_extraction_time,
                    "memory_usage": memory_info.rss,
                    "cache_stats": cache_stats
                },
                "error_stats": {
                    "total_errors": error_report.get("total_errors", 0),
                    "error_rate": error_report.get("error_rate", 0),
                    "top_errors": error_report.get("top_error_locations", [])[:3]
                },
                "status_reasons": status_reasons,
                "warmup_status": {
                    "complete": self._warmup_complete,
                    "cache_ready": self._warmup_complete and self._cache is not None
                }
            }
            
            # Store last health status
            self._last_health_status = health_report
            
            # Update global health monitor
            await global_health_monitor.update_component_status(
                f"feature_extractor_{self.language_id}",
                status,
                details=health_report
            )
            
            return health_report
            
        except Exception as e:
            await log(f"Error in health check: {e}", level="error")
            await ErrorAudit.record_error(
                e,
                f"feature_extractor_health_check_{self.language_id}",
                ProcessingError,
                severity=ErrorSeverity.ERROR,
                context={"language": self.language_id}
            )
            return {
                "status": ComponentStatus.UNHEALTHY.value,
                "error": str(e),
                "timestamp": time.time()
            }

    async def _submit_task(self, coro) -> Any:
        """Submit a task with proper tracking."""
        task = submit_async_task(coro)
        self._pending_tasks.add(task)
        try:
            return await asyncio.wrap_future(task)
        finally:
            self._pending_tasks.remove(task)
            
    async def cleanup(self):
        """Clean up with proper task handling."""
        try:
            # Cancel all pending tasks
            if self._pending_tasks:
                for task in self._pending_tasks:
                    task.cancel()
                await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                self._pending_tasks.clear()
                
            # Clean up caches
            await self._cleanup_caches()
            
        except Exception as e:
            await log(f"Error cleaning up feature extractor: {e}", level="error")

    @cached_in_request
    async def _extract_category_features(
        self,
        category: FeatureCategory,
        ast: Dict[str, Any],
        source_code: str
    ) -> Dict[str, Any]:
        """Extract features for a specific category."""
        features = {}
        
        # Get pattern processor instance
        from parsers.pattern_processor import pattern_processor
        
        # Get patterns for this category
        patterns = await pattern_processor.get_patterns_for_category(
            category,
            PatternPurpose.UNDERSTANDING,
            self.language_id,
            self.parser_type
        )
        
        if patterns:
            for pattern in patterns:
                # Process pattern
                processed = await pattern_processor.process_pattern(
                    pattern["name"],
                    source_code,
                    self.language_id
                )
                
                if processed.matches:
                    features[pattern["name"]] = processed.matches
        
        return features

    @handle_async_errors(error_types=ProcessingError)
    async def extract_features(
        self,
        ast: Dict[str, Any],
        source_code: str,
        pattern_processor: Optional[Any] = None,
        parser_type: Optional[ParserType] = None
    ) -> ExtractedFeatures:
        """Extract features from AST and source code."""
        if not self._initialized:
            await self.ensure_initialized()
            
        start_time = time.time()
        
        # Get request context for metrics
        request_cache = get_current_request_cache()
        if request_cache:
            await request_cache.set(
                "feature_extraction_count",
                (await request_cache.get("feature_extraction_count", 0)) + 1
            )
        
        # Check file size limits
        MAX_FILE_SIZE = 1024 * 1024  # 1MB
        if len(source_code) > MAX_FILE_SIZE:
            await log(f"File size exceeds limit: {len(source_code)} bytes", level="warning")
            # Process in chunks
            return await self._extract_features_chunked(source_code, pattern_processor, parser_type)
        
        async with AsyncErrorBoundary(f"feature_extraction_{self.language_id}"):
            try:
                # Check cache first
                cache_key = f"features:{hash(source_code)}:{parser_type.value if parser_type else 'unknown'}"
                cached_result = await self._cache.get(cache_key)
                if cached_result:
                    self._metrics["cache_hits"] += 1
                    if request_cache:
                        await request_cache.set(
                            "feature_extraction_cache_hits",
                            (await request_cache.get("feature_extraction_cache_hits", 0)) + 1
                        )
                    return ExtractedFeatures(**cached_result)
                
                self._metrics["cache_misses"] += 1
                self._metrics["total_features"] += 1
                
                # Update status
                await global_health_monitor.update_component_status(
                    f"feature_extractor_{self.language_id}",
                    ComponentStatus.PROCESSING,
                    details={
                        "operation": "feature_extraction",
                        "source_size": len(source_code),
                        "parser_type": parser_type.value if parser_type else "unknown"
                    }
                )
                
                # Extract features by category with memory monitoring
                features = {}
                memory_usage = psutil.Process().memory_info().rss
                MAX_MEMORY = 1024 * 1024 * 1024  # 1GB
                
                async with request_cache_context() as cache:
                    for category in FeatureCategory:
                        # Check memory usage
                        current_memory = psutil.Process().memory_info().rss
                        if current_memory - memory_usage > MAX_MEMORY:
                            await log("Memory limit exceeded, stopping feature extraction", level="warning")
                            break
                        
                        # Get patterns based on parser type
                        if pattern_processor:
                            features[category] = await self._extract_features_with_learning(
                                category,
                                source_code,
                                pattern_processor,
                                parser_type or ParserType.UNKNOWN
                            )
                
                # Create documentation features
                documentation = await self._extract_documentation(
                    features.get(FeatureCategory.DOCUMENTATION, {})
                )
                
                # Calculate complexity metrics
                metrics = await self._calculate_metrics(
                    features.get(FeatureCategory.SYNTAX, {}),
                    source_code
                )
                
                # Create result
                result = ExtractedFeatures(
                    features=features,
                    documentation=documentation,
                    metrics=metrics
                )
                
                # Cache result
                await self._cache.set(cache_key, result.__dict__)
                
                # Update metrics
                self._metrics["successful_extractions"] += 1
                extraction_time = time.time() - start_time
                self._metrics["extraction_times"].append(extraction_time)
                
                # Track request-level metrics
                if request_cache:
                    extraction_metrics = {
                        "language_id": self.language_id,
                        "parser_type": parser_type.value if parser_type else "unknown",
                        "extraction_time": extraction_time,
                        "features_found": len(features),
                        "memory_used": current_memory - memory_usage,
                        "timestamp": time.time()
                    }
                    await request_cache.set(
                        f"extraction_metrics_{self.language_id}",
                        extraction_metrics
                    )
                
                # Update final status
                await global_health_monitor.update_component_status(
                    f"feature_extractor_{self.language_id}",
                    ComponentStatus.HEALTHY,
                    details={
                        "operation": "feature_extraction_complete",
                        "extraction_time": extraction_time,
                        "features_found": len(features),
                        "memory_used": current_memory - memory_usage,
                        "parser_type": parser_type.value if parser_type else "unknown"
                    }
                )
                
                return result
            except Exception as e:
                self._metrics["failed_extractions"] += 1
                extraction_time = time.time() - start_time
                
                # Track error in request context
                if request_cache:
                    await request_cache.set(
                        "last_extraction_error",
                        {
                            "error": str(e),
                            "language_id": self.language_id,
                            "parser_type": parser_type.value if parser_type else "unknown",
                            "timestamp": time.time()
                        }
                    )
                
                await log(f"Error extracting features for {self.language_id}: {e}", level="error")
                await global_health_monitor.update_component_status(
                    f"feature_extractor_{self.language_id}",
                    ComponentStatus.UNHEALTHY,
                    error=True,
                    details={
                        "operation": "feature_extraction",
                        "error": str(e),
                        "extraction_time": extraction_time,
                        "parser_type": parser_type.value if parser_type else "unknown"
                    }
                )
                
                # Get error recommendations
                recommendations = await ErrorAudit.get_standardization_recommendations()
                relevant_recs = [r for r in recommendations if r["location"] == "extract_features"]
                
                if relevant_recs:
                    await log(
                        "Error handling recommendations available",
                        level="warning",
                        context={"recommendations": relevant_recs}
                    )
                
                # Record error for audit
                await ErrorAudit.record_error(
                    e,
                    f"feature_extraction_{self.language_id}",
                    ProcessingError,
                    context={
                        "parser_type": parser_type.value if parser_type else "unknown",
                        "extraction_time": extraction_time,
                        "recommendations": relevant_recs
                    }
                )
                
                return ExtractedFeatures()

    async def _extract_documentation(self, features: Dict[str, Any]) -> Documentation:
        """Extract documentation features."""
        raise NotImplementedError("_extract_documentation must be implemented by subclasses")
    
    async def _calculate_metrics(self, features: Dict[str, Any], source_code: str) -> ComplexityMetrics:
        """Calculate code complexity metrics."""
        raise NotImplementedError("_calculate_metrics must be implemented by subclasses")

    @handle_async_errors(error_types=ProcessingError)
    async def _get_pattern(self, pattern_name: str) -> Optional[Dict[str, Any]]:
        """Get a pattern by name."""
        if not self._initialized:
            await self.ensure_initialized()
            
        try:
            # Check cache first
            cache_key = f"pattern:{self.language_id}:{pattern_name}"
            cached_pattern = await self._cache.get(cache_key)
            if cached_pattern:
                self._metrics["cache_hits"] += 1
                return cached_pattern
                
            self._metrics["cache_misses"] += 1
            
            # Load pattern from storage
            async with transaction_scope() as txn:
                # First try to get from main patterns table
                pattern = await txn.fetchrow("""
                    SELECT * FROM patterns
                    WHERE language_id = $1 AND pattern_name = $2
                """, self.language_id, pattern_name)
                
                if not pattern:
                    # Try custom patterns table
                    pattern = await txn.fetchrow("""
                        SELECT * FROM custom_patterns
                        WHERE language_id = $1 AND pattern_name = $2
                    """, self.language_id, pattern_name)
                    
                    if not pattern:
                        # Try tree-sitter patterns table
                        pattern = await txn.fetchrow("""
                            SELECT * FROM tree_sitter_patterns
                            WHERE language_id = $1 AND pattern_name = $2
                        """, self.language_id, pattern_name)
                
                if pattern:
                    # Convert to dict and add metadata
                    pattern_dict = dict(pattern)
                    pattern_dict["metadata"] = {
                        "source": pattern.get("source", "unknown"),
                        "last_updated": pattern.get("last_updated"),
                        "usage_count": pattern.get("usage_count", 0)
                    }
                    
                    # Cache pattern
                    await self._cache.set(cache_key, pattern_dict)
                    
                    # Update usage count
                    await txn.execute("""
                        UPDATE patterns
                        SET usage_count = usage_count + 1,
                            last_used = NOW()
                        WHERE language_id = $1 AND pattern_name = $2
                    """, self.language_id, pattern_name)
                    
                    return pattern_dict
                    
            return None
            
        except Exception as e:
            await log(f"Error getting pattern {pattern_name}: {e}", level="error")
            await ErrorAudit.record_error(
                e,
                f"pattern_loading_{self.language_id}",
                ProcessingError,
                context={
                    "pattern_name": pattern_name,
                    "language_id": self.language_id
                }
            )
            return None

    async def _extract_features_chunked(
        self,
        source_code: str,
        pattern_processor: Optional[Any] = None,
        parser_type: Optional[ParserType] = None
    ) -> ExtractedFeatures:
        """Extract features from large files by processing in chunks."""
        CHUNK_SIZE = 100 * 1024  # 100KB chunks
        features = {}
        
        # Split source code into chunks
        chunks = [source_code[i:i + CHUNK_SIZE] 
                 for i in range(0, len(source_code), CHUNK_SIZE)]
        
        for i, chunk in enumerate(chunks):
            try:
                # Process each chunk
                chunk_features = await self._extract_chunk_features(
                    chunk,
                    pattern_processor,
                    parser_type,
                    chunk_index=i
                )
                
                # Merge features
                for category, category_features in chunk_features.items():
                    if category not in features:
                        features[category] = {}
                    features[category].update(category_features)
                    
            except Exception as e:
                await log(f"Error processing chunk {i}: {e}", level="warning")
                continue
        
        # Create final result
        documentation = await self._extract_documentation(
            features.get(FeatureCategory.DOCUMENTATION, {})
        )
        
        metrics = await self._calculate_metrics(
            features.get(FeatureCategory.SYNTAX, {}),
            source_code
        )
        
        return ExtractedFeatures(
            features=features,
            documentation=documentation,
            metrics=metrics
        )

    async def _extract_chunk_features(
        self,
        chunk: str,
        pattern_processor: Optional[Any],
        parser_type: Optional[ParserType],
        chunk_index: int
    ) -> Dict[str, Any]:
        """Extract features from a single chunk of source code."""
        features = {}
        
        if pattern_processor:
            for category in FeatureCategory:
                patterns = await pattern_processor.get_patterns_for_category(
                    category,
                    PatternPurpose.UNDERSTANDING,
                    self.language_id,
                    parser_type or ParserType.UNKNOWN
                )
                
                category_features = {}
                for pattern in patterns:
                    try:
                        if parser_type == ParserType.TREE_SITTER:
                            processed = await pattern_processor._process_tree_sitter_pattern(
                                pattern,
                                chunk,
                                self.language_id
                            )
                        else:
                            processed = await pattern_processor._process_custom_pattern(
                                pattern,
                                chunk,
                                self.language_id
                            )
                        
                        if processed.matches:
                            # Adjust match positions for chunk index
                            for match in processed.matches:
                                if "start" in match:
                                    match["start"] += chunk_index * len(chunk)
                                if "end" in match:
                                    match["end"] += chunk_index * len(chunk)
                            category_features[pattern["name"]] = processed.matches
                            
                    except Exception as e:
                        await log(f"Error processing pattern in chunk {chunk_index}: {e}", level="warning")
                        continue
                
                if category_features:
                    features[category] = category_features
        
        return features

    async def _update_pattern_stats(
        self,
        pattern_name: str,
        success: bool,
        extraction_time: float,
        features_found: int
    ) -> None:
        """Update pattern usage statistics for learning."""
        if not self._learning_enabled:
            return
            
        if pattern_name not in self._pattern_usage_stats:
            self._pattern_usage_stats[pattern_name] = {
                "uses": 0,
                "successes": 0,
                "failures": 0,
                "avg_time": 0.0,
                "features_found": 0
            }
        
        stats = self._pattern_usage_stats[pattern_name]
        stats["uses"] += 1
        if success:
            stats["successes"] += 1
        else:
            stats["failures"] += 1
        
        # Update moving averages
        stats["avg_time"] = (stats["avg_time"] * (stats["uses"] - 1) + extraction_time) / stats["uses"]
        stats["features_found"] = (stats["features_found"] * (stats["uses"] - 1) + features_found) / stats["uses"]
        
        # Update success rate
        self._pattern_success_rates[pattern_name] = stats["successes"] / stats["uses"]
        
        # Adjust thresholds based on pattern performance
        if stats["uses"] > 100:  # Wait for sufficient data
            if self._pattern_success_rates[pattern_name] < 0.3:  # Low success rate
                self._adaptive_thresholds[pattern_name] = {
                    "max_time": stats["avg_time"] * 0.8,  # Reduce time allowance
                    "min_features": stats["features_found"] * 1.2  # Require more features
                }
            elif self._pattern_success_rates[pattern_name] > 0.8:  # High success rate
                self._adaptive_thresholds[pattern_name] = {
                    "max_time": stats["avg_time"] * 1.2,  # Allow more time
                    "min_features": stats["features_found"] * 0.8  # Accept fewer features
                }

    async def _should_use_pattern(self, pattern_name: str) -> bool:
        """Determine if a pattern should be used based on its performance."""
        if not self._learning_enabled or pattern_name not in self._pattern_success_rates:
            return True
            
        success_rate = self._pattern_success_rates[pattern_name]
        if success_rate < 0.2:  # Very poor performance
            return False
            
        return True

    async def _analyze_code_context(self, source_code: str) -> Dict[str, Any]:
        """Analyze code context for pattern selection."""
        context = {
            "size": len(source_code),
            "complexity": 0,
            "patterns": set(),
            "imports": set(),
            "declarations": set(),
            "style": None
        }
        
        try:
            lines = source_code.splitlines()
            
            # Basic complexity estimation
            context["complexity"] = len([l for l in lines if any(kw in l for kw in [
                'if', 'for', 'while', 'class', 'def', 'switch', 'case'
            ])])
            
            # Extract imports
            context["imports"] = {
                line.split()[1].split('.')[0]
                for line in lines 
                if line.strip().startswith(('import', 'from')) and ' ' in line
            }
            
            # Detect code style
            indentation = [len(line) - len(line.lstrip()) for line in lines if line.strip()]
            if indentation:
                common_indent = max(set(indentation), key=indentation.count)
                context["style"] = {
                    "indentation": common_indent,
                    "uses_spaces": ' ' in lines[0] if lines else True
                }
            
            # Extract declarations
            context["declarations"] = {
                line.split()[1].split('(')[0]
                for line in lines
                if line.strip().startswith(('def', 'class', 'async def'))
            }
            
            return context
        except Exception as e:
            await log(f"Error analyzing code context: {e}", level="warning")
            return context

    async def _select_patterns_for_context(
        self,
        code_context: Dict[str, Any],
        available_patterns: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Select most appropriate patterns based on code context."""
        if not self._context_learning_enabled:
            return available_patterns
            
        selected_patterns = []
        context_key = f"{self.language_id}:{code_context['complexity']}:{len(code_context['imports'])}"
        
        for pattern in available_patterns:
            pattern_name = pattern["name"]
            
            # Skip patterns that consistently fail for this context
            if context_key in self._pattern_context_success:
                success_rate = self._pattern_context_success[context_key].get(pattern_name, 1.0)
                if success_rate < 0.2:  # Very poor performance in this context
                    continue
            
            # Prioritize patterns based on context
            score = 0
            
            # Size-based scoring
            if code_context["size"] < 1000:  # Small files
                if pattern.get("optimized_for_small_files", False):
                    score += 2
            else:  # Large files
                if pattern.get("optimized_for_large_files", False):
                    score += 2
            
            # Complexity-based scoring
            if code_context["complexity"] > 10:  # Complex code
                if pattern.get("handles_complexity", False):
                    score += 2
            
            # Import-based scoring
            pattern_imports = set(pattern.get("relevant_imports", []))
            if pattern_imports & code_context["imports"]:
                score += len(pattern_imports & code_context["imports"])
            
            # Declaration-based scoring
            if any(decl in pattern.get("relevant_declarations", []) 
                  for decl in code_context["declarations"]):
                score += 1
            
            # Historical performance scoring
            if context_key in self._pattern_context_success:
                success_rate = self._pattern_context_success[context_key].get(pattern_name, 0.5)
                score += success_rate * 3
            
            pattern["context_score"] = score
            selected_patterns.append(pattern)
        
        # Sort by score and return top patterns
        return sorted(selected_patterns, key=lambda p: p["context_score"], reverse=True)

    async def _update_context_stats(
        self,
        context_key: str,
        pattern_name: str,
        success: bool,
        extraction_time: float
    ) -> None:
        """Update pattern performance statistics for specific contexts."""
        if not self._context_learning_enabled:
            return
            
        if context_key not in self._context_stats:
            self._context_stats[context_key] = {
                "total_uses": 0,
                "patterns": {}
            }
        
        stats = self._context_stats[context_key]
        stats["total_uses"] += 1
        
        if pattern_name not in stats["patterns"]:
            stats["patterns"][pattern_name] = {
                "uses": 0,
                "successes": 0,
                "avg_time": 0.0
            }
        
        pattern_stats = stats["patterns"][pattern_name]
        pattern_stats["uses"] += 1
        if success:
            pattern_stats["successes"] += 1
        
        # Update moving average for extraction time
        pattern_stats["avg_time"] = (
            (pattern_stats["avg_time"] * (pattern_stats["uses"] - 1) + extraction_time)
            / pattern_stats["uses"]
        )
        
        # Update success rate for context
        if context_key not in self._pattern_context_success:
            self._pattern_context_success[context_key] = {}
        
        self._pattern_context_success[context_key][pattern_name] = (
            pattern_stats["successes"] / pattern_stats["uses"]
        )

    async def _extract_features_with_learning(
        self,
        category: FeatureCategory,
        source_code: str,
        pattern_processor: Any,
        parser_type: Optional[ParserType]
    ) -> Dict[str, Any]:
        """Extract features with pattern learning and adaptation."""
        features = {}
        
        # Analyze code context
        code_context = await self._analyze_code_context(source_code)
        context_key = f"{self.language_id}:{code_context['complexity']}:{len(code_context['imports'])}"
        
        # Get and prioritize patterns
        patterns = await pattern_processor.get_patterns_for_category(
            category,
            PatternPurpose.UNDERSTANDING,
            self.language_id,
            parser_type or ParserType.UNKNOWN
        )
        
        prioritized_patterns = await self._select_patterns_for_context(code_context, patterns)
        
        for pattern in prioritized_patterns:
            pattern_name = pattern["name"]
            
            # Check if pattern should be used
            if not await self._should_use_pattern(pattern_name):
                continue
            
            start_time = time.time()
            try:
                # Process pattern with timeout based on adaptive thresholds
                timeout = self._adaptive_thresholds.get(
                    pattern_name, 
                    {"max_time": 5.0}  # Default timeout
                )["max_time"]
                
                async with asyncio.timeout(timeout):
                    if parser_type == ParserType.TREE_SITTER:
                        processed = await pattern_processor._process_tree_sitter_pattern(
                            pattern,
                            source_code,
                            self.language_id
                        )
                    else:
                        processed = await pattern_processor._process_custom_pattern(
                            pattern,
                            source_code,
                            self.language_id
                        )
                
                extraction_time = time.time() - start_time
                
                if processed.matches:
                    features[pattern_name] = processed.matches
                    # Update pattern stats with success
                    await self._update_pattern_stats(
                        pattern_name,
                        True,
                        extraction_time,
                        len(processed.matches)
                    )
                    # Update context stats
                    await self._update_context_stats(
                        context_key,
                        pattern_name,
                        True,
                        extraction_time
                    )
                    
            except Exception as e:
                extraction_time = time.time() - start_time
                # Update pattern stats with failure
                await self._update_pattern_stats(
                    pattern_name,
                    False,
                    extraction_time,
                    0
                )
                # Update context stats
                await self._update_context_stats(
                    context_key,
                    pattern_name,
                    False,
                    extraction_time
                )
                await log(f"Error processing pattern {pattern_name}: {e}", level="warning")
                continue
        
        return features

    async def get_context_performance_report(self) -> Dict[str, Any]:
        """Get a report of pattern performance in different contexts."""
        return {
            "context_stats": self._context_stats,
            "pattern_context_success": self._pattern_context_success,
            "contexts_analyzed": len(self._context_stats),
            "top_performing_contexts": sorted(
                [
                    {
                        "context": context,
                        "total_uses": stats["total_uses"],
                        "avg_success_rate": sum(
                            p["successes"] / p["uses"] 
                            for p in stats["patterns"].values()
                        ) / len(stats["patterns"]) if stats["patterns"] else 0
                    }
                    for context, stats in self._context_stats.items()
                ],
                key=lambda x: x["avg_success_rate"],
                reverse=True
            )[:10]
        }

    async def _cleanup_cache(self) -> None:
        """Clean up expired cache entries and manage memory usage."""
        try:
            current_time = time.time()
            
            # Only run cleanup at configured intervals
            if current_time - self._last_cleanup < self._cache_config["cleanup_interval"]:
                return
                
            self._last_cleanup = current_time
            
            # Get current memory usage
            process = psutil.Process()
            memory_info = process.memory_info()
            
            # Check if we need to clean up
            if (len(self._cache) > self._cache_config["max_size"] or
                memory_info.rss > self._cache_config["max_memory"]):
                
                # Sort entries by last access time
                sorted_entries = sorted(
                    self._cache.items(),
                    key=lambda x: x[1].get("last_access", 0)
                )
                
                # Remove oldest entries until we're under limits
                while (len(self._cache) > self._cache_config["max_size"] or
                       memory_info.rss > self._cache_config["max_memory"]):
                    if not sorted_entries:
                        break
                    key, _ = sorted_entries.pop(0)
                    await self._cache.delete(key)
                    self._cache_stats.evictions += 1
                    
                    # Update memory info
                    memory_info = process.memory_info()
            
            # Remove expired entries
            expired_keys = []
            async for key, value in self._cache.items():
                if current_time - value.get("timestamp", 0) > self._cache_config["ttl"]:
                    expired_keys.append(key)
            
            for key in expired_keys:
                await self._cache.delete(key)
                self._cache_stats.evictions += 1
            
            # Update cache stats
            self._cache_stats.memory_usage = memory_info.rss
            
        except Exception as e:
            await log(f"Error in cache cleanup: {e}", level="error")

    async def _get_from_cache(self, key: str) -> Optional[Dict[str, Any]]:
        """Get item from cache with stats tracking."""
        start_time = time.time()
        try:
            value = await self._cache.get(key)
            access_time = time.time() - start_time
            
            if value:
                self._cache_stats.hits += 1
                self._cache_stats.access_times.append(access_time)
                # Update access time
                value["last_access"] = time.time()
                await self._cache.set(key, value)
            else:
                self._cache_stats.misses += 1
            
            # Update average access time
            if self._cache_stats.access_times:
                self._cache_stats.avg_access_time = (
                    sum(self._cache_stats.access_times) /
                    len(self._cache_stats.access_times)
                )
            
            return value.get("data") if value else None
            
        except Exception as e:
            await log(f"Error getting from cache: {e}", level="error")
            return None

    async def _store_in_cache(self, key: str, value: Dict[str, Any]) -> None:
        """Store item in cache with metadata."""
        try:
            # Check if we need cleanup
            await self._cleanup_cache()
            
            # Store with metadata
            await self._cache.set(key, {
                "data": value,
                "timestamp": time.time(),
                "last_access": time.time(),
                "size": len(str(value))  # Rough size estimate
            })
            
        except Exception as e:
            await log(f"Error storing in cache: {e}", level="error")

    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "hits": self._cache_stats.hits,
            "misses": self._cache_stats.misses,
            "hit_rate": (
                self._cache_stats.hits /
                (self._cache_stats.hits + self._cache_stats.misses)
                if (self._cache_stats.hits + self._cache_stats.misses) > 0
                else 0
            ),
            "evictions": self._cache_stats.evictions,
            "memory_usage": self._cache_stats.memory_usage,
            "avg_access_time": self._cache_stats.avg_access_time,
            "cache_size": len(self._cache) if self._cache else 0,
            "config": self._cache_config
        }

class TreeSitterFeatureExtractor(BaseFeatureExtractor):
    """Tree-sitter specific feature extraction."""
    
    def __init__(self):
        """Private constructor - use create() instead."""
        super().__init__()
        self._parser = None
        self._language = None
    
    @classmethod
    async def create(cls, language_id: str, file_type: FileType) -> 'TreeSitterFeatureExtractor':
        """Async factory method to create and initialize a tree-sitter feature extractor."""
        instance = await super().create(language_id, file_type)
        
        try:
            async with AsyncErrorBoundary(f"tree_sitter_initialization_{language_id}"):
                # Check if language is supported
                if language_id not in SupportedLanguage.__args__:
                    raise ValueError(f"Language {language_id} not supported by tree-sitter-language-pack")
                
                # Initialize tree-sitter components
                instance._parser = get_parser(language_id)
                instance._language = get_language(language_id)
                
                if not instance._parser or not instance._language:
                    raise ValueError(f"Failed to initialize parser/language for {language_id}")
                
                await log(f"Tree-sitter components initialized for {language_id}", level="info")
                return instance
                
        except Exception as e:
            await log(f"Error initializing tree-sitter components: {e}", level="error")
            await global_health_monitor.update_component_status(
                f"feature_extractor_{language_id}",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"tree_sitter_error": str(e)}
            )
            # Cleanup on initialization failure
            cleanup_task = submit_async_task(instance.cleanup())
            await asyncio.wrap_future(cleanup_task)
            raise ProcessingError(f"Failed to initialize tree-sitter components for {language_id}: {e}")

    async def _extract_documentation(self, features: Dict[str, Any]) -> Documentation:
        """Extract documentation features using tree-sitter."""
        doc_features = features.get(PatternCategory.DOCUMENTATION.value, {})
        
        # Initialize Documentation object
        documentation = Documentation()
        
        # Extract docstrings
        if 'docstring' in doc_features:
            documentation.docstrings = doc_features['docstring']
            
            # Combine docstring content
            for doc in documentation.docstrings:
                if 'text' in doc:
                    documentation.content += doc['text'] + "\n"
        
        # Extract comments
        if 'comment' in doc_features:
            documentation.comments = doc_features['comment']
        
        # Extract TODOs
        for comment_type in ['todo', 'fixme', 'note', 'warning']:
            if comment_type in doc_features:
                documentation.todos.extend(doc_features[comment_type])
        
        # Extract metadata
        if 'metadata' in doc_features:
            documentation.metadata = {
                item.get('key', ''): item.get('value', '')
                for item in doc_features.get('metadata', [])
                if 'key' in item and 'value' in item
            }
            
        return documentation
    
    async def _calculate_metrics(self, features: Dict[str, Any], source_code: str) -> ComplexityMetrics:
        """Calculate code complexity metrics using tree-sitter."""
        metrics = ComplexityMetrics()
        
        # Count lines of code
        lines = source_code.splitlines()
        metrics.lines_of_code = {
            'total': len(lines),
            'code': len([l for l in lines if l.strip() and not l.strip().startswith(('#', '//', '/*', '*', '"""', "'''"))]),
            'comment': len([l for l in lines if l.strip() and l.strip().startswith(('#', '//', '/*', '*', '"""', "'''"))]),
            'blank': len([l for l in lines if not l.strip()])
        }
        
        # Calculate cyclomatic complexity
        branch_count = 0
        for branch_type in ['if', 'for', 'while', 'case', 'switch']:
            if branch_type in features:
                branch_count += len(features[branch_type])
        
        metrics.cyclomatic = branch_count + 1
        metrics.cognitive = branch_count
        
        return metrics

class CustomFeatureExtractor(BaseFeatureExtractor):
    """Custom parser feature extraction."""
    
    def __init__(self):
        """Private constructor - use create() instead."""
        super().__init__()
        self._parser = None
    
    @classmethod
    async def create(cls, language_id: str, file_type: FileType) -> 'CustomFeatureExtractor':
        """Async factory method to create and initialize a custom feature extractor."""
        instance = await super().create(language_id, file_type)
        
        try:
            async with AsyncErrorBoundary(f"custom_parser_initialization_{language_id}"):
                # Check if language has custom parser
                if language_id not in CUSTOM_PARSER_CLASSES:
                    raise ValueError(f"No custom parser available for {language_id}")
                
                # Initialize custom parser
                parser_class = CUSTOM_PARSER_CLASSES[language_id]
                instance._parser = parser_class()
                
                await log(f"Custom parser initialized for {language_id}", level="info")
                return instance
                
        except Exception as e:
            await log(f"Error initializing custom parser: {e}", level="error")
            await global_health_monitor.update_component_status(
                f"feature_extractor_{language_id}",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"custom_parser_error": str(e)}
            )
            # Cleanup on initialization failure
            cleanup_task = submit_async_task(instance.cleanup())
            await asyncio.wrap_future(cleanup_task)
            raise ProcessingError(f"Failed to initialize custom parser for {language_id}: {e}")

    @handle_async_errors(error_types=ProcessingError)
    async def _get_pattern(self, pattern_name: str) -> Optional[Dict[str, Any]]:
        """Get a pattern by name."""
        if not self._initialized:
            await self.ensure_initialized()
            
        try:
            # Check cache first
            cache_key = f"pattern:{self.language_id}:{pattern_name}"
            cached_pattern = await self._cache.get(cache_key)
            if cached_pattern:
                self._metrics["cache_hits"] += 1
                return cached_pattern
                
            self._metrics["cache_misses"] += 1
            
            # Load pattern from storage
            async with transaction_scope() as txn:
                # First try to get from main patterns table
                pattern = await txn.fetchrow("""
                    SELECT * FROM patterns
                    WHERE language_id = $1 AND pattern_name = $2
                """, self.language_id, pattern_name)
                
                if not pattern:
                    # Try custom patterns table
                    pattern = await txn.fetchrow("""
                        SELECT * FROM custom_patterns
                        WHERE language_id = $1 AND pattern_name = $2
                    """, self.language_id, pattern_name)
                    
                    if not pattern:
                        # Try tree-sitter patterns table
                        pattern = await txn.fetchrow("""
                            SELECT * FROM tree_sitter_patterns
                            WHERE language_id = $1 AND pattern_name = $2
                        """, self.language_id, pattern_name)
                
                if pattern:
                    # Convert to dict and add metadata
                    pattern_dict = dict(pattern)
                    pattern_dict["metadata"] = {
                        "source": pattern.get("source", "unknown"),
                        "last_updated": pattern.get("last_updated"),
                        "usage_count": pattern.get("usage_count", 0)
                    }
                    
                    # Cache pattern
                    await self._cache.set(cache_key, pattern_dict)
                    
                    # Update usage count
                    await txn.execute("""
                        UPDATE patterns
                        SET usage_count = usage_count + 1,
                            last_used = NOW()
                        WHERE language_id = $1 AND pattern_name = $2
                    """, self.language_id, pattern_name)
                    
                    return pattern_dict
                    
            return None
            
        except Exception as e:
            await log(f"Error getting pattern {pattern_name}: {e}", level="error")
            await ErrorAudit.record_error(
                e,
                f"pattern_loading_{self.language_id}",
                ProcessingError,
                context={
                    "pattern_name": pattern_name,
                    "language_id": self.language_id
                }
            )
            return None

    async def _extract_documentation(self, features: Dict[str, Any]) -> Documentation:
        """Extract documentation features using custom parser."""
        doc_features = features.get(PatternCategory.DOCUMENTATION.value, {})
        
        # Initialize Documentation object
        documentation = Documentation()
        
        # Extract docstrings
        if 'docstring' in doc_features:
            documentation.docstrings = doc_features['docstring']
            
            # Combine docstring content
            for doc in documentation.docstrings:
                if 'text' in doc:
                    documentation.content += doc['text'] + "\n"
        
        # Extract comments
        if 'comment' in doc_features:
            documentation.comments = doc_features['comment']
        
        # Extract TODOs
        for comment_type in ['todo', 'fixme', 'note', 'warning']:
            if comment_type in doc_features:
                documentation.todos.extend(doc_features[comment_type])
        
        # Extract metadata
        if 'metadata' in doc_features:
            documentation.metadata = {
                item.get('key', ''): item.get('value', '')
                for item in doc_features.get('metadata', [])
                if 'key' in item and 'value' in item
            }
            
        return documentation
    
    async def _calculate_metrics(self, features: Dict[str, Any], source_code: str) -> ComplexityMetrics:
        """Calculate code complexity metrics using custom parser."""
        metrics = ComplexityMetrics()
        
        # Count lines of code
        lines = source_code.splitlines()
        metrics.lines_of_code = {
            'total': len(lines),
            'code': len([l for l in lines if l.strip() and not l.strip().startswith(('#', '//', '/*', '*', '"""', "'''"))]),
            'comment': len([l for l in lines if l.strip() and l.strip().startswith(('#', '//', '/*', '*', '"""', "'''"))]),
            'blank': len([l for l in lines if not l.strip()])
        }
        
        # Calculate cyclomatic complexity
        branch_count = 0
        for branch_type in ['if', 'for', 'while', 'case', 'switch']:
            if branch_type in features:
                branch_count += len(features[branch_type])
        
        metrics.cyclomatic = branch_count + 1
        metrics.cognitive = branch_count
        
        return metrics

# Export public interfaces
__all__ = [
    'BaseFeatureExtractor',
    'TreeSitterFeatureExtractor',
    'CustomFeatureExtractor'
]