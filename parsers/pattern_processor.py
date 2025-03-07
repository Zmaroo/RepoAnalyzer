"""[6.0] Pattern processing and validation.

This module provides pattern processing capabilities for code analysis and manipulation.
Core pattern processing functionality separated from AI capabilities.
"""

from typing import Dict, Any, List, Union, Optional, Set, Tuple
from dataclasses import dataclass, field
import asyncio
import re
import time
import numpy as np
from parsers.types import (
    ParserType, PatternCategory, PatternPurpose, FileType, 
    PatternDefinition, QueryPattern, AIContext, 
    AIProcessingResult, PatternType, PatternRelationType
)
from parsers.models import (
    PatternMatch, PATTERN_CATEGORIES, ProcessedPattern, 
    QueryResult, PatternRelationship
)
from parsers.parser_interfaces import AIParserInterface
from utils.logger import log
from utils.error_handling import (
    handle_async_errors,
    AsyncErrorBoundary,
    ProcessingError,
    ErrorAudit,
    ErrorSeverity
)
from utils.cache import UnifiedCache, cache_coordinator, cache_metrics
from utils.cache_analytics import get_cache_analytics, CacheAnalytics
from utils.request_cache import cached_in_request, request_cache_context, get_current_request_cache
from utils.shutdown import register_shutdown_handler
from db.pattern_storage import PatternStorageMetrics
from db.transaction import transaction_scope
from ai_tools.pattern_integration import PatternLearningMetrics
from utils.health_monitor import global_health_monitor, ComponentStatus, monitor_operation
import traceback
import os
import psutil

class PatternProcessor(AIParserInterface):
    """Core pattern processing system."""
    
    def __init__(self):
        """Initialize pattern processor."""
        super().__init__(
            language_id="pattern_processor",
            file_type=FileType.CODE,
            capabilities=set()  # Core processor doesn't have AI capabilities
        )
        self._initialized = False
        self._pending_tasks: Set[asyncio.Task] = set()
        self._pattern_cache = None
        self._validation_cache = None
        self._metrics = PatternStorageMetrics()
        self._learning_metrics = PatternLearningMetrics()
        self._processing_stats = {
            "total_patterns": 0,
            "matched_patterns": 0,
            "failed_patterns": 0,
            "validation_stats": {
                "total_validations": 0,
                "cache_hits": 0,
                "successful_validations": 0,
                "failed_validations": 0,
                "validation_errors": {}  # Track common validation errors
            }
        }
        self._lock = asyncio.Lock()
        self._validation_ttl = 300  # 5 minutes cache TTL
        self._warmup_complete = False

    @classmethod
    async def create(cls) -> 'PatternProcessor':
        """Create and initialize a pattern processor instance."""
        instance = cls()
        await instance.initialize()
        return instance

    async def initialize(self) -> bool:
        """Initialize the pattern processor."""
        if self._initialized:
            return True

        try:
            async with AsyncErrorBoundary("pattern_processor_initialization"):
                # Initialize caches with analytics
                self._pattern_cache = UnifiedCache("pattern_processor_patterns", ttl=3600)
                self._validation_cache = UnifiedCache("pattern_processor_validation", ttl=self._validation_ttl)
                
                # Register caches with coordinator
                await cache_coordinator.register_cache("pattern_processor_patterns", self._pattern_cache)
                await cache_coordinator.register_cache("pattern_processor_validation", self._validation_cache)
                
                # Initialize cache analytics
                analytics = await get_cache_analytics()
                analytics.register_warmup_function(
                    "pattern_processor_patterns",
                    self._warmup_pattern_cache
                )
                
                # Enable cache optimization
                await analytics.optimize_ttl_values()
                
                # Register with health monitor
                global_health_monitor.register_component(
                    "pattern_processor",
                    health_check=self._check_health
                )
                
                # Initialize error analysis
                await ErrorAudit.analyze_codebase(os.path.dirname(__file__))
                
                # Register shutdown handler
                register_shutdown_handler(self.cleanup)
                
                # Start warmup task
                warmup_task = asyncio.create_task(self._warmup_caches())
                self._pending_tasks.add(warmup_task)
                
                self._initialized = True
                await log("Pattern processor initialized", level="info")
                return True
        except Exception as e:
            await log(f"Error initializing pattern processor: {e}", level="error")
            return False

    async def _warmup_caches(self):
        """Warm up caches with frequently used patterns."""
        try:
            # Get frequently used patterns
            async with transaction_scope() as txn:
                patterns = await txn.fetch("""
                    SELECT pattern_name, usage_count
                    FROM pattern_usage_stats
                    WHERE usage_count > 10
                    ORDER BY usage_count DESC
                    LIMIT 100
                """)
                
                # Warm up pattern cache
                for pattern in patterns:
                    await self._warmup_pattern_cache([pattern["pattern_name"]])
                    
            self._warmup_complete = True
            await log("Pattern cache warmup complete", level="info")
        except Exception as e:
            await log(f"Error warming up caches: {e}", level="error")

    async def _warmup_pattern_cache(self, keys: List[str]) -> Dict[str, Any]:
        """Warmup function for pattern cache."""
        results = {}
        for key in keys:
            try:
                pattern = await self._get_pattern(key, None)
                if pattern:
                    results[key] = pattern
            except Exception as e:
                await log(f"Error warming up pattern {key}: {e}", level="warning")
        return results

    async def process_pattern(
        self,
        pattern_name: str,
        source_code: str,
        language_id: str
    ) -> ProcessedPattern:
        """Process a single pattern against source code."""
        if not self._initialized:
            await self.initialize()

        try:
            async with self._lock:
                # Check cache first
                cache_key = f"{pattern_name}:{language_id}:{hash(source_code)}"
                cached_result = await self._pattern_cache.get(cache_key)
                if cached_result:
                    return ProcessedPattern(**cached_result)

                pattern = await self._get_pattern(pattern_name, language_id)
                if not pattern:
                    raise ProcessingError(f"Pattern {pattern_name} not found")

                matches = await self._process_pattern_internal(source_code, pattern)
                
                result = ProcessedPattern(
                    pattern_name=pattern_name,
                    matches=matches,
                    category=pattern.category,
                    purpose=pattern.purpose
                )

                # Cache result
                await self._pattern_cache.set(cache_key, result.__dict__)
                
                self._processing_stats["total_patterns"] += 1
                if matches:
                    self._processing_stats["matched_patterns"] += 1
                
                return result

        except Exception as e:
            self._processing_stats["failed_patterns"] += 1
            await log(f"Error processing pattern {pattern_name}: {e}", level="error")
            return ProcessedPattern(
                pattern_name=pattern_name,
                error=str(e)
            )

    async def process_for_purpose(
        self,
        source_code: str,
        purpose: PatternPurpose,
        file_type: FileType = FileType.CODE,
        categories: Optional[List[PatternCategory]] = None
    ) -> List[ProcessedPattern]:
        """Process patterns for a specific purpose."""
        if not self._initialized:
            await self.initialize()
        
        results = []
        if categories is None:
            categories = self._get_relevant_categories(purpose)
        
        for category in categories:
            patterns = await self._get_patterns_for_category(category, purpose)
            category_results = await self._process_category_patterns(
                source_code, patterns, category, purpose, file_type
            )
            results.extend(category_results)
        
        return results

    async def _process_pattern_internal(
        self,
        source_code: str,
        pattern: QueryPattern
    ) -> List[PatternMatch]:
        """Internal pattern processing implementation."""
        start_time = time.time()
        matches = []

        try:
            if pattern.tree_sitter:
                matches = await self._process_tree_sitter_pattern(source_code, pattern)
            elif pattern.regex:
                matches = await self._process_regex_pattern(source_code, pattern)

            execution_time = time.time() - start_time
            await self._track_metrics(pattern.pattern_name, execution_time, len(matches))
            
            return matches

        except Exception as e:
            await log(f"Error in pattern processing: {e}", level="error")
            return []

    def _get_relevant_categories(self, purpose: PatternPurpose) -> List[PatternCategory]:
        """Get relevant categories based on purpose."""
        purpose_category_map = {
            PatternPurpose.UNDERSTANDING: [
                PatternCategory.SYNTAX,
                PatternCategory.SEMANTICS,
                PatternCategory.CONTEXT,
                PatternCategory.DEPENDENCIES
            ],
            PatternPurpose.MODIFICATION: [
                PatternCategory.CODE_PATTERNS,
                PatternCategory.BEST_PRACTICES,
                PatternCategory.USER_PATTERNS
            ],
            PatternPurpose.VALIDATION: [
                PatternCategory.COMMON_ISSUES,
                PatternCategory.BEST_PRACTICES
            ],
            PatternPurpose.LEARNING: [
                PatternCategory.LEARNING,
                PatternCategory.USER_PATTERNS
            ]
        }
        return purpose_category_map.get(purpose, list(PatternCategory))

    async def _track_metrics(
        self,
        pattern_name: str,
        execution_time: float,
        match_count: int
    ) -> None:
        """Track pattern processing metrics."""
        async with transaction_scope() as txn:
            await self._metrics.track_pattern_execution(
                pattern_name,
                execution_time,
                match_count
            )

    def get_metrics(self) -> Dict[str, Any]:
        """Get pattern processing metrics."""
        return {
            "storage": self._metrics.__dict__,
            "learning": self._learning_metrics.__dict__,
            "processing": self._processing_stats
        }

    def reset_metrics(self) -> None:
        """Reset all metrics."""
        self._metrics = PatternStorageMetrics()
        self._learning_metrics = PatternLearningMetrics()
        self._processing_stats = {
            "total_patterns": 0,
            "matched_patterns": 0,
            "failed_patterns": 0
        }

    async def _check_health(self) -> Dict[str, Any]:
        """Health check for pattern processor."""
        stats = await self.get_validation_stats()
        metrics = self.get_metrics()
        
        # Get error audit data
        error_report = await ErrorAudit.get_error_report()
        
        # Get cache analytics
        analytics = await get_cache_analytics()
        cache_stats = await analytics.get_metrics()
        
        # Get resource usage
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        
        # Calculate health status
        status = ComponentStatus.HEALTHY
        details = {
            "validation_success_rate": stats.get("success_rate", 0),
            "cache_hit_rate": stats.get("cache_hit_rate", 0),
            "total_patterns": metrics["processing"]["total_patterns"],
            "failed_patterns": metrics["processing"]["failed_patterns"],
            "pattern_cache_size": await self._pattern_cache.size() if self._pattern_cache else 0,
            "validation_cache_size": await self._validation_cache.size() if self._validation_cache else 0,
            "error_stats": {
                "total_errors": error_report.get("total_errors", 0),
                "error_rate": error_report.get("error_rate", 0),
                "top_errors": error_report.get("top_error_locations", [])[:3]
            },
            "cache_stats": {
                "hit_rates": cache_stats.get("hit_rates", {}),
                "memory_usage": cache_stats.get("memory_usage", {}),
                "eviction_rates": cache_stats.get("eviction_rates", {})
            },
            "resource_usage": {
                "memory_rss": memory_info.rss,
                "memory_vms": memory_info.vms,
                "cpu_percent": process.cpu_percent(),
                "thread_count": len(process.threads())
            },
            "warmup_status": {
                "complete": self._warmup_complete,
                "cache_ready": self._warmup_complete and self._pattern_cache is not None
            }
        }
        
        # Check for degraded conditions
        if stats.get("success_rate", 0) < 0.8:  # Less than 80% validation success
            status = ComponentStatus.DEGRADED
            details["reason"] = "Low validation success rate"
        elif metrics["processing"]["failed_patterns"] > metrics["processing"]["total_patterns"] * 0.2:  # More than 20% failures
            status = ComponentStatus.DEGRADED
            details["reason"] = "High pattern failure rate"
        elif error_report.get("error_rate", 0) > 0.1:  # More than 10% error rate
            status = ComponentStatus.DEGRADED
            details["reason"] = "High error rate"
        elif details["resource_usage"]["cpu_percent"] > 80:  # High CPU usage
            status = ComponentStatus.DEGRADED
            details["reason"] = "High CPU usage"
        elif not self._warmup_complete:  # Cache not ready
            status = ComponentStatus.DEGRADED
            details["reason"] = "Cache warmup incomplete"
            
        return {
            "status": status,
            "details": details
        }

    async def cleanup(self):
        """Clean up processor resources."""
        try:
            if self._pending_tasks:
                for task in self._pending_tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                self._pending_tasks.clear()
            
            # Clean up caches
            if self._pattern_cache:
                await self._pattern_cache.clear_async()
                await cache_coordinator.unregister_cache("pattern_processor_patterns")
            if self._validation_cache:
                await self._validation_cache.clear_async()
                await cache_coordinator.unregister_cache("pattern_processor_validation")
            
            # Save error analysis
            await ErrorAudit.save_report()
            
            # Save cache analytics
            analytics = await get_cache_analytics()
            await analytics.save_metrics_history(self._pattern_cache.get_metrics())
            await analytics.save_metrics_history(self._validation_cache.get_metrics())
            
            # Save metrics to database
            async with transaction_scope() as txn:
                await txn.execute("""
                    INSERT INTO pattern_processor_metrics (
                        timestamp, total_patterns, matched_patterns,
                        failed_patterns, validation_stats
                    ) VALUES ($1, $2, $3, $4, $5)
                """, (
                    time.time(),
                    self._processing_stats["total_patterns"],
                    self._processing_stats["matched_patterns"],
                    self._processing_stats["failed_patterns"],
                    self._processing_stats["validation_stats"]
                ))
            
            # Unregister from health monitor
            global_health_monitor.unregister_component("pattern_processor")
            
            self._initialized = False
            await log("Pattern processor cleaned up", level="info")
        except Exception as e:
            await log(f"Error cleaning up pattern processor: {e}", level="error")
            raise ProcessingError(f"Failed to cleanup pattern processor: {e}")

    async def _process_regex_pattern(self, source_code: str, pattern: QueryPattern) -> List[PatternMatch]:
        """Process using regex pattern."""
        matches = []
        for match in pattern.regex.finditer(source_code):
            result = PatternMatch(
                text=match.group(0),
                start=match.start(),
                end=match.end(),
                metadata={
                    "groups": match.groups(),
                    "named_groups": match.groupdict()
                }
            )
            if pattern.extract:
                try:
                    extracted = pattern.extract(result)
                    if extracted:
                        result.metadata.update(extracted)
                except Exception as e:
                    await log(f"Error in pattern extraction: {e}", level="error")
            matches.append(result)
        return matches

    async def _process_tree_sitter_pattern(self, source_code: str, pattern: QueryPattern) -> List[PatternMatch]:
        """Process using tree-sitter pattern."""
        from tree_sitter_language_pack import get_parser
        
        matches = []
        parser = get_parser(pattern.language_id)
        if not parser:
            return matches

        tree = await parser.parse(bytes(source_code, "utf8"))
        if not tree:
            return matches

        query = parser.language.query(pattern.tree_sitter)
        for match in query.matches(tree.root_node):
            captures = {capture.name: capture.node for capture in match.captures}
            result = PatternMatch(
                text=match.pattern_node.text.decode('utf8'),
                start=match.pattern_node.start_point,
                end=match.pattern_node.end_point,
                metadata={"captures": captures}
            )
            
            if pattern.extract:
                try:
                    extracted = pattern.extract(result)
                    if extracted:
                        result.metadata.update(extracted)
                except Exception as e:
                    await log(f"Error in pattern extraction: {e}", level="error")
            
            matches.append(result)
        
        return matches

    @monitor_operation("validate_pattern", "pattern_processor")
    @cached_in_request
    @handle_async_errors(error_types=(ProcessingError,))
    async def validate_pattern(
        self,
        pattern: ProcessedPattern,
        validation_context: Optional[Dict[str, Any]] = None,
        skip_cache: bool = False
    ) -> Tuple[bool, List[str]]:
        """Validate a pattern with request-level caching and monitoring."""
        if not self._initialized:
            await self.initialize()
            
        # Get request context for metrics
        request_cache = get_current_request_cache()
        if request_cache:
            await request_cache.set(
                "pattern_validation_count",
                (await request_cache.get("pattern_validation_count", 0)) + 1
            )
            
        try:
            async with AsyncErrorBoundary(
                operation_name="pattern_validation",
                error_types=ProcessingError,
                severity=ErrorSeverity.WARNING
            ):
                self._processing_stats["validation_stats"]["total_validations"] += 1
                
                # Generate cache key
                cache_key = self._generate_validation_cache_key(pattern, validation_context)
                
                # Check validation cache if not skipping
                if not skip_cache:
                    cached_result = await self._validation_cache.get_async(cache_key)
                    if cached_result:
                        self._processing_stats["validation_stats"]["cache_hits"] += 1
                        await cache_metrics.increment("pattern_processor_validation", "hits")
                        await log(
                            "Pattern validation cache hit",
                            level="debug",
                            context={
                                "pattern_name": pattern.pattern_name,
                                "cache_key": cache_key,
                                "is_valid": cached_result["is_valid"]
                            }
                        )
                        return cached_result["is_valid"], cached_result["errors"]
                
                validation_errors = []
                validation_context = validation_context or {}
                
                try:
                    # Basic validation with detailed error context
                    if not pattern.pattern_name:
                        await self._track_validation_error(
                            "missing_pattern_name",
                            {"pattern_type": getattr(pattern, "pattern_type", None)}
                        )
                        validation_errors.append({
                            "error": "Pattern name is required",
                            "context": {"pattern_type": getattr(pattern, "pattern_type", None)}
                        })
                    if not pattern.category:
                        await self._track_validation_error(
                            "missing_category",
                            {"pattern_name": pattern.pattern_name}
                        )
                        validation_errors.append({
                            "error": "Pattern category is required",
                            "context": {"pattern_name": pattern.pattern_name}
                        })
                        
                    # Content validation with size analysis
                    if hasattr(pattern, 'content'):
                        if not pattern.content:
                            await self._track_validation_error(
                                "empty_content",
                                {"pattern_name": pattern.pattern_name}
                            )
                            validation_errors.append({
                                "error": "Pattern content is empty",
                                "context": {"pattern_name": pattern.pattern_name}
                            })
                        elif len(pattern.content) > 10000:  # Arbitrary limit
                            await self._track_validation_error(
                                "content_too_large",
                                {
                                    "pattern_name": pattern.pattern_name,
                                    "content_size": len(pattern.content),
                                    "max_size": 10000
                                }
                            )
                            validation_errors.append({
                                "error": "Pattern content exceeds size limit",
                                "context": {
                                    "pattern_name": pattern.pattern_name,
                                    "content_size": len(pattern.content),
                                    "max_size": 10000
                                }
                            })
                    
                    # Context-specific validation
                    if validation_context:
                        await self._validate_with_context(pattern, validation_context, validation_errors)
                    
                    # Relationship validation
                    if hasattr(pattern, 'relationships'):
                        await self._validate_relationships(pattern, validation_errors)
                    
                    # Track pattern evolution if valid
                    is_valid = len(validation_errors) == 0
                    if is_valid:
                        await self._track_pattern_evolution(pattern)
                        self._processing_stats["validation_stats"]["successful_validations"] += 1
                        await log(
                            "Pattern validated successfully",
                            level="info",
                            context={
                                "pattern_name": pattern.pattern_name,
                                "pattern_type": getattr(pattern, "pattern_type", None),
                                "validation_context": validation_context
                            }
                        )
                    else:
                        self._processing_stats["validation_stats"]["failed_validations"] += 1
                        await log(
                            "Pattern validation failed",
                            level="warning",
                            context={
                                "pattern_name": pattern.pattern_name,
                                "error_count": len(validation_errors),
                                "errors": [err["error"] for err in validation_errors],
                                "validation_context": validation_context
                            }
                        )
                    
                    # Cache validation result
                    cache_data = {
                        "is_valid": is_valid,
                        "errors": [err["error"] for err in validation_errors],
                        "timestamp": time.time()
                    }
                    await self._validation_cache.set_async(cache_key, cache_data)
                    await cache_metrics.increment("pattern_processor_validation", "sets")
                    
                    # Track request-level metrics
                    if request_cache:
                        validation_metrics = {
                            "pattern_name": pattern.pattern_name,
                            "validation_time": time.time(),
                            "is_valid": is_valid,
                            "error_count": len(validation_errors)
                        }
                        await request_cache.set(
                            f"validation_metrics_{pattern.pattern_name}",
                            validation_metrics
                        )
                    
                    return is_valid, [err["error"] for err in validation_errors]
                    
                except Exception as e:
                    error_msg = f"Validation error: {str(e)}"
                    
                    # Get error recommendations
                    recommendations = await ErrorAudit.get_standardization_recommendations()
                    relevant_recs = [r for r in recommendations if r["location"] == "validate_pattern"]
                    
                    if relevant_recs:
                        await log(
                            "Error handling recommendations available",
                            level="warning",
                            context={"recommendations": relevant_recs}
                        )
                    
                    await self._track_validation_error(
                        "validation_exception",
                        {
                            "pattern_name": pattern.pattern_name,
                            "error": str(e),
                            "validation_context": validation_context,
                            "recommendations": relevant_recs
                        }
                    )
                    
                    # Track in request context
                    if request_cache:
                        await request_cache.set(
                            "last_validation_error",
                            {
                                "error": str(e),
                                "pattern": pattern.pattern_name,
                                "timestamp": time.time()
                            }
                        )
                    
                    return False, [error_msg]
            
        except Exception as e:
            error_msg = f"Validation error: {str(e)}"
            
            # Get error recommendations
            recommendations = await ErrorAudit.get_standardization_recommendations()
            relevant_recs = [r for r in recommendations if r["location"] == "validate_pattern"]
            
            if relevant_recs:
                await log(
                    "Error handling recommendations available",
                    level="warning",
                    context={"recommendations": relevant_recs}
                )
            
            await self._track_validation_error(
                "validation_exception",
                {
                    "pattern_name": pattern.pattern_name,
                    "error": str(e),
                    "validation_context": validation_context,
                    "recommendations": relevant_recs
                }
            )
            
            # Track in request context
            if request_cache:
                await request_cache.set(
                    "last_validation_error",
                    {
                        "error": str(e),
                        "pattern": pattern.pattern_name,
                        "timestamp": time.time()
                    }
                )
            
            return False, [error_msg]

    def _generate_validation_cache_key(
        self,
        pattern: ProcessedPattern,
        validation_context: Optional[Dict[str, Any]]
    ) -> str:
        """Generate a cache key for validation results."""
        key_parts = [
            pattern.pattern_name,
            str(pattern.category) if pattern.category else "",
            str(hash(pattern.content)) if hasattr(pattern, "content") else "",
            str(hash(str(validation_context))) if validation_context else ""
        ]
        return ":".join(key_parts)

    async def _track_validation_error(self, error_type: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Track validation error types for monitoring."""
        stats = self._processing_stats["validation_stats"]
        if "validation_errors" not in stats:
            stats["validation_errors"] = {}
        if error_type not in stats["validation_errors"]:
            stats["validation_errors"][error_type] = 0
        stats["validation_errors"][error_type] += 1
        
        # Log with context
        log_context = {
            "error_type": error_type,
            "total_errors": stats["validation_errors"][error_type],
            "validation_stats": {
                "total_validations": stats["total_validations"],
                "failed_validations": stats["failed_validations"]
            }
        }
        if context:
            log_context.update(context)
            
        await log(
            f"Pattern validation error: {error_type}",
            level="warning",
            context=log_context
        )

    async def get_validation_stats(self) -> Dict[str, Any]:
        """Get detailed validation statistics."""
        stats = self._processing_stats["validation_stats"].copy()
        
        # Calculate success rate
        total = stats["total_validations"]
        if total > 0:
            stats["success_rate"] = stats["successful_validations"] / total
            stats["cache_hit_rate"] = stats["cache_hits"] / total
        
        # Get most common errors
        if "validation_errors" in stats:
            sorted_errors = sorted(
                stats["validation_errors"].items(),
                key=lambda x: x[1],
                reverse=True
            )
            stats["top_validation_errors"] = dict(sorted_errors[:5])
        
        return stats

    async def _validate_with_context(
        self,
        pattern: ProcessedPattern,
        context: Dict[str, Any],
        errors: List[str]
    ) -> None:
        """Validate pattern with additional context."""
        # Language-specific validation
        if "language" in context:
            if not self._validate_language_specific(pattern, context["language"]):
                errors.append(f"Invalid pattern for language {context['language']}")
        
        # Project-specific validation
        if "project_patterns" in context:
            conflicts = self._check_pattern_conflicts(pattern, context["project_patterns"])
            if conflicts:
                errors.append(f"Pattern conflicts with existing patterns: {conflicts}")
        
        # Purpose-specific validation
        if "purpose" in context:
            if not self._validate_purpose_compatibility(pattern, context["purpose"]):
                errors.append(f"Pattern incompatible with purpose {context['purpose']}")
    
    async def _validate_relationships(
        self,
        pattern: ProcessedPattern,
        errors: List[str]
    ) -> None:
        """Validate pattern relationships."""
        if not hasattr(pattern, 'relationships'):
            return
            
        for rel in pattern.relationships:
            # Validate relationship type
            if not isinstance(rel, PatternRelationship):
                errors.append(f"Invalid relationship type: {type(rel)}")
                continue
            
            # Validate target pattern exists
            target_exists = await self._check_pattern_exists(rel.target_id)
            if not target_exists:
                errors.append(f"Target pattern {rel.target_id} does not exist")
            
            # Validate relationship type is valid
            if rel.type not in PatternRelationType:
                errors.append(f"Invalid relationship type: {rel.type}")
            
            # Validate cyclic relationships
            if await self._has_cyclic_relationship(pattern.pattern_name, rel.target_id):
                errors.append(f"Cyclic relationship detected with pattern {rel.target_id}")
    
    async def _track_pattern_evolution(self, pattern: ProcessedPattern) -> None:
        """Track pattern evolution and relationships."""
        try:
            async with transaction_scope() as txn:
                # Store pattern version
                version_data = {
                    "pattern_name": pattern.pattern_name,
                    "version": time.time(),
                    "content": pattern.content if hasattr(pattern, 'content') else None,
                    "category": pattern.category,
                    "purpose": pattern.purpose,
                    "confidence": pattern.confidence if hasattr(pattern, 'confidence') else None
                }
                
                await txn.execute("""
                    INSERT INTO pattern_versions (
                        pattern_name, version, content, category,
                        purpose, confidence
                    ) VALUES ($1, $2, $3, $4, $5, $6)
                """, version_data.values())
                
                # Store relationships if present
                if hasattr(pattern, 'relationships'):
                    for rel in pattern.relationships:
                        await txn.execute("""
                            INSERT INTO pattern_relationships (
                                source_pattern, target_pattern,
                                relationship_type, metadata
                            ) VALUES ($1, $2, $3, $4)
                        """, (pattern.pattern_name, rel.target_id,
                              rel.type, rel.metadata))
                
                # Update pattern metrics
                self._metrics.total_patterns += 1
                if hasattr(pattern, 'relationships'):
                    self._metrics.pattern_relationships += len(pattern.relationships)
                
        except Exception as e:
            await log(f"Error tracking pattern evolution: {e}", level="error")
    
    async def _check_pattern_exists(self, pattern_id: str) -> bool:
        """Check if a pattern exists."""
        try:
            async with transaction_scope() as txn:
                result = await txn.fetchval("""
                    SELECT EXISTS(
                        SELECT 1 FROM patterns WHERE pattern_name = $1
                    )
                """, pattern_id)
                return bool(result)
        except Exception as e:
            await log(f"Error checking pattern existence: {e}", level="error")
            return False
    
    async def _has_cyclic_relationship(
        self,
        source: str,
        target: str,
        visited: Optional[Set[str]] = None
    ) -> bool:
        """Check for cyclic relationships."""
        if visited is None:
            visited = set()
            
        if source in visited:
            return True
            
        visited.add(source)
        
        try:
            async with transaction_scope() as txn:
                relationships = await txn.fetch("""
                    SELECT target_pattern 
                    FROM pattern_relationships 
                    WHERE source_pattern = $1
                """, target)
                
                for rel in relationships:
                    if await self._has_cyclic_relationship(rel["target_pattern"], source, visited):
                        return True
                        
                return False
                
        except Exception as e:
            await log(f"Error checking cyclic relationships: {e}", level="error")
            return False

# Global instance
pattern_processor = PatternProcessor()

async def get_pattern_processor() -> PatternProcessor:
    """Get the global pattern processor instance."""
    if not pattern_processor._initialized:
        await pattern_processor.initialize()
    return pattern_processor 