"""Base parser implementation.

This module provides the base parser implementation that both tree-sitter and custom parsers extend.
Tree-sitter support is provided through tree-sitter-language-pack.
Integrates with cache analytics, error handling, and logging systems.
"""

from typing import Dict, Optional, Set, List, Any, Union, TYPE_CHECKING, ForwardRef
import asyncio
import importlib
import re
import time
from dataclasses import dataclass, field
from tree_sitter_language_pack import get_binding, get_language, get_parser, SupportedLanguage
from parsers.types import (
    FileType, ParserType, AICapability, AIContext, AIProcessingResult,
    InteractionType, ConfidenceLevel, ParserResult, PatternCategory, PatternPurpose,
    ExtractedFeatures, FeatureCategory, PatternValidationResult
)
from parsers.models import (
    FileClassification, BaseNodeDict, PATTERN_CATEGORIES,
    Documentation, ComplexityMetrics
)
from parsers.parser_interfaces import BaseParserInterface, AIParserInterface
from utils.logger import log
from utils.error_handling import (
    AsyncErrorBoundary,
    handle_async_errors,
    handle_errors,
    ProcessingError,
    ErrorAudit,
    ErrorSeverity
)
from utils.shutdown import register_shutdown_handler
from utils.cache import UnifiedCache, cache_coordinator
from utils.cache_analytics import get_cache_analytics, CacheAnalytics
from utils.health_monitor import ComponentStatus, global_health_monitor, monitor_operation
from utils.async_runner import submit_async_task, cleanup_tasks
from utils.request_cache import request_cache_context, cached_in_request, get_current_request_cache
from db.transaction import transaction_scope, get_transaction_coordinator
from db.upsert_ops import coordinator as upsert_coordinator
import traceback

if TYPE_CHECKING:
    from parsers.tree_sitter_parser import TreeSitterParser

@dataclass
class BaseParser(BaseParserInterface, AIParserInterface):
    """Base parser implementation with AI capabilities.
    
    This class provides a complete implementation of both BaseParserInterface and
    AIParserInterface, serving as the foundation for language-specific parsers.
    
    Attributes:
        language_id (str): The identifier for the language this parser handles
        file_type (FileType): The type of files this parser can process
        parser_type (ParserType): The type of parser implementation
        _initialized (bool): Whether the parser has been initialized
        _pending_tasks (Set[asyncio.Task]): Set of pending async tasks
        _metrics (Dict[str, Any]): Parser performance metrics
    """
    
    def __init__(self, language_id: str, file_type: FileType, parser_type: ParserType):
        """Initialize base parser.
        
        Args:
            language_id: The identifier for the language this parser handles
            file_type: The type of files this parser can process
            parser_type: The type of parser implementation
        """
        # Initialize both parent interfaces
        BaseParserInterface.__init__(self, language_id, file_type, parser_type)
        AIParserInterface.__init__(
            self,
            language_id=language_id,
            file_type=file_type,
            capabilities={
                AICapability.CODE_UNDERSTANDING,
                AICapability.CODE_GENERATION,
                AICapability.CODE_MODIFICATION,
                AICapability.CODE_REVIEW,
                AICapability.LEARNING
            }
        )
        
        self._pending_tasks: Set[asyncio.Task] = set()
        self._lock = asyncio.Lock()
        self._metrics = {
            "total_parsed": 0,
            "successful_parses": 0,
            "failed_parses": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "parse_times": []
        }
        self._warmup_complete = False
        self._error_recovery_stats = {
            "total_errors": 0,
            "recovered_errors": 0,
            "failed_recoveries": 0,
            "recovery_strategies": {},
            "error_patterns": {}
        }
        self._recovery_strategies = {}
        self._error_patterns = {}
        self._recovery_learning_enabled = True
        
        # Initialize caches with standardized naming
        self._ast_cache = UnifiedCache(f"{self.language_id}_ast")
        self._feature_cache = UnifiedCache(f"{self.language_id}_features")
        
        # Register with shutdown handler
        register_shutdown_handler(self._cleanup)
    
    async def initialize(self) -> bool:
        """Initialize the parser.
        
        Returns:
            bool: True if initialization was successful
            
        Raises:
            ProcessingError: If initialization fails
        """
        try:
            async with AsyncErrorBoundary(f"base_parser_initialization_{self.language_id}"):
                # Wait for database initialization
                from db.transaction import get_transaction_coordinator
                transaction_coordinator = await get_transaction_coordinator()
                if not await transaction_coordinator.is_ready():
                    await log(f"Database not ready for {self.language_id} parser", level="warning")
                    return False

                # Initialize health monitoring
                await global_health_monitor.update_component_status(
                    f"parser_{self.language_id}",
                    ComponentStatus.INITIALIZING,
                    details={"stage": "starting"}
                )
                
                # Register caches
                await cache_coordinator.register_cache(f"{self.language_id}_ast", self._ast_cache)
                await cache_coordinator.register_cache(f"{self.language_id}_features", self._feature_cache)
                
                # Initialize cache analytics
                analytics = await get_cache_analytics()
                analytics.register_warmup_function(
                    f"{self.language_id}_ast",
                    self._warmup_ast_cache
                )
                analytics.register_warmup_function(
                    f"{self.language_id}_features",
                    self._warmup_feature_cache
                )
                
                # Start warmup task through async_runner
                warmup_task = submit_async_task(self._warmup_caches())
                await asyncio.wrap_future(warmup_task)
                
                self._initialized = True
                await log(f"Base parser initialized for {self.language_id}", level="info")
                
                # Update final health status
                await self._check_health()
                
                return True
                
        except Exception as e:
            await log(f"Error initializing base parser for {self.language_id}: {e}", level="error")
            await global_health_monitor.update_component_status(
                f"parser_{self.language_id}",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"initialization_error": str(e)}
            )
            raise ProcessingError(f"Failed to initialize base parser for {self.language_id}: {e}")
    
    @handle_async_errors(error_types=ProcessingError)
    @cached_in_request
    async def parse(self, source_code: str) -> Optional[ParserResult]:
        """Parse source code using the appropriate parser.
        
        Args:
            source_code: The source code to parse
            
        Returns:
            Optional[ParserResult]: The parsing result or None if parsing failed
        """
        if not self._initialized:
            await self.ensure_initialized()
        
        start_time = time.time()
        self._metrics["total_parsed"] += 1
        
        try:
            async with AsyncErrorBoundary(f"{self.language_id} parsing"):
                async with request_cache_context() as cache:
                    # Check cache first
                    cache_key = f"ast:{self.language_id}:{hash(source_code)}"
                    cached_result = await self._ast_cache.get_async(cache_key)
                    if cached_result:
                        self._metrics["cache_hits"] += 1
                        return ParserResult(**cached_result)
                    
                    self._metrics["cache_misses"] += 1
                    
                    # Parse with error recovery
                    try:
                        with monitor_operation("parse", f"parser_{self.language_id}"):
                            ast = await self._parse_source(source_code)
                    except Exception as e:
                        await log(f"Primary parse failed: {e}", level="warning")
                        context = {
                            "language_id": self.language_id,
                            "file_type": self.file_type.value,
                            "parser_type": self.parser_type.value,
                            "source_code": source_code
                        }
                        recovery_result = await self.recover_from_parsing_error(e, context)
                        if not recovery_result:
                            raise ProcessingError(f"All parsing attempts failed for {self.language_id}")
                        ast = recovery_result
                    
                    # Extract features
                    features = await self.extract_features(ast, source_code)
                    
                    # Create result
                    result = ParserResult(
                        success=True,
                        file_type=self.file_type,
                        parser_type=self.parser_type,
                        language=self.language_id,
                        features=features,
                        ast=ast
                    )
                    
                    # Cache result
                    await self._ast_cache.set_async(cache_key, result.__dict__)
                    
                    # Update metrics
                    self._metrics["successful_parses"] += 1
                    parse_time = time.time() - start_time
                    self._metrics["parse_times"].append(parse_time)
                    
                    return result
                    
        except Exception as e:
            self._metrics["failed_parses"] += 1
            await log(f"Error parsing with {self.language_id}: {e}", level="error")
            await ErrorAudit.record_error(
                e,
                f"{self.language_id}_parse",
                ProcessingError,
                context={"parse_time": time.time() - start_time}
            )
            return None
    
    @handle_async_errors(error_types=ProcessingError)
    async def extract_features(
        self,
        ast: Dict[str, Any],
        source_code: str,
        pattern_processor: Optional[Any] = None,
        parser_type: Optional[ParserType] = None
    ) -> ExtractedFeatures:
        """Extract features from AST.
        
        Args:
            ast: The AST to extract features from
            source_code: The original source code
            pattern_processor: Optional pattern processor for enhanced extraction
            parser_type: Optional parser type for specific extraction logic
            
        Returns:
            ExtractedFeatures: The extracted features
        """
        if not self._initialized:
            await self.ensure_initialized()
        
        try:
            async with AsyncErrorBoundary(f"{self.language_id} feature extraction"):
                # Check cache first
                cache_key = f"features:{self.language_id}:{hash(source_code)}"
                cached_features = await self._feature_cache.get_async(cache_key)
                if cached_features:
                    return ExtractedFeatures(**cached_features)
                
                # Extract basic features
                features = await self._extract_basic_features(source_code)
                
                # Extract enhanced features if pattern processor available
                if pattern_processor:
                    enhanced_features = await pattern_processor.extract_features(
                        ast,
                        source_code,
                        self.language_id,
                        parser_type or self.parser_type
                    )
                    features.update(enhanced_features)
                
                # Cache features
                await self._feature_cache.set_async(cache_key, features)
                
                return ExtractedFeatures(**features)
                
        except Exception as e:
            await log(f"Error extracting features: {e}", level="error")
            return ExtractedFeatures()
    
    async def validate(self, source_code: str) -> PatternValidationResult:
        """Validate source code using the parser.
        
        Args:
            source_code: The source code to validate
            
        Returns:
            PatternValidationResult: The validation result
        """
        if not self._initialized:
            await self.ensure_initialized()
        
        try:
            async with AsyncErrorBoundary(f"{self.language_id} validation"):
                # Parse first
                parse_result = await self.parse(source_code)
                if not parse_result or not parse_result.success:
                    return PatternValidationResult(
                        is_valid=False,
                        errors=["Failed to parse source code"]
                    )
                
                # Validate AST
                validation_time = time.time()
                errors = await self._validate_ast(parse_result.ast)
                validation_time = time.time() - validation_time
                
                return PatternValidationResult(
                    is_valid=len(errors) == 0,
                    errors=errors,
                    validation_time=validation_time
                )
                
        except Exception as e:
            await log(f"Error validating source code: {e}", level="error")
            return PatternValidationResult(
                is_valid=False,
                errors=[str(e)]
            )
    
    async def process_with_ai(
        self,
        source_code: str,
        context: AIContext
    ) -> AIProcessingResult:
        """Process source code with AI assistance.
        
        Args:
            source_code: The source code to process
            context: The AI processing context
            
        Returns:
            AIProcessingResult: The AI processing result
        """
        if not self._initialized:
            await self.ensure_initialized()
        
        try:
            async with AsyncErrorBoundary(f"{self.language_id} AI processing"):
                # Parse first
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
            await log(f"Error in AI processing: {e}", level="error")
            return AIProcessingResult(
                success=False,
                response=f"Error processing with AI: {str(e)}"
            )
    
    async def learn_from_code(
        self,
        source_code: str,
        context: AIContext
    ) -> List[Dict[str, Any]]:
        """Learn patterns from source code.
        
        Args:
            source_code: The source code to learn from
            context: The AI learning context
            
        Returns:
            List[Dict[str, Any]]: The learned patterns
        """
        if not self._initialized:
            await self.ensure_initialized()
        
        try:
            async with AsyncErrorBoundary(f"{self.language_id} pattern learning"):
                # Parse first
                parse_result = await self.parse(source_code)
                if not parse_result or not parse_result.success:
                    return []
                
                # Extract features
                features = await self.extract_features(parse_result.ast, source_code)
                
                # Learn patterns
                patterns = []
                if AICapability.LEARNING in self.ai_capabilities:
                    patterns = await self._learn_patterns(features, context)
                
                return patterns
                
        except Exception as e:
            await log(f"Error learning patterns: {e}", level="error")
            return []
    
    async def _cleanup(self) -> None:
        """Internal cleanup method registered with shutdown handler."""
        try:
            if not self._initialized:
                return
            
            # Update status
            await global_health_monitor.update_component_status(
                f"parser_{self.language_id}",
                ComponentStatus.SHUTTING_DOWN,
                details={"stage": "starting"}
            )
            
            # Cancel any pending tasks
            for task in self._pending_tasks.copy():
                if not task.done():
                    task.cancel()
            
            # Wait for tasks to complete with timeout
            if self._pending_tasks:
                try:
                    await asyncio.wait_for(
                        asyncio.gather(*self._pending_tasks, return_exceptions=True),
                        timeout=5.0
                    )
                except asyncio.TimeoutError:
                    await log(f"Timeout waiting for tasks to complete in {self.language_id} parser", level="warning")
                except Exception as e:
                    await log(f"Error waiting for tasks in {self.language_id} parser: {e}", level="error")
                finally:
                    self._pending_tasks.clear()
            
            # Clean up caches
            await cache_coordinator.unregister_cache(f"{self.language_id}_ast")
            await cache_coordinator.unregister_cache(f"{self.language_id}_features")
            
            # Save metrics
            async with transaction_scope() as txn:
                await txn.execute("""
                    INSERT INTO parser_metrics (
                        timestamp, language_id, total_parses,
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
            
            self._initialized = False
            await log(f"Base parser cleaned up for {self.language_id}", level="info")
            
            # Update final status
            await global_health_monitor.update_component_status(
                f"parser_{self.language_id}",
                ComponentStatus.SHUTDOWN,
                details={"cleanup": "successful"}
            )
            
        except Exception as e:
            await log(f"Error cleaning up base parser: {e}", level="error")
            await global_health_monitor.update_component_status(
                f"parser_{self.language_id}",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"cleanup_error": str(e)}
            )
            raise ProcessingError(f"Failed to cleanup base parser: {e}")
    
    async def cleanup(self) -> None:
        """Public cleanup method that ensures cleanup is handled through async_runner."""
        cleanup_task = submit_async_task(self._cleanup())
        await asyncio.wrap_future(cleanup_task)

    # Keep existing methods but update to use async_runner for tasks
    async def _submit_task(self, coro) -> Any:
        """Submit a task through async_runner."""
        task = submit_async_task(coro)
        try:
            return await asyncio.wrap_future(task)
        except Exception as e:
            await log(f"Error in task execution: {e}", level="error")
            raise

    async def _warmup_ast_cache(self, keys: List[str]) -> Dict[str, Any]:
        """Warmup function for AST cache."""
        results = {}
        for key in keys:
            try:
                # Parse some sample code for warmup
                sample_code = "// Sample code for warmup"
                ast = await self._parse_source(sample_code)
                if ast:
                    results[key] = ast
            except Exception as e:
                await log(f"Error warming up AST cache for {key}: {e}", level="warning")
        return results

    async def _warmup_feature_cache(self, keys: List[str]) -> Dict[str, Any]:
        """Warmup function for feature cache."""
        results = {}
        for key in keys:
            try:
                # Extract features from sample AST for warmup
                sample_ast = {"type": "root", "children": []}
                features = await self.extract_features(sample_ast, "")
                if features:
                    results[key] = features
            except Exception as e:
                await log(f"Error warming up feature cache for {key}: {e}", level="warning")
        return results

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

    async def recover_from_error(
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
                            # Import here to avoid circular dependency
                            from parsers.tree_sitter_parser import TreeSitterParser
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

    async def _check_health(self) -> Dict[str, Any]:
        """Comprehensive health check."""
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