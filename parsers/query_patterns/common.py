"""Common Tree-sitter patterns shared between languages.

This module provides common patterns that can be shared across languages,
integrating with the enhanced pattern processing system, including proper typing,
relationships, and context.
"""

from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field
from parsers.types import (
    PatternCategory, PatternPurpose, PatternType, PatternRelationType,
    PatternContext, PatternRelationship, PatternPerformanceMetrics,
    PatternValidationResult, PatternMatchResult, QueryPattern,
    AICapability, AIContext, AIProcessingResult, InteractionType,
    ExtractedFeatures, FileType, ParserType
)
from parsers.models import PATTERN_CATEGORIES
from .enhanced_patterns import AdaptivePattern, ResilientPattern, CrossProjectPatternLearner
from utils.error_handling import AsyncErrorBoundary, handle_async_errors, ProcessingError, ErrorSeverity
from utils.health_monitor import monitor_operation, global_health_monitor, ComponentStatus
from utils.request_cache import cached_in_request, get_current_request_cache
from utils.cache_analytics import get_cache_analytics
from utils.async_runner import submit_async_task, cleanup_tasks
from utils.logger import log
from utils.shutdown import register_shutdown_handler
import asyncio
from parsers.pattern_processor import pattern_processor
from parsers.block_extractor import get_block_extractor
from parsers.feature_extractor import BaseFeatureExtractor
from parsers.unified_parser import get_unified_parser
from parsers.base_parser import BaseParser
from parsers.tree_sitter_parser import get_tree_sitter_parser
from parsers.ai_pattern_processor import get_ai_pattern_processor
import time

# Common capabilities shared across languages
COMMON_CAPABILITIES = {
    AICapability.CODE_UNDERSTANDING,
    AICapability.CODE_GENERATION,
    AICapability.CODE_MODIFICATION,
    AICapability.CODE_REVIEW,
    AICapability.LEARNING
}

# Common pattern relationships
COMMON_PATTERN_RELATIONSHIPS = {
    "function": [
        PatternRelationship(
            source_pattern="function",
            target_pattern="comment",
            relationship_type=PatternRelationType.COMPLEMENTS,
            confidence=0.8,
            metadata={"documentation": True}
        )
    ],
    "class": [
        PatternRelationship(
            source_pattern="class",
            target_pattern="method",
            relationship_type=PatternRelationType.CONTAINS,
            confidence=0.95,
            metadata={"class_members": True}
        ),
        PatternRelationship(
            source_pattern="class",
            target_pattern="comment",
            relationship_type=PatternRelationType.COMPLEMENTS,
            confidence=0.8,
            metadata={"documentation": True}
        )
    ],
    "module": [
        PatternRelationship(
            source_pattern="module",
            target_pattern="import",
            relationship_type=PatternRelationType.CONTAINS,
            confidence=0.95,
            metadata={"module_system": True}
        ),
        PatternRelationship(
            source_pattern="module",
            target_pattern="export",
            relationship_type=PatternRelationType.CONTAINS,
            confidence=0.95,
            metadata={"module_system": True}
        )
    ]
}

# Performance metrics for common patterns
COMMON_PATTERN_METRICS = {
    "function": PatternPerformanceMetrics(
        execution_time=0.0,
        memory_usage=0,
        cache_hits=0,
        cache_misses=0,
        error_count=0,
        success_rate=0.0,
        pattern_stats={"matches": 0, "failures": 0}
    ),
    "class": PatternPerformanceMetrics(
        execution_time=0.0,
        memory_usage=0,
        cache_hits=0,
        cache_misses=0,
        error_count=0,
        success_rate=0.0,
        pattern_stats={"matches": 0, "failures": 0}
    ),
    "module": PatternPerformanceMetrics(
        execution_time=0.0,
        memory_usage=0,
        cache_hits=0,
        cache_misses=0,
        error_count=0,
        success_rate=0.0,
        pattern_stats={"matches": 0, "failures": 0}
    )
}

# Enhanced common patterns with proper typing and relationships
COMMON_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "function": ResilientPattern(
                name="function",
                pattern="""
                [
                    (function_definition) @syntax.function,
                    (method_definition) @syntax.method
                ]
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="*",  # Wildcard for all languages
                confidence=0.95,
                metadata={
                    "relationships": COMMON_PATTERN_RELATIONSHIPS["function"],
                    "metrics": COMMON_PATTERN_METRICS["function"],
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    )
                }
            ),
            
            "class": ResilientPattern(
                name="class",
                pattern="""
                [
                    (class_definition) @syntax.class,
                    (class_declaration) @syntax.class
                ]
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="*",
                confidence=0.95,
                metadata={
                    "relationships": COMMON_PATTERN_RELATIONSHIPS["class"],
                    "metrics": COMMON_PATTERN_METRICS["class"],
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    )
                }
            ),
            
            "module": ResilientPattern(
                name="module",
                pattern="""
                [
                    (module) @syntax.module,
                    (program) @syntax.module
                ]
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="*",
                confidence=0.95,
                metadata={
                    "relationships": COMMON_PATTERN_RELATIONSHIPS["module"],
                    "metrics": COMMON_PATTERN_METRICS["module"],
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    )
                }
            )
        }
    },

    PatternCategory.SEMANTICS: {
        PatternPurpose.UNDERSTANDING: {
            "variable": AdaptivePattern(
                name="variable",
                pattern="""
                [
                    (identifier) @semantics.variable.ref,
                    (variable_declaration) @semantics.variable.def
                ]
                """,
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="*",
                confidence=0.9,
                metadata={
                    "relationships": [],
                    "metrics": PatternPerformanceMetrics(),
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    )
                }
            ),
            
            "literal": AdaptivePattern(
                name="literal",
                pattern="""
                [
                    (string_literal) @semantics.literal.string,
                    (number_literal) @semantics.literal.number,
                    (boolean_literal) @semantics.literal.boolean,
                    (null_literal) @semantics.literal.null
                ]
                """,
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="*",
                confidence=0.9,
                metadata={
                    "relationships": [],
                    "metrics": PatternPerformanceMetrics(),
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    )
                }
            ),
            
            "expression": AdaptivePattern(
                name="expression",
                pattern="""
                [
                    (binary_expression) @semantics.expression.binary,
                    (unary_expression) @semantics.expression.unary
                ]
                """,
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="*",
                confidence=0.9,
                metadata={
                    "relationships": [],
                    "metrics": PatternPerformanceMetrics(),
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    )
                }
            )
        }
    },

    PatternCategory.DOCUMENTATION: {
        PatternPurpose.UNDERSTANDING: {
            "documentation": AdaptivePattern(
                name="documentation",
                pattern="""
                [
                    (comment) @documentation.comment,
                    (block_comment) @documentation.block,
                    (line_comment) @documentation.line,
                    (documentation_comment) @documentation.doc
                ]
                """,
                category=PatternCategory.DOCUMENTATION,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="*",
                confidence=0.9,
                metadata={
                    "relationships": [],
                    "metrics": PatternPerformanceMetrics(),
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    )
                }
            )
        }
    },

    PatternCategory.STRUCTURE: {
        PatternPurpose.UNDERSTANDING: {
            "import": AdaptivePattern(
                name="import",
                pattern="""
                [
                    (import_statement) @structure.import,
                    (import_declaration) @structure.import
                ]
                """,
                category=PatternCategory.STRUCTURE,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="*",
                confidence=0.9,
                metadata={
                    "relationships": [],
                    "metrics": PatternPerformanceMetrics(),
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    )
                }
            ),
            
            "export": AdaptivePattern(
                name="export",
                pattern="""
                [
                    (export_statement) @structure.export,
                    (export_declaration) @structure.export
                ]
                """,
                category=PatternCategory.STRUCTURE,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="*",
                confidence=0.9,
                metadata={
                    "relationships": [],
                    "metrics": PatternPerformanceMetrics(),
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    )
                }
            ),
            
            "namespace": AdaptivePattern(
                name="namespace",
                pattern="""
                [
                    (namespace_definition) @structure.namespace,
                    (package_declaration) @structure.namespace
                ]
                """,
                category=PatternCategory.STRUCTURE,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="*",
                confidence=0.9,
                metadata={
                    "relationships": [],
                    "metrics": PatternPerformanceMetrics(),
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    )
                }
            )
        }
    }
}

class CommonPatternLearner(CrossProjectPatternLearner):
    """Common pattern learner that can be used across languages."""
    
    def __init__(self):
        super().__init__()
        self._block_extractor = None
        self._feature_extractor = None
        self._unified_parser = None
        self._pattern_processor = pattern_processor
        self._ai_processor = None
        self._metrics = {
            "total_patterns": 0,
            "learned_patterns": 0,
            "failed_patterns": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "learning_times": []
        }
        register_shutdown_handler(self.cleanup)

    async def initialize(self):
        """Initialize with all required components."""
        await super().initialize()
        
        # Initialize required components
        self._block_extractor = await get_block_extractor()
        self._feature_extractor = await BaseFeatureExtractor.create("*", FileType.CODE)
        self._unified_parser = await get_unified_parser()
        self._ai_processor = await get_ai_pattern_processor()
        
        # Register with pattern processor
        await self._pattern_processor.register_language_patterns(
            "*", 
            COMMON_PATTERNS,
            self
        )
        
        # Initialize health monitoring
        await global_health_monitor.update_component_status(
            "common_pattern_learner",
            ComponentStatus.HEALTHY,
            details={
                "patterns_loaded": len(COMMON_PATTERNS),
                "capabilities": list(COMMON_CAPABILITIES)
            }
        )

    async def _get_parser(self) -> BaseParser:
        """Get appropriate parser for common patterns."""
        # Use unified parser for common patterns
        return await get_unified_parser()

    async def learn_from_project(self, project_path: str) -> List[Dict[str, Any]]:
        """Learn common patterns with AI assistance."""
        start_time = time.time()
        self._metrics["total_patterns"] += 1
        
        try:
            # Try AI-assisted learning first
            ai_context = AIContext(
                language_id="*",
                file_type=FileType.CODE,
                interaction_type=InteractionType.LEARNING,
                repository_id=None,
                file_path=project_path
            )
            
            ai_result = await self._ai_processor.process_with_ai(
                source_code="",  # Will be filled by processor
                context=ai_context
            )
            
            learned_patterns = []
            if ai_result.success:
                learned_patterns.extend(ai_result.learned_patterns)
                self._metrics["learned_patterns"] += len(ai_result.learned_patterns)
            
            # Then do cross-project learning through base class
            project_patterns = await self._extract_project_patterns(project_path)
            await self._integrate_patterns(project_patterns, project_path)
            learned_patterns.extend(project_patterns)
            
            # Finally add common patterns
            async with AsyncErrorBoundary("common_pattern_learning"):
                # Extract blocks with caching
                blocks = await self._block_extractor.get_child_blocks(
                    "*",
                    "",  # Will be filled from files
                    None
                )
                
                # Extract features with metrics
                features = []
                for block in blocks:
                    block_features = await self._feature_extractor.extract_features(
                        block.content,
                        block.metadata
                    )
                    features.append(block_features)
                
                # Learn patterns from features
                common_patterns = await self._learn_patterns_from_features(features)
                learned_patterns.extend(common_patterns)
            
            # Update metrics
            learning_time = time.time() - start_time
            self._metrics["learning_times"].append(learning_time)
            
            # Update health status
            await global_health_monitor.update_component_status(
                "common_pattern_learner",
                ComponentStatus.HEALTHY,
                details={
                    "learned_patterns": len(learned_patterns),
                    "learning_time": learning_time
                }
            )
            
            return learned_patterns
            
        except Exception as e:
            self._metrics["failed_patterns"] += 1
            await log(f"Error learning patterns: {e}", level="error")
            
            # Update health status
            await global_health_monitor.update_component_status(
                "common_pattern_learner",
                ComponentStatus.DEGRADED,
                error=True,
                details={"error": str(e)}
            )
            
            return []

    async def cleanup(self):
        """Clean up pattern learner resources."""
        try:
            # Clean up base class resources
            await super().cleanup()
            
            # Clean up specific components
            if self._block_extractor:
                await self._block_extractor.cleanup()
            if self._feature_extractor:
                await self._feature_extractor.cleanup()
            if self._unified_parser:
                await self._unified_parser.cleanup()
            if self._ai_processor:
                await self._ai_processor.cleanup()
            
            # Update final status
            await global_health_monitor.update_component_status(
                "common_pattern_learner",
                ComponentStatus.SHUTDOWN,
                details={
                    "cleanup": "successful",
                    "final_metrics": self._metrics
                }
            )
            
        except Exception as e:
            await log(f"Error in cleanup: {e}", level="error")
            await global_health_monitor.update_component_status(
                "common_pattern_learner",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"cleanup_error": str(e)}
            )

# Initialize pattern learner
common_pattern_learner = CommonPatternLearner()

@handle_async_errors(error_types=ProcessingError)
async def process_common_pattern(
    pattern: Union[AdaptivePattern, ResilientPattern],
    source_code: str,
    context: Optional[PatternContext] = None
) -> List[Dict[str, Any]]:
    """Process a common pattern with full system integration."""
    async with AsyncErrorBoundary(
        operation_name=f"process_pattern_{pattern.name}",
        error_types=ProcessingError,
        severity=ErrorSeverity.ERROR
    ):
        # Get all required components
        block_extractor = await get_block_extractor()
        feature_extractor = await BaseFeatureExtractor.create("*", FileType.CODE)
        unified_parser = await get_unified_parser()
        
        # Parse if needed
        if not context or not context.code_structure:
            parse_result = await unified_parser.parse(source_code, "*", FileType.CODE)
            if parse_result and parse_result.ast:
                context = await create_pattern_context(
                    "",
                    parse_result.ast
                )
        
        # Extract and process blocks with caching
        cache_key = f"common_pattern_{pattern.name}_{hash(source_code)}"
        cached_result = await get_current_request_cache().get(cache_key)
        if cached_result:
            return cached_result
        
        blocks = await block_extractor.get_child_blocks(
            "*",
            source_code,
            context.code_structure if context else None
        )
        
        # Process blocks and extract features
        matches = []
        start_time = time.time()
        
        for block in blocks:
            block_matches = await pattern.matches(block.content)
            if block_matches:
                # Extract features for each match
                for match in block_matches:
                    features = await feature_extractor.extract_features(
                        block.content,
                        match
                    )
                    match["features"] = features
                    match["block"] = block.__dict__
                matches.extend(block_matches)
        
        # Cache the result
        await get_current_request_cache().set(cache_key, matches)
        
        # Update pattern metrics
        await update_common_pattern_metrics(
            pattern.name,
            {
                "execution_time": time.time() - start_time,
                "matches": len(matches)
            }
        )
        
        # Update health status
        await global_health_monitor.update_component_status(
            "common_pattern_processor",
            ComponentStatus.HEALTHY,
            details={
                "pattern": pattern.name,
                "matches": len(matches),
                "processing_time": time.time() - start_time
            }
        )
        
        return matches

async def update_common_pattern_metrics(pattern_name: str, metrics: Dict[str, Any]) -> None:
    """Update performance metrics for a common pattern."""
    if pattern_name in COMMON_PATTERN_METRICS:
        pattern_metrics = COMMON_PATTERN_METRICS[pattern_name]
        pattern_metrics.execution_time = metrics.get("execution_time", 0.0)
        pattern_metrics.memory_usage = metrics.get("memory_usage", 0)
        pattern_metrics.cache_hits = metrics.get("cache_hits", 0)
        pattern_metrics.cache_misses = metrics.get("cache_misses", 0)
        pattern_metrics.error_count = metrics.get("error_count", 0)
        
        total = pattern_metrics.cache_hits + pattern_metrics.cache_misses
        if total > 0:
            pattern_metrics.success_rate = pattern_metrics.cache_hits / total

async def validate_common_pattern(
    pattern: Union[AdaptivePattern, ResilientPattern],
    context: Optional[PatternContext] = None
) -> PatternValidationResult:
    """Validate a common pattern with system integration."""
    async with AsyncErrorBoundary("common_pattern_validation"):
        # Get pattern processor
        validation_result = await pattern_processor.validate_pattern(
            pattern,
            language_id="*",
            context=context
        )
        
        # Update pattern metrics
        if not validation_result.is_valid:
            pattern_metrics = COMMON_PATTERN_METRICS.get(pattern.name)
            if pattern_metrics:
                pattern_metrics.error_count += 1
        
        return validation_result

async def create_pattern_context(
    file_path: str,
    code_structure: Dict[str, Any],
    learned_patterns: Optional[Dict[str, Any]] = None
) -> PatternContext:
    """Create pattern context with full system integration."""
    # Get unified parser
    unified_parser = await get_unified_parser()
    
    # Parse the code structure if needed
    if not code_structure:
        parse_result = await unified_parser.parse(
            file_path,
            language_id="*",  # Common patterns work across languages
            file_type=FileType.CODE
        )
        code_structure = parse_result.ast if parse_result else {}
    
    context = PatternContext(
        code_structure=code_structure,
        language_stats={"language": "*"},  # Common patterns are language-agnostic
        project_patterns=list(learned_patterns.values()) if learned_patterns else [],
        file_location=file_path,
        dependencies=set(),
        recent_changes=[],
        scope_level="global",
        allows_nesting=True,
        relevant_patterns=list(COMMON_PATTERNS.keys())
    )
    
    # Add system integration metadata
    context.metadata.update({
        "parser_type": ParserType.TREE_SITTER,
        "feature_extraction_enabled": True,
        "block_extraction_enabled": True,
        "pattern_learning_enabled": True
    })
    
    return context

# Export public interfaces
__all__ = [
    'COMMON_PATTERNS',
    'COMMON_PATTERN_RELATIONSHIPS',
    'COMMON_PATTERN_METRICS',
    'COMMON_CAPABILITIES',
    'CommonPatternLearner',
    'common_pattern_learner',
    'process_common_pattern',
    'update_common_pattern_metrics',
    'validate_common_pattern',
    'create_pattern_context'
]

# Module identification
LANGUAGE = "*" 