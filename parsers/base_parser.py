"""Base parser implementation."""

from abc import abstractmethod
from typing import Optional, Dict, Any, List, Union, Type, Callable, Set
from .types import (
    FileType, PatternCategory, PatternPurpose, ParserType,
    ParserResult, ParserConfig, ParsingStatistics,
    AICapability, AIContext, AIProcessingResult,
    FeatureCategory
)
from dataclasses import field
import re
import asyncio
from parsers.models import PatternMatch, BaseNodeDict, PATTERN_CATEGORIES
from utils.logger import log
from .parser_interfaces import BaseParserInterface, AIParserInterface
from utils.error_handling import AsyncErrorBoundary, ErrorSeverity, ProcessingError, ErrorAudit, handle_errors
from utils.cache import cache_coordinator, UnifiedCache, cache_metrics
from utils.cache_analytics import get_cache_analytics, CacheAnalytics
from utils.request_cache import cached_in_request, request_cache_context, get_current_request_cache
from utils.shutdown import register_shutdown_handler
from db.transaction import transaction_scope
from db.upsert_ops import coordinator as upsert_coordinator
from utils.health_monitor import global_health_monitor, ComponentStatus, monitor_operation
import importlib
from enum import Enum
import os
import psutil
import time

class BaseParser(BaseParserInterface, AIParserInterface):
    """Base implementation for parsers.
    
    Implementations:
    - TreeSitterParser: For languages with tree-sitter support
    - Language-specific parsers (NimParser, PlaintextParser, etc.): For custom parsing
    """
    
    def __init__(self):
        """Private constructor - use create() instead."""
        self._initialized = False
        self._pending_tasks: Set[asyncio.Task] = set()
        self.feature_extractor = None
        self._cache = None
        self._lock = asyncio.Lock()
        self._patterns = None
        self.ai_capabilities = {
            AICapability.CODE_UNDERSTANDING,
            AICapability.CODE_GENERATION,
            AICapability.CODE_MODIFICATION
        }
        self._warmup_complete = False
        self._metrics = {
            "total_parsed": 0,
            "successful_parses": 0,
            "failed_parses": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "parse_times": []
        }
    
    async def ensure_initialized(self):
        """Ensure the instance is properly initialized before use."""
        if not self._initialized:
            raise ProcessingError(f"{self.language_id} parser not initialized. Use create() to initialize.")
        return True
    
    @classmethod
    async def create(cls, language_id: str, file_type: FileType, parser_type: ParserType) -> 'BaseParser':
        """Async factory method to create and initialize a BaseParser instance."""
        instance = cls()
        instance.language_id = language_id
        instance.file_type = file_type
        instance.parser_type = parser_type
        
        try:
            async with AsyncErrorBoundary(f"{language_id} parser initialization"):
                # Track initialization resources
                initialized_resources = set()
                
                try:
                    # Initialize feature extractor according to parser type
                    from parsers.feature_extractor import TreeSitterFeatureExtractor, CustomFeatureExtractor
                    if parser_type == ParserType.TREE_SITTER:
                        instance.feature_extractor = TreeSitterFeatureExtractor(language_id, file_type)
                    elif parser_type == ParserType.CUSTOM:
                        instance.feature_extractor = CustomFeatureExtractor(language_id, file_type)
                    initialized_resources.add("feature_extractor")
                    
                    # Initialize cache
                    instance._cache = UnifiedCache(f"parser_{language_id}")
                    await cache_coordinator.register_cache(instance._cache)
                    initialized_resources.add("cache")
                    
                    # Initialize cache analytics
                    analytics = await get_cache_analytics()
                    analytics.register_warmup_function(
                        f"parser_{language_id}",
                        instance._warmup_cache
                    )
                    await analytics.optimize_ttl_values()
                    initialized_resources.add("cache_analytics")
                    
                    # Initialize error analysis
                    await ErrorAudit.analyze_codebase(os.path.dirname(__file__))
                    initialized_resources.add("error_analysis")
                    
                    # Register with health monitor
                    global_health_monitor.register_component(
                        f"parser_{language_id}",
                        health_check=instance._check_health
                    )
                    initialized_resources.add("health_monitor")
                    
                    # Start warmup task
                    warmup_task = asyncio.create_task(instance._warmup_caches())
                    instance._pending_tasks.add(warmup_task)
                    
                    instance._initialized = True
                    await log(f"{language_id} parser initialized successfully", level="info")
                    return instance
                    
                except Exception as e:
                    # Cleanup any initialized resources
                    if "cache" in initialized_resources:
                        await cache_coordinator.unregister_cache(f"parser_{language_id}")
                    if "health_monitor" in initialized_resources:
                        global_health_monitor.unregister_component(f"parser_{language_id}")
                    raise
                    
        except Exception as e:
            await log(f"Error initializing {language_id} parser: {e}", level="error")
            # Cleanup on initialization failure
            await instance.cleanup()
            raise ProcessingError(f"Failed to initialize {language_id} parser: {e}")
    
    async def _warmup_caches(self):
        """Warm up caches with frequently used patterns."""
        try:
            # Get frequently used patterns
            async with transaction_scope() as txn:
                patterns = await txn.fetch("""
                    SELECT pattern_name, usage_count
                    FROM parser_usage_stats
                    WHERE usage_count > 10
                    ORDER BY usage_count DESC
                    LIMIT 100
                """)
                
                # Warm up pattern cache
                for pattern in patterns:
                    await self._warmup_cache([pattern["pattern_name"]])
                    
            self._warmup_complete = True
            await log(f"{self.language_id} parser cache warmup complete", level="info")
        except Exception as e:
            await log(f"Error warming up caches: {e}", level="error")

    async def _warmup_cache(self, keys: List[str]) -> Dict[str, Any]:
        """Warmup function for parser cache."""
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
        """Health check for parser."""
        # Get error audit data
        error_report = await ErrorAudit.get_error_report()
        
        # Get cache analytics
        analytics = await get_cache_analytics()
        cache_stats = await analytics.get_metrics()
        
        # Get resource usage
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        
        # Calculate average parse time
        avg_parse_time = sum(self._metrics["parse_times"]) / len(self._metrics["parse_times"]) if self._metrics["parse_times"] else 0
        
        # Calculate health status
        status = ComponentStatus.HEALTHY
        details = {
            "metrics": {
                "total_parsed": self._metrics["total_parsed"],
                "success_rate": self._metrics["successful_parses"] / self._metrics["total_parsed"] if self._metrics["total_parsed"] > 0 else 0,
                "cache_hit_rate": self._metrics["cache_hits"] / (self._metrics["cache_hits"] + self._metrics["cache_misses"]) if (self._metrics["cache_hits"] + self._metrics["cache_misses"]) > 0 else 0,
                "avg_parse_time": avg_parse_time
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
            details["reason"] = "Low parse success rate"
        elif error_report.get("error_rate", 0) > 0.1:  # More than 10% error rate
            status = ComponentStatus.DEGRADED
            details["reason"] = "High error rate"
        elif details["resource_usage"]["cpu_percent"] > 80:  # High CPU usage
            status = ComponentStatus.DEGRADED
            details["reason"] = "High CPU usage"
        elif avg_parse_time > 1.0:  # Average parse time > 1 second
            status = ComponentStatus.DEGRADED
            details["reason"] = "High parse times"
        elif not self._warmup_complete:  # Cache not ready
            status = ComponentStatus.DEGRADED
            details["reason"] = "Cache warmup incomplete"
            
        return {
            "status": status,
            "details": details
        }

    async def cleanup(self):
        """Clean up parser resources."""
        try:
            # Cancel all pending tasks
            if self._pending_tasks:
                for task in self._pending_tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                self._pending_tasks.clear()
            
            # Clean up feature extractor
            if self.feature_extractor:
                await self.feature_extractor.cleanup()
            
            # Clean up cache
            if self._cache:
                await self._cache.clear_async()
                await cache_coordinator.unregister_cache(f"parser_{self.language_id}")
            
            # Save error analysis
            await ErrorAudit.save_report()
            
            # Save cache analytics
            analytics = await get_cache_analytics()
            await analytics.save_metrics_history(self._cache.get_metrics())
            
            # Save metrics to database
            async with transaction_scope() as txn:
                await txn.execute("""
                    INSERT INTO parser_metrics (
                        timestamp, language_id, total_parsed,
                        successful_parses, failed_parses,
                        cache_hits, cache_misses, avg_parse_time
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """, (
                    time.time(),
                    self.language_id,
                    self._metrics["total_parsed"],
                    self._metrics["successful_parses"],
                    self._metrics["failed_parses"],
                    self._metrics["cache_hits"],
                    self._metrics["cache_misses"],
                    sum(self._metrics["parse_times"]) / len(self._metrics["parse_times"]) if self._metrics["parse_times"] else 0
                ))
            
            # Unregister from health monitor
            global_health_monitor.unregister_component(f"parser_{self.language_id}")
            
            self._initialized = False
            await log(f"Base parser cleaned up for {self.language_id}", level="info")
        except Exception as e:
            await log(f"Error cleaning up base parser for {self.language_id}: {e}", level="error")
            raise ProcessingError(f"Failed to cleanup base parser for {self.language_id}: {e}")

    def _create_node(self, node_type: str, start_point: List[int], end_point: List[int], **kwargs) -> BaseNodeDict:
        """Helper for creating a standardized AST node."""
        return {
            "type": node_type,
            "start_point": start_point,
            "end_point": end_point,
            "children": [],
            "metadata": {
                "category": self._get_node_category(node_type),
                "purpose": self._get_node_purpose(node_type),
                **kwargs.get("metadata", {})
            },
            **kwargs
        }

    def _get_node_category(self, node_type: str) -> PatternCategory:
        """Determine the category of a node based on its type."""
        for category in PatternCategory:
            for file_type in PATTERN_CATEGORIES.get(category, {}):
                for purpose in PATTERN_CATEGORIES[category][file_type]:
                    if node_type in PATTERN_CATEGORIES[category][file_type][purpose]:
                        return category
        
        # Enhanced default categorization
        if node_type in ['comment', 'docstring', 'javadoc']:
            return PatternCategory.DOCUMENTATION
        elif node_type in ['import', 'include', 'namespace', 'module']:
            return PatternCategory.DEPENDENCIES
        elif node_type in ['function', 'class', 'method', 'constructor']:
            return PatternCategory.SYNTAX
        elif node_type in ['type', 'variable', 'parameter']:
            return PatternCategory.SEMANTICS
        elif node_type in ['error', 'warning', 'issue']:
            return PatternCategory.COMMON_ISSUES
        elif node_type in ['pattern', 'style', 'convention']:
            return PatternCategory.USER_PATTERNS
        
        return PatternCategory.CODE_PATTERNS

    def _get_node_purpose(self, node_type: str) -> PatternPurpose:
        """Determine the purpose of a node based on its type."""
        # Check each category's patterns
        for category in PatternCategory:
            for file_type in PATTERN_CATEGORIES.get(category, {}):
                for purpose, patterns in PATTERN_CATEGORIES[category][file_type].items():
                    if node_type in patterns:
                        return purpose
        
        # Default to understanding if no specific purpose found
        return PatternPurpose.UNDERSTANDING

    def _compile_patterns(self, patterns_dict: dict) -> dict:
        """Helper to compile regex patterns from a definitions dictionary."""
        compiled = {}
        for category in patterns_dict:
            for purpose, patterns in patterns_dict[category].items():
                for name, pattern_obj in patterns.items():
                    try:
                        compiled[name] = re.compile(pattern_obj.pattern)
                    except Exception as e:
                        log(f"Error compiling pattern {name}: {e}", level="error")
        return compiled
    
    def _get_syntax_errors(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get syntax errors from AST."""
        return []

    async def _initialize_cache(self):
        """Initialize cache based on parser type."""
        if not self._cache:
            # Only initialize cache for custom parsers
            # Tree-sitter parsers use tree-sitter-language-pack's caching
            if self.parser_type == ParserType.CUSTOM:
                self._cache = UnifiedCache(f"parser_{self.language_id}")
                await cache_coordinator.register_cache(self._cache)
    
    async def _check_ast_cache(self, source_code: str) -> Optional[Dict[str, Any]]:
        """Check if an AST for this source code is already cached."""
        # Only use caching for custom parsers
        if self.parser_type != ParserType.CUSTOM or not self._cache:
            return None
            
        import hashlib
        source_hash = hashlib.md5(source_code.encode('utf8')).hexdigest()
        cache_key = f"ast:{self.language_id}:{source_hash}"
        
        async with AsyncErrorBoundary(f"check_ast_cache_{self.language_id}", error_types=(Exception,)):
            task = asyncio.create_task(self._cache.get(cache_key))
            self._pending_tasks.add(task)
            try:
                cached_ast = await task
                if cached_ast:
                    log(f"AST cache hit for {self.language_id}", level="debug")
                    return cached_ast
            finally:
                self._pending_tasks.remove(task)
        
        return None
            
    async def _store_ast_in_cache(self, source_code: str, ast: Dict[str, Any]) -> None:
        """Store an AST in the cache."""
        # Only cache for custom parsers
        if self.parser_type != ParserType.CUSTOM or not self._cache:
            return
            
        import hashlib
        source_hash = hashlib.md5(source_code.encode('utf8')).hexdigest()
        cache_key = f"ast:{self.language_id}:{source_hash}"
        
        async with AsyncErrorBoundary(f"store_ast_in_cache_{self.language_id}", error_types=(Exception,)):
            task = asyncio.create_task(self._cache.set(cache_key, ast))
            self._pending_tasks.add(task)
            try:
                await task
                log(f"AST cached for {self.language_id}", level="debug")
            finally:
                self._pending_tasks.remove(task)

    async def parse(self, source_code: str) -> Optional[ParserResult]:
        """[2.2] Unified parsing pipeline."""
        if not self._initialized:
            await self.ensure_initialized()
            
        async with AsyncErrorBoundary("parse_source", error_types=(Exception,)):
            # [2.2.1] Initialize Parser
            if not self._initialized and not await self.initialize():
                log(f"Failed to initialize {self.language_id} parser", level="error")
                return None

            # [2.2.2] Generate AST
            ast = None
            
            # For custom parsers, check cache first
            if self.parser_type == ParserType.CUSTOM:
                ast = await self._check_ast_cache(source_code)
            
            if not ast:
                # If not in cache or using tree-sitter, parse the source
                task = asyncio.create_task(self._parse_source(source_code))
                self._pending_tasks.add(task)
                try:
                    ast = await task
                finally:
                    self._pending_tasks.remove(task)
                
                # Cache AST for custom parsers
                if ast and self.parser_type == ParserType.CUSTOM:
                    await self._store_ast_in_cache(source_code, ast)
            
            if not ast:
                return None

            # [2.2.3] Extract Features
            task = asyncio.create_task(self.feature_extractor.extract_features(ast, source_code))
            self._pending_tasks.add(task)
            try:
                features = await task
            finally:
                self._pending_tasks.remove(task)

            # [2.2.4] Get Syntax Errors
            errors = self._get_syntax_errors(ast)

            # RETURNS: [models.py] ParserResult
            return ParserResult(
                success=True,
                ast=ast,
                features=features.features,
                documentation=features.documentation.__dict__,
                complexity=features.metrics.__dict__,
                statistics=self.stats.__dict__,
                errors=errors
            )
        
        return None

    def _extract_category_features(
        self,
        category: FeatureCategory,
        ast: Dict[str, Any],
        source_code: str
    ) -> Dict[str, Any]:
        """Extract features for a specific category."""
        patterns = self.feature_extractor._patterns  # Or use a proper getter if needed.
        
        if category == FeatureCategory.SYNTAX:
            return self._extract_syntax_features(ast, patterns)
        elif category == FeatureCategory.SEMANTICS:
            return self._extract_semantic_features(ast, patterns)
        elif category == FeatureCategory.DOCUMENTATION:
            return self._extract_documentation_features(source_code, patterns)
        elif category == FeatureCategory.STRUCTURE:
            return self._extract_structure_features(ast, patterns)
        
        return {}

    @handle_errors(error_types=(ProcessingError,))
    async def extract_patterns(self, source_code: str) -> List[Dict[str, Any]]:
        """
        Extract code patterns from source code for repository learning.
        
        Args:
            source_code: The content of the source code to extract patterns from
            
        Returns:
            List of extracted patterns with metadata
        """
        if not self._initialized:
            await self.ensure_initialized()

        patterns = []
        cache_key = f"patterns:{self.language_id}:{hash(source_code)}"
        
        try:
            # Check cache first
            cached_patterns = await cache_coordinator.get(cache_key)
            if cached_patterns:
                return cached_patterns
            
            async with AsyncErrorBoundary(
                operation_name=f"pattern_extraction_{self.language_id}",
                error_types=(ProcessingError,),
                severity=ErrorSeverity.ERROR
            ):
                # Start transaction for pattern extraction and storage
                async with transaction_scope() as txn:
                    # Update health status
                    await global_health_monitor.update_component_status(
                        f"parser_{self.language_id}",
                        ComponentStatus.HEALTHY,
                        details={
                            "operation": "pattern_extraction",
                            "source_size": len(source_code)
                        }
                    )
                    
                    try:
                        # Parse the source first
                        ast = await self._parse_source(source_code)
                        
                        # Use the language-specific pattern processor if available
                        from parsers.pattern_processor import pattern_processor
                        if hasattr(pattern_processor, 'extract_repository_patterns'):
                            language_patterns = await pattern_processor.extract_repository_patterns(
                                file_path="",  # Not needed for pattern extraction
                                source_code=source_code,
                                language=self.language_id
                            )
                            patterns.extend(language_patterns)
                            
                        # Add file type specific patterns
                        if self.file_type == FileType.CODE:
                            # Add code-specific pattern extraction
                            code_patterns = await self._extract_code_patterns(ast, source_code)
                            patterns.extend(code_patterns)
                        elif self.file_type == FileType.DOCUMENTATION:
                            # Add documentation-specific pattern extraction
                            doc_patterns = await self._extract_doc_patterns(ast, source_code)
                            patterns.extend(doc_patterns)
                        
                        # Store patterns in cache
                        if patterns:
                            await cache_coordinator.set(cache_key, patterns)
                            
                            # Store in database
                            for pattern in patterns:
                                await upsert_coordinator.upsert_pattern(
                                    pattern,
                                    self.language_id,
                                    None  # No repository context in direct extraction
                                )
                        
                        # Update final status
                        await global_health_monitor.update_component_status(
                            f"parser_{self.language_id}",
                            ComponentStatus.HEALTHY,
                            details={
                                "operation": "pattern_extraction_complete",
                                "patterns_found": len(patterns)
                            }
                        )
                        
                    except Exception as e:
                        await log(f"Error extracting patterns: {e}", level="error")
                        await global_health_monitor.update_component_status(
                            f"parser_{self.language_id}",
                            ComponentStatus.UNHEALTHY,
                            error=True,
                            details={
                                "operation": "pattern_extraction",
                                "error": str(e)
                            }
                        )
                        raise
                        
        except Exception as e:
            await log(f"Error in pattern extraction process: {e}", level="error")
            raise ProcessingError(f"Pattern extraction failed: {e}")
            
        return patterns
        
    def _extract_code_patterns(self, ast: Dict[str, Any], source_code: str) -> List[Dict[str, Any]]:
        """Extract code patterns from AST. Override in subclasses for language-specific behavior."""
        return []
        
    def _extract_doc_patterns(self, ast: Dict[str, Any], source_code: str) -> List[Dict[str, Any]]:
        """Extract documentation patterns from AST. Override in subclasses for language-specific behavior."""
        return []

    async def _load_patterns(self) -> None:
        """Load patterns for this parser's language."""
        if self.parser_type == ParserType.CUSTOM:
            try:
                # Try direct import first
                module_path = f"parsers.query_patterns.{self.language_id}"
                pattern_name = f"{self.language_id.upper()}_PATTERNS"
                
                try:
                    module = importlib.import_module(module_path)
                    patterns = getattr(module, pattern_name)
                    self._patterns = self._compile_patterns(patterns)
                    log(f"Loaded patterns directly for {self.language_id}", level="debug")
                except (ImportError, AttributeError) as e:
                    log(f"Could not load patterns directly for {self.language_id}: {e}", level="debug")
                    
                    # Fallback to dynamic loading through pattern processor
                    from parsers.pattern_processor import pattern_processor
                    patterns = await pattern_processor.get_patterns_for_file(self.language_id)
                    if patterns:
                        self._patterns = self._compile_patterns(patterns)
                        log(f"Loaded patterns dynamically for {self.language_id}", level="debug")
                    else:
                        log(f"No patterns found for {self.language_id}", level="warning")
                        
            except Exception as e:
                log(f"Error loading patterns for {self.language_id}: {e}", level="error")
                raise ProcessingError(f"Failed to load patterns for {self.language_id}: {e}") 

    async def process_with_ai(
        self,
        source_code: str,
        context: AIContext
    ) -> AIProcessingResult:
        """Process source code with AI assistance."""
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary(f"{self.language_id} AI processing"):
            try:
                # Parse the source first
                parse_result = await self.parse(source_code)
                if not parse_result or not parse_result.success:
                    return AIProcessingResult(
                        success=False,
                        response="Failed to parse source code"
                    )
                
                # Process with AI based on capabilities
                results = AIProcessingResult(success=True)
                
                if AICapability.CODE_UNDERSTANDING in self.ai_capabilities:
                    understanding = await self._process_with_understanding(parse_result, context)
                    results.context_info.update(understanding)
                
                if AICapability.CODE_GENERATION in self.ai_capabilities:
                    generation = await self._process_with_generation(parse_result, context)
                    results.suggestions.extend(generation)
                
                if AICapability.CODE_MODIFICATION in self.ai_capabilities:
                    modification = await self._process_with_modification(parse_result, context)
                    results.ai_insights.update(modification)
                
                return results
            except Exception as e:
                log(f"Error in {self.language_id} AI processing: {e}", level="error")
                return AIProcessingResult(
                    success=False,
                    response=f"Error processing with AI: {str(e)}"
                )
    
    async def _process_with_understanding(
        self,
        parse_result: ParserResult,
        context: AIContext
    ) -> Dict[str, Any]:
        """Process with code understanding capability."""
        understanding = {}
        
        # Extract code structure
        if parse_result.ast:
            understanding["structure"] = self._analyze_code_structure(parse_result.ast)
        
        # Extract semantic information
        if parse_result.features:
            understanding["semantics"] = self._analyze_semantics(parse_result.features)
        
        # Add documentation insights
        if parse_result.documentation:
            understanding["documentation"] = parse_result.documentation
        
        return understanding
    
    async def _process_with_generation(
        self,
        parse_result: ParserResult,
        context: AIContext
    ) -> List[str]:
        """Process with code generation capability."""
        suggestions = []
        
        # Generate completion suggestions
        if parse_result.ast:
            completions = await self._generate_completions(parse_result.ast, context)
            suggestions.extend(completions)
        
        # Generate improvement suggestions
        if parse_result.features:
            improvements = await self._generate_improvements(parse_result.features, context)
            suggestions.extend(improvements)
        
        return suggestions
    
    async def _process_with_modification(
        self,
        parse_result: ParserResult,
        context: AIContext
    ) -> Dict[str, Any]:
        """Process with code modification capability."""
        insights = {}
        
        # Analyze modification impact
        if parse_result.ast:
            insights["impact"] = await self._analyze_modification_impact(parse_result.ast, context)
        
        # Generate modification suggestions
        if parse_result.features:
            insights["suggestions"] = await self._generate_modification_suggestions(
                parse_result.features,
                context
            )
        
        return insights
    
    async def _analyze_code_structure(self, ast: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze code structure from AST."""
        return {
            "node_types": self._count_node_types(ast),
            "depth": self._calculate_ast_depth(ast),
            "complexity": self._calculate_structural_complexity(ast)
        }
    
    async def _analyze_semantics(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze semantic information from features."""
        return {
            "types": self._extract_type_information(features),
            "dependencies": self._extract_dependencies(features),
            "patterns": self._identify_code_patterns(features)
        }
    
    async def _generate_completions(
        self,
        ast: Dict[str, Any],
        context: AIContext
    ) -> List[str]:
        """Generate code completion suggestions."""
        completions = []
        
        # Add completion suggestions based on AST analysis
        if "cursor_position" in context.interaction.__dict__:
            node = self._find_node_at_position(ast, context.interaction.cursor_position)
            if node:
                completions.extend(self._generate_node_completions(node))
        
        return completions
    
    async def _generate_improvements(
        self,
        features: Dict[str, Any],
        context: AIContext
    ) -> List[str]:
        """Generate code improvement suggestions."""
        improvements = []
        
        # Add improvement suggestions based on feature analysis
        for category in features:
            category_improvements = self._generate_category_improvements(
                category,
                features[category],
                context
            )
            improvements.extend(category_improvements)
        
        return improvements
    
    async def _analyze_modification_impact(
        self,
        ast: Dict[str, Any],
        context: AIContext
    ) -> Dict[str, Any]:
        """Analyze impact of potential modifications."""
        return {
            "affected_nodes": self._find_affected_nodes(ast, context),
            "complexity_change": self._estimate_complexity_change(ast, context),
            "risk_assessment": self._assess_modification_risk(ast, context)
        }
    
    async def _generate_modification_suggestions(
        self,
        features: Dict[str, Any],
        context: AIContext
    ) -> List[Dict[str, Any]]:
        """Generate suggestions for code modifications."""
        suggestions = []
        
        # Generate suggestions based on feature analysis
        for category in features:
            category_suggestions = self._generate_category_modifications(
                category,
                features[category],
                context
            )
            suggestions.extend(category_suggestions)
        
        return suggestions 

    async def _initialize_ai_deep_learning(self):
        """Initialize deep learning capabilities."""
        if AICapability.DEEP_LEARNING in self.ai_capabilities:
            self._deep_learning_cache = {}
            self._pattern_learning_results = {}
            
    async def learn_from_repositories(self, repo_ids: List[int]) -> Dict[str, Any]:
        """Learn patterns from multiple repositories."""
        if not self._initialized:
            await self.ensure_initialized()
            
        results = await self._ai_processor.deep_learn_from_multiple_repositories(repo_ids)
        return results 