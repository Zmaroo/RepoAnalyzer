"""[6.0] Pattern processing and validation.

This module provides pattern processing capabilities for code analysis and manipulation.
Core pattern processing functionality separated from AI capabilities.
Integrates with cache analytics, error handling, and logging systems.
"""

from typing import Dict, Any, List, Union, Optional, Set, Tuple
from dataclasses import dataclass, field
import asyncio
import re
import time
import importlib
import numpy as np
from tree_sitter_language_pack import get_binding, get_language, get_parser, SupportedLanguage
from parsers.types import (
    ParserType, PatternCategory, PatternPurpose, FileType, 
    PatternDefinition, QueryPattern, AIContext, 
    AIProcessingResult, PatternType, PatternRelationType,
    FeatureCategory, ParserResult, AICapability
)
from parsers.models import (
    PatternMatch, PATTERN_CATEGORIES, ProcessedPattern, 
    QueryResult, PatternRelationship
)
from parsers.parser_interfaces import BaseParserInterface, AIParserInterface
from parsers.custom_parsers import CUSTOM_PARSER_CLASSES
from parsers.language_mapping import normalize_language_name
from utils.logger import log
from utils.error_handling import (
    handle_async_errors,
    AsyncErrorBoundary,
    ProcessingError,
    ErrorAudit,
    ErrorSeverity
)
from utils.cache import UnifiedCache, cache_coordinator
from utils.cache_analytics import get_cache_analytics, CacheAnalytics
from utils.request_cache import cached_in_request, request_cache_context, get_current_request_cache
from utils.shutdown import register_shutdown_handler
from db.pattern_storage import PatternStorageMetrics, get_pattern_storage
from db.transaction import transaction_scope
from utils.health_monitor import global_health_monitor, ComponentStatus, monitor_operation
from utils.async_runner import submit_async_task, cleanup_tasks
import traceback
import os
import psutil
from parsers.query_patterns import (
    create_pattern,
    validate_pattern,
    is_language_supported,
    get_parser_type_for_language
)

class PatternProcessor(BaseParserInterface, AIParserInterface):
    """Core pattern processing system."""
    
    def __init__(self):
        """Initialize pattern processor."""
        # Initialize base parser interface
        BaseParserInterface.__init__(
            self,
            language_id="pattern_processor",
            file_type=FileType.CODE,
            parser_type=ParserType.CUSTOM  # Since it's a core parser implementation
        )
        
        # Initialize AI parser interface
        AIParserInterface.__init__(
            self,
            language_id="pattern_processor",
            file_type=FileType.CODE,
            capabilities={
                AICapability.CODE_UNDERSTANDING,
                AICapability.CODE_GENERATION,
                AICapability.CODE_MODIFICATION,
                AICapability.CODE_REVIEW,
                AICapability.LEARNING
            }
        )
        
        self._initialized = False
        self._patterns: Dict[PatternCategory, Dict[str, Any]] = {}
        self._pending_tasks: Set[asyncio.Task] = set()
        self._lock = asyncio.Lock()
        self._metrics = PatternStorageMetrics()
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
        self._validation_ttl = 300  # 5 minutes cache TTL
        self._warmup_complete = False
        self._cache = None
        self._tree_sitter_patterns = {}
        self._custom_patterns = {}
        
        # Initialize caches
        self._pattern_cache = UnifiedCache("pattern_processor_patterns")
        self._validation_cache = UnifiedCache("pattern_processor_validation")
        
        register_shutdown_handler(self.cleanup)

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
            # Update status
            await global_health_monitor.update_component_status(
                "pattern_processor",
                ComponentStatus.INITIALIZING,
                details={"stage": "starting"}
            )
            
            # Register caches with coordinator
            await cache_coordinator.register_cache("pattern_processor_patterns", self._pattern_cache)
            await cache_coordinator.register_cache("pattern_processor_validation", self._validation_cache)
            
            # Initialize cache analytics
            analytics = await get_cache_analytics()
            analytics.register_warmup_function(
                "pattern_processor_patterns",
                self._warmup_pattern_cache
            )
            
            # Load patterns for each category
            for category in PatternCategory:
                init_task = submit_async_task(self._load_patterns(category))
                await asyncio.wrap_future(init_task)
                
                await global_health_monitor.update_component_status(
                    "pattern_processor",
                    ComponentStatus.INITIALIZING,
                    details={"stage": f"loaded_{category.value}_patterns"}
                )
            
            # Register cleanup handler
            register_shutdown_handler(self.cleanup)
            
            self._initialized = True
            await log("Pattern processor initialized successfully", level="info")
            
            # Update final status
            await global_health_monitor.update_component_status(
                "pattern_processor",
                ComponentStatus.HEALTHY,
                details={
                    "stage": "complete",
                    "patterns_by_category": {
                        category.value: len(patterns)
                        for category, patterns in self._patterns.items()
                    }
                }
            )
            
            return True
        except Exception as e:
            await log(f"Error initializing pattern processor: {e}", level="error")
            await global_health_monitor.update_component_status(
                "pattern_processor",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"initialization_error": str(e)}
            )
            return False

    async def _warmup_pattern_cache(self, keys: List[str]) -> Dict[str, Any]:
        """Warmup function for pattern cache."""
        results = {}
        for key in keys:
            try:
                # Get common patterns for warmup
                patterns = await self._get_common_patterns()
                if patterns:
                    results[key] = patterns
            except Exception as e:
                await log(f"Error warming up pattern cache for {key}: {e}", level="warning")
        return results

    async def cleanup(self):
        """Clean up pattern processor resources."""
        try:
            if not self._initialized:
                return
                
            # Update status
            await global_health_monitor.update_component_status(
                "pattern_processor",
                ComponentStatus.SHUTTING_DOWN,
                details={"stage": "starting"}
            )
            
            # Clean up caches
            await cache_coordinator.unregister_cache("pattern_processor_patterns")
            await cache_coordinator.unregister_cache("pattern_processor_validation")
            
            # Save error audit report
            await ErrorAudit.save_report()
            
            # Clean up any remaining tasks
            if self._pending_tasks:
                for task in self._pending_tasks:
                    task.cancel()
                await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                self._pending_tasks.clear()
            
            self._initialized = False
            await log("Pattern processor cleaned up successfully", level="info")
            
            # Update final status
            await global_health_monitor.update_component_status(
                "pattern_processor",
                ComponentStatus.SHUTDOWN,
                details={"cleanup": "successful"}
            )
        except Exception as e:
            await log(f"Error cleaning up pattern processor: {e}", level="error")
            await global_health_monitor.update_component_status(
                "pattern_processor",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"cleanup_error": str(e)}
            )

    async def _load_patterns(self, category: PatternCategory) -> None:
        """Load patterns for a category."""
        try:
            # Get pattern storage instance
            storage = await get_pattern_storage()
            
            # Map category to pattern type and subtype
            category_mapping = {
                PatternCategory.SYNTAX: ("code", "syntax"),
                PatternCategory.SEMANTICS: ("code", "semantics"),
                PatternCategory.DOCUMENTATION: ("doc", "documentation"),
                PatternCategory.STRUCTURE: ("arch", "structure"),
                PatternCategory.CONTEXT: ("code", "context"),
                PatternCategory.DEPENDENCIES: ("code", "dependencies"),
                PatternCategory.CODE_PATTERNS: ("code", "patterns"),
                PatternCategory.BEST_PRACTICES: ("code", "best_practices"),
                PatternCategory.COMMON_ISSUES: ("code", "issues"),
                PatternCategory.USER_PATTERNS: ("code", "user"),
                PatternCategory.LEARNING: ("code", "learning")
            }
            
            if category not in category_mapping:
                await log(f"Unsupported pattern category: {category.value}", level="warning")
                return
                
            pattern_type, subtype = category_mapping[category]
            
            # Load patterns from storage
            patterns_by_type = await storage.get_patterns(None, pattern_type)
            all_patterns = patterns_by_type.get(pattern_type, [])
            
            # Filter patterns by subtype
            patterns = [
                pattern for pattern in all_patterns
                if pattern.get("pattern_type") == subtype or
                pattern.get("metadata", {}).get("subtype") == subtype
            ]
            
            # Initialize category dict if needed
            if category not in self._patterns:
                self._patterns[category] = {}
            
            # Store patterns with proper metadata
            for pattern in patterns:
                if "name" in pattern:  # Only store patterns with names
                    pattern_key = pattern["name"]
                    self._patterns[category][pattern_key] = {
                        **pattern,
                        "category": category,
                        "pattern_type": pattern_type,
                        "subtype": subtype,
                        "metadata": {
                            **(pattern.get("metadata", {})),
                            "source": pattern.get("file_path", ""),
                            "last_updated": pattern.get("last_updated")
                        }
                    }
            
            await log(f"Loaded {len(patterns)} patterns for {category.value}", level="info")
        except Exception as e:
            await log(f"Error loading patterns for {category.value}: {e}", level="error")
            raise

    @cached_in_request(lambda self, pattern_name: f"pattern:{pattern_name}")
    async def process_pattern(self, pattern_name: str, source_code: str, language_id: str):
        """Process pattern with request-level caching."""
        async with request_cache_context() as cache:
            # Check if we've already processed this pattern
            cache_key = f"pattern_result:{pattern_name}:{hash(source_code)}"
            cached_result = await cache.get(cache_key)
            if cached_result:
                return cached_result
                
            # Process pattern
            result = await self._process_pattern_impl(pattern_name, source_code, language_id)
            
            # Cache result
            await cache.set(cache_key, result)
            return result

    async def _process_pattern_internal(
        self,
        source_code: str,
        pattern: QueryPattern
    ) -> List[PatternMatch]:
        """Internal pattern processing implementation."""
        start_time = time.time()

        try:
            # Get matches using enhanced QueryPattern functionality
            matches = pattern.matches(source_code)
            
            # Convert to PatternMatch instances
            pattern_matches = []
            for match in matches:
                pattern_match = PatternMatch(
                    pattern_name=pattern.name,
                    start_line=match.get("start", 0),
                    end_line=match.get("end", 0),
                    start_col=0,  # These would need to be extracted from the match
                    end_col=0,    # based on pattern type
                    matched_text=match.get("text", ""),
                    category=pattern.category,
                    purpose=pattern.purpose,
                    confidence=pattern.confidence,
                    metadata=match
                )
                pattern_matches.append(pattern_match)
            
            execution_time = time.time() - start_time
            await self._track_metrics(pattern.name, execution_time, len(pattern_matches))
            
            return pattern_matches

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
            "processing": self._processing_stats
        }

    def reset_metrics(self) -> None:
        """Reset all metrics."""
        self._metrics = PatternStorageMetrics()
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

    async def _process_tree_sitter_pattern(
        self,
        pattern: Dict[str, Any],
        source_code: str,
        language_id: str
    ) -> QueryResult:
        """Process a tree-sitter pattern."""
        try:
            # Get tree-sitter components
            parser = get_parser(language_id)
            language = get_language(language_id)
            
            if not parser or not language:
                raise ProcessingError(f"Failed to get tree-sitter components for {language_id}")
            
            # Parse source code
            tree = parser.parse(bytes(source_code, "utf8"))
            
            # Create and execute query
            query = language.query(pattern.pattern)
            matches = query.matches(tree.root_node)
            
            # Process matches
            result = QueryResult(pattern_name=pattern.name)
            for match in matches:
                match_data = {
                    "node": match.pattern_node,
                    "captures": {c.name: c.node for c in match.captures}
                }
                
                # Apply extraction function if provided
                if pattern.extract:
                    try:
                        extracted_data = pattern.extract(match_data)
                        match_data.update(extracted_data)
                    except Exception as e:
                        await log(f"Error in pattern extraction: {e}", level="error")
                
                result.matches.append(match_data)
            
            return result
        except Exception as e:
            await log(f"Error processing tree-sitter pattern: {e}", level="error")
            return QueryResult(pattern_name=pattern.name)

    async def _process_custom_pattern(
        self,
        pattern: Dict[str, Any],
        source_code: str,
        language_id: str
    ) -> QueryResult:
        """Process a custom pattern."""
        try:
            # Get custom parser class
            parser_class = CUSTOM_PARSER_CLASSES.get(language_id)
            if not parser_class:
                raise ProcessingError(f"No custom parser found for {language_id}")
            
            # Create parser instance
            parser = parser_class()
            
            # Process pattern
            result = QueryResult(pattern_name=pattern.name)
            matches = await parser.process_pattern(pattern, source_code)
            
            # Apply extraction function if provided
            if pattern.extract and matches:
                try:
                    for match in matches:
                        extracted = pattern.extract(match)
                        if extracted:
                            match.update(extracted)
                except Exception as e:
                    await log(f"Error in pattern extraction: {e}", level="error")
            
            result.matches = matches
            return result
            
        except Exception as e:
            await log(f"Error processing custom pattern: {e}", level="error")
            return QueryResult(pattern_name=pattern.name)

    async def get_patterns_for_category(
        self,
        category: FeatureCategory,
        purpose: PatternPurpose,
        language_id: str,
        parser_type: ParserType
    ) -> List[QueryPattern]:
        """Get patterns for a specific category, purpose, and language."""
        if not self._initialized:
            await self.ensure_initialized()
        
        # Check cache first
        cache_key = f"patterns:{category.value}:{purpose.value}:{language_id}:{parser_type.value}"
        cached_patterns = await self._cache.get(cache_key)
        if cached_patterns:
            return [QueryPattern(**p) for p in cached_patterns]
        
        patterns = []
        
        # Get patterns based on parser type
        if parser_type == ParserType.CUSTOM:
            patterns.extend(await self._get_custom_patterns(category, purpose, language_id))
        elif parser_type == ParserType.TREE_SITTER:
            patterns.extend(await self._get_tree_sitter_patterns(category, purpose, language_id))
        
        # Cache patterns
        await self._cache.set(cache_key, [p.__dict__ for p in patterns])
        
        return patterns
    
    async def _get_tree_sitter_patterns(
        self,
        category: FeatureCategory,
        purpose: PatternPurpose,
        language_id: str
    ) -> List[QueryPattern]:
        """Get tree-sitter patterns for a specific category, purpose, and language."""
        patterns = []
        
        # Get pattern files for this category and language
        pattern_files = await self._get_pattern_files(category, language_id, ParserType.TREE_SITTER)
        
        for pattern_file in pattern_files:
            # Load patterns
            file_patterns = await self._load_pattern_file(pattern_file)
            for pattern_data in file_patterns:
                try:
                    # Create QueryPattern instance
                    pattern = create_pattern(
                        name=pattern_data["name"],
                        pattern=pattern_data["pattern"],
                        category=category,
                        purpose=purpose,
                        language_id=language_id,
                        extract=pattern_data.get("extract"),
                        confidence=pattern_data.get("confidence", 0.0),
                        metadata=pattern_data.get("metadata", {})
                    )
                    patterns.append(pattern)
                except Exception as e:
                    await log(f"Error creating pattern from {pattern_file}: {e}", level="error")
        
        return patterns
    
    async def _get_custom_patterns(
        self,
        category: FeatureCategory,
        purpose: PatternPurpose,
        language_id: str
    ) -> List[QueryPattern]:
        """Get custom patterns for a specific category, purpose, and language."""
        patterns = []
        
        # Get pattern files for this category and language
        pattern_files = await self._get_pattern_files(category, language_id, ParserType.CUSTOM)
        
        for pattern_file in pattern_files:
            # Load patterns
            file_patterns = await self._load_pattern_file(pattern_file)
            for pattern_data in file_patterns:
                try:
                    # Create QueryPattern instance
                    pattern = create_pattern(
                        name=pattern_data["name"],
                        pattern=pattern_data["pattern"],
                        category=category,
                        purpose=purpose,
                        language_id=language_id,
                        extract=pattern_data.get("extract"),
                        confidence=pattern_data.get("confidence", 0.0),
                        metadata=pattern_data.get("metadata", {})
                    )
                    patterns.append(pattern)
                except Exception as e:
                    await log(f"Error creating pattern from {pattern_file}: {e}", level="error")
        
        return patterns
    
    async def _get_pattern_files(
        self,
        category: FeatureCategory,
        language_id: str,
        parser_type: ParserType
    ) -> List[str]:
        """Get pattern files for a specific category and language."""
        import glob
        import os
        
        pattern_files = []
        
        # Get pattern files from query_patterns directory
        pattern_dir = os.path.join("parsers", "query_patterns")
        
        if parser_type == ParserType.CUSTOM:
            # For custom parsers, look for language-specific pattern files
            pattern_glob = os.path.join(pattern_dir, f"{language_id}_{category.value}_*.py")
        else:
            # For tree-sitter, look for tree-sitter pattern files
            pattern_glob = os.path.join(pattern_dir, f"tree_sitter_{language_id}_{category.value}_*.scm")
        
        pattern_files.extend(glob.glob(pattern_glob))
        
        return pattern_files
    
    async def _load_pattern_file(self, pattern_file: str) -> List[Dict[str, Any]]:
        """Load patterns from a pattern file."""
        import json
        
        try:
            with open(pattern_file, "r") as f:
                patterns = json.load(f)
            return patterns
        except Exception as e:
            await log(f"Error loading pattern file {pattern_file}: {e}", level="error")
            return []
    
    async def validate_pattern(self, pattern: Dict[str, Any], language_id: str) -> bool:
        """Validate a pattern for a specific language."""
        try:
            # Check required fields
            required_fields = ["name", "pattern", "purpose"]
            for field in required_fields:
                if field not in pattern:
                    await log(f"Pattern missing required field {field}", level="error")
                    return False
            
            # Validate pattern syntax
            if pattern.get("type") == "tree-sitter":
                # Validate tree-sitter query syntax
                if language_id in SupportedLanguage.__args__:
                    language = get_language(language_id)
                    try:
                        language.query(pattern["pattern"])
                    except Exception as e:
                        await log(f"Invalid tree-sitter query: {e}", level="error")
                        return False
            else:
                # Validate regex pattern
                import re
                try:
                    re.compile(pattern["pattern"])
                except Exception as e:
                    await log(f"Invalid regex pattern: {e}", level="error")
                    return False
            
            return True
        except Exception as e:
            await log(f"Error validating pattern: {e}", level="error")
            return False
    
    async def _get_pattern(
        self,
        pattern_name: str,
        language_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get a pattern by name and language."""
        # Check tree-sitter patterns
        if pattern_name in self._tree_sitter_patterns.get(language_id, {}):
            return self._tree_sitter_patterns[language_id][pattern_name]
        
        # Check custom patterns
        if pattern_name in self._custom_patterns.get(language_id, {}):
            return self._custom_patterns[language_id][pattern_name]
        
        return None
    
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

    async def _parse_source(self, source_code: str) -> Optional[Dict[str, Any]]:
        """Parse source code into AST."""
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary(f"{self.language_id} parsing"):
            try:
                # For pattern processor, we create a simple AST-like structure
                ast = {
                    "type": "pattern_root",
                    "content": source_code,
                    "patterns": await self._process_pattern_internal(source_code, None)
                }
                return ast
            except Exception as e:
                log(f"Error parsing pattern content: {e}", level="error")
                return None

    def _parse_content(self, source_code: str) -> Dict[str, Any]:
        """Internal synchronous parsing method."""
        # Pattern processor doesn't need synchronous parsing
        # All work is done in _parse_source
        return {
            "type": "pattern_root",
            "content": source_code
        }

    async def parse(self, source_code: str) -> Optional[ParserResult]:
        """Parse source code and return structured results."""
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary(f"{self.language_id} parsing"):
            try:
                # Parse the source
                ast = await self._parse_source(source_code)
                if not ast:
                    return None
                
                # Extract features
                features = await self.extract_features(ast, source_code)
                
                return ParserResult(
                    success=True,
                    ast=ast,
                    features=features,
                    documentation=features.get(FeatureCategory.DOCUMENTATION.value, {}),
                    complexity=features.get(FeatureCategory.SYNTAX.value, {}).get("metrics", {}),
                    statistics=self.stats
                )
            except Exception as e:
                log(f"Error in pattern processor: {e}", level="error")
                return None

    async def extract_features(self, ast: Dict[str, Any], source_code: str) -> Dict[str, Dict[str, Any]]:
        """Extract features from parsed content."""
        features = {
            FeatureCategory.SYNTAX.value: {
                "patterns": ast.get("patterns", []),
                "metrics": {
                    "pattern_count": len(ast.get("patterns", [])),
                    "source_length": len(source_code)
                }
            },
            FeatureCategory.DOCUMENTATION.value: {}  # Pattern processor doesn't handle docs
        }
        return features

    async def process_with_ai(
        self,
        source_code: str,
        context: AIContext
    ) -> AIProcessingResult:
        """Process source code with AI assistance."""
        if not self._initialized:
            await self.initialize()
            
        try:
            async with AsyncErrorBoundary("ai_pattern_processing"):
                # Process patterns with AI context
                patterns = await self.process_for_purpose(
                    source_code,
                    context.purpose,
                    context.file_type
                )
                
                return AIProcessingResult(
                    success=True,
                    patterns=patterns,
                    confidence=context.confidence_threshold,
                    metadata={
                        "pattern_count": len(patterns),
                        "processing_time": time.time()
                    }
                )
        except Exception as e:
            await log(f"Error in AI pattern processing: {e}", level="error")
            return AIProcessingResult(
                success=False,
                error=str(e)
            )

    async def process_with_deep_learning(
        self,
        source_code: str,
        context: AIContext,
        repositories: List[int]
    ) -> AIProcessingResult:
        """Process with deep learning capabilities."""
        if not self._initialized:
            await self.initialize()
            
        try:
            async with AsyncErrorBoundary("deep_learning_pattern_processing"):
                # First learn from repositories
                learning_results = await self.learn_from_repositories(repositories)
                
                # Then process with learned patterns
                context.metadata = {
                    "learning_results": learning_results,
                    "repositories": repositories
                }
                
                return await self.process_with_ai(source_code, context)
        except Exception as e:
            await log(f"Error in deep learning pattern processing: {e}", level="error")
            return AIProcessingResult(
                success=False,
                error=str(e)
            )

    async def learn_from_repositories(
        self,
        repo_ids: List[int]
    ) -> Dict[str, Any]:
        """Learn patterns from multiple repositories."""
        if not self._initialized:
            await self.initialize()
            
        try:
            async with AsyncErrorBoundary("repository_pattern_learning"):
                learned_patterns = {}
                
                async with transaction_scope() as txn:
                    # Get repository patterns
                    patterns = await txn.fetch("""
                        SELECT pattern_name, content, category, purpose
                        FROM repository_patterns
                        WHERE repository_id = ANY($1)
                    """, repo_ids)
                    
                    # Process and store learned patterns
                    for pattern in patterns:
                        pattern_key = f"{pattern['pattern_name']}_{pattern['category']}"
                        learned_patterns[pattern_key] = {
                            "content": pattern["content"],
                            "category": pattern["category"],
                            "purpose": pattern["purpose"],
                            "source_repos": repo_ids
                        }
                        
                    # Update learning metrics
                    await txn.execute("""
                        INSERT INTO pattern_learning_metrics (
                            timestamp, repository_count, pattern_count,
                            success_rate
                        ) VALUES ($1, $2, $3, $4)
                    """, (
                        time.time(),
                        len(repo_ids),
                        len(learned_patterns),
                        1.0  # Assuming all patterns were learned successfully
                    ))
                
                return {
                    "learned_patterns": len(learned_patterns),
                    "repositories": len(repo_ids),
                    "timestamp": time.time()
                }
        except Exception as e:
            await log(f"Error learning from repositories: {e}", level="error")
            return {
                "error": str(e),
                "learned_patterns": 0,
                "repositories": len(repo_ids)
            }

    async def validate_all_patterns(patterns: List[Dict[str, Any]], language_id: Optional[str] = None) -> Dict[str, Any]:
        """Validate all patterns for all languages or a specific language.
        
        Args:
            patterns: List of patterns to validate
            language_id: Optional language ID to filter patterns
            
        Returns:
            Dictionary containing validation results and statistics
        """
        validation_results = {
            "valid_patterns": [],
            "invalid_patterns": [],
            "validation_time": 0,
            "stats": {
                "total": 0,
                "valid": 0,
                "invalid": 0
            }
        }
        
        start_time = time.time()
        
        for pattern in patterns:
            # Skip if language_id is specified and doesn't match
            if language_id and pattern.get("language_id") != language_id:
                continue
            
            validation_results["stats"]["total"] += 1
            
            # Create ProcessedPattern instance
            processed_pattern = ProcessedPattern(
                pattern_name=pattern["name"],
                category=pattern.get("category"),
                purpose=pattern.get("purpose"),
                content=pattern.get("pattern"),
                metadata=pattern.get("metadata", {})
            )
            
            # Validate pattern
            is_valid, errors = await pattern_processor.validate_pattern(
                processed_pattern,
                {"language": pattern.get("language_id", "unknown")}
            )
            
            if is_valid:
                validation_results["valid_patterns"].append({
                    "pattern": pattern["name"],
                    "language": pattern.get("language_id", "unknown")
                })
                validation_results["stats"]["valid"] += 1
            else:
                validation_results["invalid_patterns"].append({
                    "pattern": pattern["name"],
                    "language": pattern.get("language_id", "unknown"),
                    "errors": errors
                })
                validation_results["stats"]["invalid"] += 1
        
        validation_results["validation_time"] = time.time() - start_time
        
        return validation_results

    async def report_validation_results(results: Dict[str, Any]) -> str:
        """Generate a human-readable report of pattern validation results.
        
        Args:
            results: Validation results from validate_all_patterns
            
        Returns:
            Formatted string containing the validation report
        """
        report = []
        report.append("Pattern Validation Report")
        report.append("=" * 25)
        report.append("")
        
        # Add statistics
        report.append("Statistics:")
        report.append(f"- Total patterns: {results['stats']['total']}")
        report.append(f"- Valid patterns: {results['stats']['valid']}")
        report.append(f"- Invalid patterns: {results['stats']['invalid']}")
        report.append(f"- Validation time: {results['validation_time']:.2f}s")
        report.append("")
        
        # Add invalid patterns if any
        if results["invalid_patterns"]:
            report.append("Invalid Patterns:")
            for pattern in results["invalid_patterns"]:
                report.append(f"- {pattern['pattern']} ({pattern['language']}):")
                for error in pattern["errors"]:
                    report.append(f"  - {error}")
            report.append("")
        
        return "\n".join(report)

# Global instance
pattern_processor = PatternProcessor()

# Export commonly used functions
__all__ = [
    'pattern_processor',
    'validate_all_patterns',
    'report_validation_results'
] 