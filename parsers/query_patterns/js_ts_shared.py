"""Shared patterns between JavaScript and TypeScript with enhanced type system and relationships.

This module provides patterns that are common between JavaScript and TypeScript,
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
from .common import COMMON_PATTERNS
from .enhanced_patterns import AdaptivePattern, ResilientPattern, CrossProjectPatternLearner
from utils.error_handling import AsyncErrorBoundary, handle_async_errors, ProcessingError, ErrorSeverity
from utils.health_monitor import monitor_operation, global_health_monitor, ComponentStatus
from utils.request_cache import cached_in_request
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

# JS/TS shared capabilities
JS_TS_CAPABILITIES = {
    AICapability.CODE_UNDERSTANDING,
    AICapability.CODE_GENERATION,
    AICapability.CODE_MODIFICATION,
    AICapability.CODE_REVIEW,
    AICapability.LEARNING
}

# Pattern relationships for shared JS/TS patterns
JS_TS_PATTERN_RELATIONSHIPS = {
    "function_definition": [
        PatternRelationship(
            source_pattern="function_definition",
            target_pattern="comments",
            relationship_type=PatternRelationType.COMPLEMENTS,
            confidence=0.9,
            metadata={"documentation": True}
        )
    ],
    "class_definition": [
        PatternRelationship(
            source_pattern="class_definition",
            target_pattern="method_definition",
            relationship_type=PatternRelationType.CONTAINS,
            confidence=0.95,
            metadata={"class_members": True}
        ),
        PatternRelationship(
            source_pattern="class_definition",
            target_pattern="comments",
            relationship_type=PatternRelationType.COMPLEMENTS,
            confidence=0.9,
            metadata={"documentation": True}
        )
    ],
    "module_exports": [
        PatternRelationship(
            source_pattern="module_exports",
            target_pattern="function_definition",
            relationship_type=PatternRelationType.EXPORTS,
            confidence=0.95,
            metadata={"module_system": True}
        ),
        PatternRelationship(
            source_pattern="module_exports",
            target_pattern="class_definition",
            relationship_type=PatternRelationType.EXPORTS,
            confidence=0.95,
            metadata={"module_system": True}
        )
    ]
}

# Performance metrics tracking for shared JS/TS patterns
JS_TS_PATTERN_METRICS = {
    "function_definition": PatternPerformanceMetrics(
        execution_time=0.0,
        memory_usage=0,
        cache_hits=0,
        cache_misses=0,
        error_count=0,
        success_rate=0.0,
        pattern_stats={"matches": 0, "failures": 0}
    ),
    "class_definition": PatternPerformanceMetrics(
        execution_time=0.0,
        memory_usage=0,
        cache_hits=0,
        cache_misses=0,
        error_count=0,
        success_rate=0.0,
        pattern_stats={"matches": 0, "failures": 0}
    ),
    "module_exports": PatternPerformanceMetrics(
        execution_time=0.0,
        memory_usage=0,
        cache_hits=0,
        cache_misses=0,
        error_count=0,
        success_rate=0.0,
        pattern_stats={"matches": 0, "failures": 0}
    )
}

# Enhanced shared patterns with proper typing and relationships
JS_TS_SHARED_PATTERNS = {
    **COMMON_PATTERNS,  # Inherit common patterns
    
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "function_definition": ResilientPattern(
                name="function_definition",
                pattern="""
                [
                    (function_declaration
                        name: (identifier) @syntax.function.name
                        parameters: (formal_parameters) @syntax.function.params
                        body: (statement_block) @syntax.function.body) @syntax.function.def,
                    
                    (arrow_function
                        parameters: (formal_parameters) @syntax.arrow.params
                        body: [(statement_block) (expression)] @syntax.arrow.body) @syntax.arrow.def
                ]
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="js_ts",
                confidence=0.95,
                metadata={
                    "relationships": JS_TS_PATTERN_RELATIONSHIPS["function_definition"],
                    "metrics": JS_TS_PATTERN_METRICS["function_definition"],
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    )
                }
            ),
            
            "class_definition": ResilientPattern(
                name="class_definition",
                pattern="""
                [
                    (class_declaration
                        name: (identifier) @syntax.class.name
                        extends: (class_heritage)? @syntax.class.extends
                        body: (class_body) @syntax.class.body) @syntax.class.def,
                    
                    (method_definition
                        name: (property_identifier) @syntax.method.name
                        parameters: (formal_parameters) @syntax.method.params
                        body: (statement_block) @syntax.method.body) @syntax.method.def
                ]
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="js_ts",
                confidence=0.95,
                metadata={
                    "relationships": JS_TS_PATTERN_RELATIONSHIPS["class_definition"],
                    "metrics": JS_TS_PATTERN_METRICS["class_definition"],
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
            "module_exports": AdaptivePattern(
                name="module_exports",
                pattern="""
                [
                    (assignment_expression
                        left: (member_expression
                            object: (identifier) @semantics.module.object
                            property: (property_identifier) @semantics.module.property)
                        right: (_) @semantics.module.value) @semantics.module.exports,
                    
                    (export_statement
                        declaration: (_) @semantics.export.value) @semantics.export.statement
                ]
                """,
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="js_ts",
                confidence=0.9,
                metadata={
                    "relationships": JS_TS_PATTERN_RELATIONSHIPS["module_exports"],
                    "metrics": JS_TS_PATTERN_METRICS["module_exports"],
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    )
                }
            ),
            
            "variable_declaration": AdaptivePattern(
                name="variable_declaration",
                pattern="""
                [
                    (variable_declaration
                        kind: [(const) (let) (var)] @semantics.var.kind
                        declarator: (variable_declarator
                            name: (identifier) @semantics.var.name
                            value: (_)? @semantics.var.value)) @semantics.var.def
                ]
                """,
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="js_ts",
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
            "comments": AdaptivePattern(
                name="comments",
                pattern="""
                [
                    (comment) @documentation.comment
                ]
                """,
                category=PatternCategory.DOCUMENTATION,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="js_ts",
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

def create_pattern_context(file_path: str, code_structure: Dict[str, Any]) -> PatternContext:
    """Create pattern context for JS/TS files."""
    return PatternContext(
        code_structure=code_structure,
        language_stats={"language": "js_ts", "version": "es2022"},
        project_patterns=[],
        file_location=file_path,
        dependencies=set(),
        recent_changes=[],
        scope_level="global",
        allows_nesting=True,
        relevant_patterns=list(JS_TS_SHARED_PATTERNS.keys())
    )

def get_js_ts_pattern_relationships(pattern_name: str) -> List[PatternRelationship]:
    """Get relationships for a specific pattern."""
    return JS_TS_PATTERN_RELATIONSHIPS.get(pattern_name, [])

def update_js_ts_pattern_metrics(pattern_name: str, metrics: Dict[str, Any]) -> None:
    """Update performance metrics for a pattern."""
    if pattern_name in JS_TS_PATTERN_METRICS:
        pattern_metrics = JS_TS_PATTERN_METRICS[pattern_name]
        pattern_metrics.execution_time = metrics.get("execution_time", 0.0)
        pattern_metrics.memory_usage = metrics.get("memory_usage", 0)
        pattern_metrics.cache_hits = metrics.get("cache_hits", 0)
        pattern_metrics.cache_misses = metrics.get("cache_misses", 0)
        pattern_metrics.error_count = metrics.get("error_count", 0)
        
        total = pattern_metrics.cache_hits + pattern_metrics.cache_misses
        if total > 0:
            pattern_metrics.success_rate = pattern_metrics.cache_hits / total

def get_js_ts_pattern_match_result(
    pattern_name: str,
    matches: List[Dict[str, Any]],
    context: PatternContext
) -> PatternMatchResult:
    """Create a pattern match result with relationships and metrics."""
    return PatternMatchResult(
        pattern_name=pattern_name,
        matches=matches,
        context=context,
        relationships=get_js_ts_pattern_relationships(pattern_name),
        performance=JS_TS_PATTERN_METRICS.get(pattern_name, PatternPerformanceMetrics()),
        validation=PatternValidationResult(is_valid=True),
        metadata={"language": "js_ts"}
    )

# Export public interfaces
__all__ = [
    'JS_TS_SHARED_PATTERNS',
    'JS_TS_PATTERN_RELATIONSHIPS',
    'JS_TS_PATTERN_METRICS',
    'create_pattern_context',
    'get_js_ts_pattern_relationships',
    'update_js_ts_pattern_metrics',
    'get_js_ts_pattern_match_result'
]

# Module identification
LANGUAGE = "js_ts"

class JSTSPatternLearner(CrossProjectPatternLearner):
    """Enhanced JS/TS pattern learner with full system integration."""
    
    def __init__(self):
        super().__init__()
        self._block_extractor = None
        self._feature_extractor = None
        self._unified_parser = None
        self._pattern_processor = pattern_processor
        self._ai_processor = None
        register_shutdown_handler(self.cleanup)

    async def initialize(self):
        """Initialize with all required components."""
        await super().initialize()
        
        # Initialize required components
        self._block_extractor = await get_block_extractor()
        self._feature_extractor = await BaseFeatureExtractor.create("js_ts", FileType.CODE)
        self._unified_parser = await get_unified_parser()
        self._ai_processor = await get_ai_pattern_processor()
        
        # Register with pattern processor
        await self._pattern_processor.register_language_patterns(
            "js_ts", 
            JS_TS_SHARED_PATTERNS,
            self
        )

    async def _get_parser(self) -> BaseParser:
        """Get appropriate parser for JS/TS."""
        # Try tree-sitter first
        tree_sitter_parser = await get_tree_sitter_parser("javascript")  # Use JS parser as base
        if tree_sitter_parser:
            return tree_sitter_parser
            
        # Fallback to base parser
        return await BaseParser.create(
            language_id="js_ts",
            file_type=FileType.CODE,
            parser_type=ParserType.CUSTOM
        )

    async def learn_from_project(self, project_path: str) -> List[Dict[str, Any]]:
        """Learn patterns with AI assistance."""
        if not self._ai_processor:
            await self.initialize()
            
        # Try AI-assisted learning first
        ai_context = AIContext(
            language_id="js_ts",
            file_type=FileType.CODE,
            interaction_type=InteractionType.LEARNING,
            repository_id=None,
            file_path=project_path
        )
        
        ai_result = await self._ai_processor.process_with_ai(
            source_code="",  # Will be filled by processor
            context=ai_context
        )
        
        if ai_result.success:
            return ai_result.learned_patterns
            
        # Fallback to standard learning
        async with AsyncErrorBoundary("js_ts_pattern_learning"):
            # Extract blocks using block extractor
            blocks = await self._block_extractor.extract_from_project(
                project_path,
                language_id="js_ts"
            )

            # Extract features from blocks
            features = []
            for block in blocks:
                block_features = await self._feature_extractor.extract_features(
                    block.content,
                    block.metadata
                )
                features.append(block_features)

            # Learn patterns from features
            patterns = await self._learn_patterns_from_features(features)
            
            return patterns

    async def _learn_patterns_from_features(
        self,
        features: List[ExtractedFeatures]
    ) -> List[Dict[str, Any]]:
        """Learn patterns from extracted features."""
        patterns = []
        
        # Group features by category
        for category in PatternCategory:
            category_features = [
                f for f in features 
                if f.category == category
            ]
            
            if category_features:
                # Learn patterns for this category
                learned = await self._learn_category_patterns(
                    category,
                    category_features
                )
                patterns.extend(learned)
        
        return patterns

    async def cleanup(self):
        """Clean up pattern learner resources."""
        if self._block_extractor:
            await self._block_extractor.cleanup()
        if self._feature_extractor:
            await self._feature_extractor.cleanup()
        if self._unified_parser:
            await self._unified_parser.cleanup()
        if self._ai_processor:
            await self._ai_processor.cleanup()

# Initialize pattern learner
js_ts_pattern_learner = JSTSPatternLearner()

@handle_async_errors(error_types=ProcessingError)
async def process_js_ts_pattern(
    pattern: Union[AdaptivePattern, ResilientPattern],
    source_code: str,
    context: Optional[PatternContext] = None
) -> List[Dict[str, Any]]:
    """Process a JS/TS pattern with full system integration."""
    async with AsyncErrorBoundary(
        operation_name=f"process_pattern_{pattern.name}",
        error_types=ProcessingError,
        severity=ErrorSeverity.ERROR
    ):
        # Get all required components
        block_extractor = await get_block_extractor()
        feature_extractor = await BaseFeatureExtractor.create("js_ts", FileType.CODE)
        unified_parser = await get_unified_parser()
        
        # Parse if needed
        if not context or not context.code_structure:
            parse_result = await unified_parser.parse(source_code, "js_ts", FileType.CODE)
            if parse_result and parse_result.ast:
                context = await create_pattern_context(
                    "",
                    parse_result.ast
                )
        
        # Extract and process blocks
        blocks = await block_extractor.get_child_blocks(
            "js_ts",
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
        
        # Update pattern metrics
        await update_js_ts_pattern_metrics(
            pattern.name,
            {
                "execution_time": time.time() - start_time,
                "matches": len(matches)
            }
        )
        
        return matches

# Update initialization
async def initialize_js_ts_patterns():
    """Initialize JS/TS patterns during app startup."""
    global js_ts_pattern_learner
    
    # Initialize pattern processor first
    await pattern_processor.initialize()
    
    # Register JS/TS patterns
    await pattern_processor.register_language_patterns(
        "js_ts",
        JS_TS_SHARED_PATTERNS,
        metadata={
            "parser_type": ParserType.TREE_SITTER,
            "supports_learning": True,
            "supports_adaptation": True,
            "capabilities": JS_TS_CAPABILITIES
        }
    )
    
    # Create and initialize learner
    js_ts_pattern_learner = await JSTSPatternLearner.create()
    
    # Register learner with pattern processor
    await pattern_processor.register_pattern_learner(
        "js_ts",
        js_ts_pattern_learner
    )
    
    await global_health_monitor.update_component_status(
        "js_ts_patterns",
        ComponentStatus.HEALTHY,
        details={
            "patterns_loaded": len(JS_TS_SHARED_PATTERNS),
            "capabilities": list(JS_TS_CAPABILITIES)
        }
    )

async def extract_js_ts_features(
    pattern: Union[AdaptivePattern, ResilientPattern],
    matches: List[Dict[str, Any]],
    context: PatternContext
) -> ExtractedFeatures:
    """Extract features from pattern matches."""
    feature_extractor = await BaseFeatureExtractor.create("js_ts", FileType.CODE)
    
    features = ExtractedFeatures()
    
    for match in matches:
        # Extract features based on pattern category
        if pattern.category == PatternCategory.SYNTAX:
            syntax_features = await feature_extractor._extract_syntax_features(
                match,
                context
            )
            features.update(syntax_features)
            
        elif pattern.category == PatternCategory.SEMANTICS:
            semantic_features = await feature_extractor._extract_semantic_features(
                match,
                context
            )
            features.update(semantic_features)
    
    return features

async def validate_js_ts_pattern(
    pattern: Union[AdaptivePattern, ResilientPattern],
    context: Optional[PatternContext] = None
) -> PatternValidationResult:
    """Validate a JS/TS pattern with system integration."""
    async with AsyncErrorBoundary("js_ts_pattern_validation"):
        # Get pattern processor
        validation_result = await pattern_processor.validate_pattern(
            pattern,
            language_id="js_ts",
            context=context
        )
        
        # Update pattern metrics
        if not validation_result.is_valid:
            pattern_metrics = JS_TS_PATTERN_METRICS.get(pattern.name)
            if pattern_metrics:
                pattern_metrics.error_count += 1
        
        return validation_result
