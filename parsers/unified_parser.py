"""Unified parsing interface.

Pipeline Stages:
1. File Classification & Parser Selection
   - Uses: parsers/file_classification.py -> get_file_classification()
     Returns: Optional[FileClassification]
   - Uses: parsers/language_support.py -> language_registry.get_parser()
     Returns: Optional[BaseParser]

2. Content Parsing
   - Uses: parsers/base_parser.py -> BaseParser.parse()
     Returns: Optional[ParserResult]

3. Feature Extraction
   - Uses: parsers/base_parser.py -> BaseParser._extract_category_features()
     Returns: ExtractedFeatures

4. Result Standardization
   - Returns: Optional[ParserResult]
"""

from typing import Optional, Set, Dict, Any, List, Union
import asyncio
from dataclasses import dataclass, field
from parsers.types import (
    FileType, ParserType, AICapability, AIContext, AIProcessingResult,
    InteractionType, ConfidenceLevel, PatternCategory
)
from parsers.models import (
    FileClassification, ParserResult, BaseNodeDict,
    TreeSitterNodeDict
)
from parsers.parser_interfaces import BaseParserInterface, AIParserInterface
from parsers.language_mapping import (
    get_parser_type,
    get_file_type,
    get_ai_capabilities,
    get_complete_language_info
)
from parsers.tree_sitter_parser import get_tree_sitter_parser
from parsers.custom_parsers import get_custom_parser
from utils.error_handling import handle_async_errors, ParsingError, AsyncErrorBoundary, ErrorSeverity, ProcessingError
from utils.encoding import encode_query_pattern
from utils.logger import log
from utils.cache import cache_coordinator, UnifiedCache
from utils.shutdown import register_shutdown_handler
from db.transaction import transaction_scope
from db.upsert_ops import coordinator as upsert_coordinator
from utils.health_monitor import global_health_monitor
from utils.health_monitor import ComponentStatus

@dataclass
class UnifiedParser(BaseParserInterface, AIParserInterface):
    """[5.1] Unified parser implementation with AI capabilities."""
    
    def __init__(self, language_id: str):
        """Initialize unified parser."""
        super().__init__(
            language_id=language_id,
            file_type=FileType.CODE,
            parser_type=ParserType.HYBRID,
            capabilities={
                AICapability.CODE_UNDERSTANDING,
                AICapability.CODE_GENERATION,
                AICapability.CODE_MODIFICATION,
                AICapability.CODE_REVIEW,
                AICapability.DOCUMENTATION,
                AICapability.LEARNING
            }
        )
        self._initialized = False
        self._pending_tasks: Set[asyncio.Task] = set()
        self._tree_sitter_parser = None
        self._custom_parser = None
        self._cache = None
        self._lock = asyncio.Lock()
    
    async def ensure_initialized(self):
        """Ensure the parser is initialized."""
        if not self._initialized:
            raise ProcessingError(f"Unified parser not initialized for {self.language_id}. Use create() to initialize.")
        return True
    
    @classmethod
    async def create(cls, language_id: str) -> 'UnifiedParser':
        """[5.1.1] Create and initialize a unified parser instance."""
        instance = cls(language_id)
        try:
            async with AsyncErrorBoundary(f"unified_parser_initialization_{language_id}"):
                # Get language information
                language_info = get_complete_language_info(language_id)
                
                # Initialize tree-sitter parser if available
                if language_info["parser_type"] == ParserType.TREE_SITTER:
                    instance._tree_sitter_parser = await get_tree_sitter_parser(language_id)
                
                # Initialize custom parser if available
                if (language_info["parser_type"] == ParserType.CUSTOM or
                    language_info["fallback_parser_type"] == ParserType.CUSTOM):
                    instance._custom_parser = await get_custom_parser(language_id)
                
                # Initialize cache
                instance._cache = UnifiedCache(f"unified_parser_{language_id}")
                await cache_coordinator.register_cache(instance._cache)
                
                # Register shutdown handler
                register_shutdown_handler(instance.cleanup)
                
                instance._initialized = True
                log(f"Unified parser initialized for {language_id}", level="info")
                return instance
        except Exception as e:
            log(f"Error initializing unified parser for {language_id}: {e}", level="error")
            # Cleanup on initialization failure
            await instance.cleanup()
            raise ProcessingError(f"Failed to initialize unified parser for {language_id}: {e}")
    
    async def parse(self, source_code: str) -> Optional[ParserResult]:
        """[5.1.2] Parse source code using available parsers."""
        if not self._initialized:
            await self.ensure_initialized()
            
        async with AsyncErrorBoundary(f"unified_parse_{self.language_id}"):
            try:
                # Check cache first
                cache_key = f"ast:{hash(source_code)}"
                cached_result = await self._cache.get(cache_key)
                if cached_result:
                    return ParserResult(**cached_result)
                
                # Try tree-sitter parser first
                if self._tree_sitter_parser:
                    result = await self._tree_sitter_parser.parse(source_code)
                    if result and result.success:
                        # Cache successful result
                        await self._cache.set(cache_key, result.__dict__)
                        return result
                
                # Fall back to custom parser
                if self._custom_parser:
                    result = await self._custom_parser.parse(source_code)
                    if result and result.success:
                        # Cache successful result
                        await self._cache.set(cache_key, result.__dict__)
                        return result
                
                return None
            except Exception as e:
                log(f"Error parsing {self.language_id} code: {e}", level="error")
                return None
    
    async def process_with_ai(
        self,
        source_code: str,
        context: AIContext
    ) -> AIProcessingResult:
        """[5.1.3] Process source code with AI assistance."""
        if not self._initialized:
            await self.ensure_initialized()
            
        async with AsyncErrorBoundary(f"unified_ai_processing_{self.language_id}"):
            try:
                results = AIProcessingResult(success=True)
                
                # Parse source code first
                parse_result = await self.parse(source_code)
                if not parse_result or not parse_result.success:
                    return AIProcessingResult(
                        success=False,
                        response="Failed to parse source code"
                    )
                
                # Process with understanding capability
                if AICapability.CODE_UNDERSTANDING in self.capabilities:
                    understanding = await self._process_with_understanding(parse_result, context)
                    results.context_info.update(understanding)
                
                # Process with generation capability
                if AICapability.CODE_GENERATION in self.capabilities:
                    generation = await self._process_with_generation(parse_result, context)
                    results.suggestions.extend(generation)
                
                # Process with modification capability
                if AICapability.CODE_MODIFICATION in self.capabilities:
                    modification = await self._process_with_modification(parse_result, context)
                    results.ai_insights.update(modification)
                
                # Process with review capability
                if AICapability.CODE_REVIEW in self.capabilities:
                    review = await self._process_with_review(parse_result, context)
                    results.ai_insights.update(review)
                
                # Process with documentation capability
                if AICapability.DOCUMENTATION in self.capabilities:
                    documentation = await self._process_with_documentation(parse_result, context)
                    results.ai_insights.update(documentation)
                
                # Process with learning capability
                if AICapability.LEARNING in self.capabilities:
                    learning = await self._process_with_learning(parse_result, context)
                    results.learned_patterns.extend(learning)
                
                return results
            except Exception as e:
                log(f"Error in unified AI processing for {self.language_id}: {e}", level="error")
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
        
        # Update categories to process
        categories_to_process = [
            PatternCategory.SYNTAX,
            PatternCategory.SEMANTICS,
            PatternCategory.CODE_PATTERNS,
            PatternCategory.BEST_PRACTICES,    # Added
            PatternCategory.COMMON_ISSUES,     # Added
            PatternCategory.USER_PATTERNS,     # Added
            PatternCategory.DEPENDENCIES       # Added
        ]
        
        for category in categories_to_process:
            if category in parse_result.features:
                understanding[category.value] = await self._analyze_category(
                    category,
                    parse_result.features[category]
                )
        
        return understanding
    
    async def _process_with_generation(
        self,
        parse_result: ParserResult,
        context: AIContext
    ) -> List[str]:
        """[5.1.5] Process with code generation capability."""
        suggestions = []
        
        # Try tree-sitter parser first
        if self._tree_sitter_parser:
            tree_sitter_suggestions = await self._tree_sitter_parser._process_with_generation(
                parse_result,
                context
            )
            suggestions.extend(tree_sitter_suggestions)
        
        # Add custom parser suggestions
        if self._custom_parser:
            custom_suggestions = await self._custom_parser._process_with_generation(
                parse_result,
                context
            )
            suggestions.extend(custom_suggestions)
        
        return suggestions
    
    async def _process_with_modification(
        self,
        parse_result: ParserResult,
        context: AIContext
    ) -> Dict[str, Any]:
        """[5.1.6] Process with code modification capability."""
        insights = {}
        
        # Try tree-sitter parser first
        if self._tree_sitter_parser:
            tree_sitter_insights = await self._tree_sitter_parser._process_with_modification(
                parse_result,
                context
            )
            insights.update(tree_sitter_insights)
        
        # Add custom parser insights
        if self._custom_parser:
            custom_insights = await self._custom_parser._process_with_modification(
                parse_result,
                context
            )
            insights.update(custom_insights)
        
        return insights
    
    async def _process_with_review(
        self,
        parse_result: ParserResult,
        context: AIContext
    ) -> Dict[str, Any]:
        """[5.1.7] Process with code review capability."""
        review = {}
        
        # Try tree-sitter parser first
        if self._tree_sitter_parser:
            tree_sitter_review = await self._tree_sitter_parser._process_with_review(
                parse_result,
                context
            )
            review.update(tree_sitter_review)
        
        # Add custom parser review
        if self._custom_parser:
            custom_review = await self._custom_parser._process_with_review(
                parse_result,
                context
            )
            review.update(custom_review)
        
        return review
    
    async def _process_with_documentation(
        self,
        parse_result: ParserResult,
        context: AIContext
    ) -> Dict[str, Any]:
        """[5.1.8] Process with documentation capability."""
        documentation = {}
        
        # Try tree-sitter parser first
        if self._tree_sitter_parser:
            tree_sitter_docs = await self._tree_sitter_parser._process_with_documentation(
                parse_result,
                context
            )
            documentation.update(tree_sitter_docs)
        
        # Add custom parser documentation
        if self._custom_parser:
            custom_docs = await self._custom_parser._process_with_documentation(
                parse_result,
                context
            )
            documentation.update(custom_docs)
        
        return documentation
    
    async def _process_with_learning(
        self,
        parse_result: ParserResult,
        context: AIContext
    ) -> List[Dict[str, Any]]:
        """[5.1.9] Process with learning capability."""
        if not self._initialized:
            await self.ensure_initialized()
            
        patterns = []
        
        async with AsyncErrorBoundary(
            operation_name="pattern_learning",
            error_types=(ProcessingError,),
            severity=ErrorSeverity.ERROR
        ):
            try:
                # Get pattern processor instance
                from parsers.pattern_processor import pattern_processor
                from parsers.ai_pattern_processor import ai_pattern_processor
                
                # Start transaction for pattern processing
                async with transaction_scope() as txn:
                    # Update health status
                    await global_health_monitor.update_component_status(
                        f"parser_{self.language_id}",
                        ComponentStatus.HEALTHY,
                        details={
                            "operation": "pattern_learning",
                            "context": context.__dict__
                        }
                    )
                    
                    # Process with tree-sitter parser
                    if self._tree_sitter_parser:
                        try:
                            tree_sitter_patterns = await self._tree_sitter_parser._process_with_learning(
                                parse_result,
                                context
                            )
                            # Validate and enhance patterns
                            for pattern in tree_sitter_patterns:
                                if await pattern_processor.validate_pattern(pattern, self.language_id):
                                    # Enhance with AI insights
                                    enhanced = await ai_pattern_processor.process_pattern(
                                        pattern,
                                        context
                                    )
                                    if enhanced.success:
                                        pattern.update(enhanced.ai_insights)
                                    patterns.append(pattern)
                        except Exception as e:
                            await log(f"Error in tree-sitter pattern learning: {e}", level="error")
                            await global_health_monitor.update_component_status(
                                f"parser_{self.language_id}",
                                ComponentStatus.DEGRADED,
                                error=True,
                                details={
                                    "operation": "tree_sitter_pattern_learning",
                                    "error": str(e)
                                }
                            )
                    
                    # Process with custom parser
                    if self._custom_parser:
                        try:
                            custom_patterns = await self._custom_parser._process_with_learning(
                                parse_result,
                                context
                            )
                            # Validate and enhance patterns
                            for pattern in custom_patterns:
                                if await pattern_processor.validate_pattern(pattern, self.language_id):
                                    # Enhance with AI insights
                                    enhanced = await ai_pattern_processor.process_pattern(
                                        pattern,
                                        context
                                    )
                                    if enhanced.success:
                                        pattern.update(enhanced.ai_insights)
                                    patterns.append(pattern)
                        except Exception as e:
                            await log(f"Error in custom pattern learning: {e}", level="error")
                            await global_health_monitor.update_component_status(
                                f"parser_{self.language_id}",
                                ComponentStatus.DEGRADED,
                                error=True,
                                details={
                                    "operation": "custom_pattern_learning",
                                    "error": str(e)
                                }
                            )
                    
                    # Analyze pattern relationships
                    if patterns:
                        relationships = await pattern_processor.analyze_pattern_relationships(patterns)
                        
                        # Store patterns and relationships
                        for pattern in patterns:
                            # Store pattern
                            await upsert_coordinator.upsert_pattern(
                                pattern,
                                self.language_id,
                                context.repository_id if context else None
                            )
                            
                            # Store relationships
                            if pattern["id"] in relationships:
                                for rel in relationships[pattern["id"]]:
                                    await upsert_coordinator.upsert_pattern_relationship(
                                        pattern["id"],
                                        rel["target_id"],
                                        rel["type"],
                                        rel["metadata"]
                                    )
                    
                    # Update final status
                    await global_health_monitor.update_component_status(
                        f"parser_{self.language_id}",
                        ComponentStatus.HEALTHY,
                        details={
                            "operation": "pattern_learning_complete",
                            "patterns_found": len(patterns),
                            "relationships_found": len(relationships) if patterns else 0
                        }
                    )
                    
            except Exception as e:
                await log(f"Error in pattern learning process: {e}", level="error")
                await global_health_monitor.update_component_status(
                    f"parser_{self.language_id}",
                    ComponentStatus.UNHEALTHY,
                    error=True,
                    details={
                        "operation": "pattern_learning",
                        "error": str(e)
                    }
                )
                raise ProcessingError(f"Pattern learning failed: {e}")
        
        return patterns
    
    async def cleanup(self):
        """[5.1.10] Clean up parser resources."""
        try:
            if not self._initialized:
                return
                
            # Clean up tree-sitter parser
            if self._tree_sitter_parser:
                await self._tree_sitter_parser.cleanup()
                self._tree_sitter_parser = None
            
            # Clean up custom parser
            if self._custom_parser:
                await self._custom_parser.cleanup()
                self._custom_parser = None
            
            # Clean up cache
            if self._cache:
                await cache_coordinator.unregister_cache(self._cache)
                self._cache = None
            
            # Cancel all pending tasks
            if self._pending_tasks:
                for task in self._pending_tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                self._pending_tasks.clear()
            
            self._initialized = False
            log(f"Unified parser cleaned up for {self.language_id}", level="info")
        except Exception as e:
            log(f"Error cleaning up unified parser for {self.language_id}: {e}", level="error")
            raise ProcessingError(f"Failed to cleanup unified parser for {self.language_id}: {e}")

    async def process_with_deep_learning(
        self,
        source_code: str,
        context: AIContext,
        repositories: List[int]
    ) -> AIProcessingResult:
        """Process with deep learning capabilities."""
        results = AIProcessingResult(success=True)

        # Process with tree-sitter parser if available
        if self._tree_sitter_parser:
            tree_sitter_results = await self._tree_sitter_parser.process_deep_learning(
                source_code,
                context,
                repositories
            )
            results.ai_insights.update(tree_sitter_results.ai_insights)

        # Add custom parser insights
        if self._custom_parser:
            custom_results = await self._custom_parser.process_deep_learning(
                source_code,
                context,
                repositories
            )
            results.ai_insights.update(custom_results.ai_insights)

        return results

# Global instance cache
_parser_instances: Dict[str, UnifiedParser] = {}

async def get_unified_parser(language_id: str) -> Optional[UnifiedParser]:
    """[5.2] Get a unified parser instance for a language."""
    if language_id not in _parser_instances:
        try:
            parser = await UnifiedParser.create(language_id)
            _parser_instances[language_id] = parser
        except Exception as e:
            log(f"Error creating unified parser for {language_id}: {e}", level="error")
            return None
    
    return _parser_instances[language_id] 