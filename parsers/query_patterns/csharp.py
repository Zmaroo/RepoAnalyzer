"""C#-specific patterns with enhanced type system and relationships.

This module provides C#-specific patterns that integrate with the enhanced
pattern processing system, including proper typing, relationships, and context.
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

# C# capabilities
CSHARP_CAPABILITIES = {
    AICapability.CODE_UNDERSTANDING,
    AICapability.CODE_GENERATION,
    AICapability.CODE_MODIFICATION,
    AICapability.CODE_REVIEW,
    AICapability.LEARNING
}

# Pattern relationships for C#
CSHARP_PATTERN_RELATIONSHIPS = {
    "function": [
        PatternRelationship(
            source_pattern="function",
            target_pattern="type",
            relationship_type=PatternRelationType.USES,
            confidence=0.95,
            metadata={"return_type": True}
        ),
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
            target_pattern="function",
            relationship_type=PatternRelationType.IMPLEMENTS,
            confidence=0.95,
            metadata={"methods": True}
        ),
        PatternRelationship(
            source_pattern="class",
            target_pattern="interface",
            relationship_type=PatternRelationType.IMPLEMENTS,
            confidence=0.95,
            metadata={"interfaces": True}
        )
    ],
    "interface": [
        PatternRelationship(
            source_pattern="interface",
            target_pattern="function",
            relationship_type=PatternRelationType.DEFINES,
            confidence=0.95,
            metadata={"methods": True}
        )
    ]
}

# Performance metrics tracking for C# patterns
CSHARP_PATTERN_METRICS = {
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
    "interface": PatternPerformanceMetrics(
        execution_time=0.0,
        memory_usage=0,
        cache_hits=0,
        cache_misses=0,
        error_count=0,
        success_rate=0.0,
        pattern_stats={"matches": 0, "failures": 0}
    )
}

# Enhanced C# patterns with proper typing and relationships
CSHARP_PATTERNS = {
    **COMMON_PATTERNS,  # Inherit common patterns
    
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "function": ResilientPattern(
                name="function",
                pattern="""
                [
                    (method_declaration
                        attributes: (attribute_list)* @syntax.function.attributes
                        modifiers: (_)* @syntax.function.modifier
                        type: (_) @syntax.function.return_type
                        name: (identifier) @syntax.function.name
                        parameters: (parameter_list) @syntax.function.params
                        body: [(block) (arrow_expression_clause)]? @syntax.function.body) @syntax.function.method,
                        
                    (constructor_declaration
                        attributes: (attribute_list)* @syntax.function.constructor.attributes
                        modifiers: (_)* @syntax.function.constructor.modifier
                        name: (identifier) @syntax.function.constructor.name
                        parameter_list: (parameter_list) @syntax.function.constructor.params
                        initializer: (constructor_initializer)? @syntax.function.constructor.init
                        body: (block) @syntax.function.constructor.body) @syntax.function.constructor
                ]
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="c_sharp",
                confidence=0.95,
                metadata={
                    "relationships": CSHARP_PATTERN_RELATIONSHIPS["function"],
                    "metrics": CSHARP_PATTERN_METRICS["function"],
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    )
                }
            ),
            
            "class": ResilientPattern(
                name="class",
                pattern="""
                (class_declaration
                    attributes: (attribute_list)* @syntax.class.attributes
                    modifiers: (_)* @syntax.class.modifier
                    name: (identifier) @syntax.class.name
                    type_parameters: (type_parameter_list)? @syntax.class.type_params
                    base_list: (base_list)? @syntax.class.bases
                    body: (declaration_list) @syntax.class.body) @syntax.class.def
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="c_sharp",
                confidence=0.95,
                metadata={
                    "relationships": CSHARP_PATTERN_RELATIONSHIPS["class"],
                    "metrics": CSHARP_PATTERN_METRICS["class"],
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    )
                }
            ),
            
            "interface": ResilientPattern(
                name="interface",
                pattern="""
                (interface_declaration
                    attributes: (attribute_list)* @syntax.interface.attributes
                    modifiers: (_)* @syntax.interface.modifier
                    name: (identifier) @syntax.interface.name
                    type_parameter_list: (type_parameter_list)? @syntax.interface.type_params
                    base_list: (base_list)? @syntax.interface.extends
                    body: (declaration_list) @syntax.interface.body) @syntax.interface.def
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="c_sharp",
                confidence=0.95,
                metadata={
                    "relationships": CSHARP_PATTERN_RELATIONSHIPS["interface"],
                    "metrics": CSHARP_PATTERN_METRICS["interface"],
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
            "namespace": QueryPattern(
                pattern="""
                [
                    (namespace_declaration
                        name: (qualified_name) @structure.namespace.name
                        body: (declaration_list) @structure.namespace.body) @structure.namespace,
                        
                    (using_directive
                        static_keyword: (static_keyword)? @structure.using.static
                        name: (qualified_name) @structure.using.name
                        alias: (identifier)? @structure.using.alias) @structure.using
                ]
                """,
                extract=lambda node: {
                    "name": node["captures"].get("structure.namespace.name", {}).get("text", ""),
                    "using": node["captures"].get("structure.using.name", {}).get("text", ""),
                    "is_static_using": "structure.using.static" in node["captures"]
                },
                description="Matches C# namespace and using declarations",
                examples=[
                    "namespace MyNamespace { }",
                    "using static System.Math;"
                ],
                category=PatternCategory.STRUCTURE,
                purpose=PatternPurpose.UNDERSTANDING
            )
        }
    },
    
    PatternCategory.SEMANTICS: {
        PatternPurpose.UNDERSTANDING: {
            "linq": AdaptivePattern(
                name="linq",
                pattern="""
                (query_expression
                    clauses: [(from_clause
                               type: (_)? @semantics.linq.from.type
                               name: (identifier) @semantics.linq.from.name
                               in: (_) @semantics.linq.from.source)
                             (where_clause
                               condition: (_) @semantics.linq.where.condition)
                             (orderby_clause
                               orderings: (ordering
                                 expression: (_) @semantics.linq.orderby.expr
                                 direction: [(ascending_keyword) (descending_keyword)]? @semantics.linq.orderby.dir)*)
                             (select_clause
                               expression: (_) @semantics.linq.select.expr)
                             (group_clause
                               expression: (_) @semantics.linq.group.expr
                               by: (_) @semantics.linq.group.by)
                             (join_clause
                               name: (identifier) @semantics.linq.join.name
                               in: (_) @semantics.linq.join.source
                               on: (_) @semantics.linq.join.on
                               equals: (_) @semantics.linq.join.equals)]*) @semantics.linq.query
                """,
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="c_sharp",
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
            
            "async": AdaptivePattern(
                name="async",
                pattern="""
                [
                    (method_declaration
                        modifiers: (async_keyword) @semantics.async.modifier) @semantics.async.method,
                        
                    (await_expression
                        expression: (_) @semantics.async.await.expr) @semantics.async.await,
                        
                    (anonymous_method_expression
                        modifiers: (async_keyword) @semantics.async.lambda.modifier) @semantics.async.lambda
                ]
                """,
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="c_sharp",
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
                    (documentation_comment
                        tags: [(element
                                name: (_) @documentation.xml.tag.name
                                attributes: (attribute
                                    name: (_) @documentation.xml.attr.name
                                    value: (_) @documentation.xml.attr.value)*
                                content: (_)* @documentation.xml.content)]*) @documentation.xml,
                    (comment) @documentation.comment
                ]
                """,
                category=PatternCategory.DOCUMENTATION,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="c_sharp",
                confidence=0.9,
                metadata={
                    "relationships": [
                        PatternRelationship(
                            source_pattern="comments",
                            target_pattern="function",
                            relationship_type=PatternRelationType.COMPLEMENTS,
                            confidence=0.8
                        )
                    ],
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
    """Create pattern context for C# files."""
    return PatternContext(
        code_structure=code_structure,
        language_stats={"language": "c_sharp"},
        project_patterns=[],
        file_location=file_path,
        dependencies=set(),
        recent_changes=[],
        scope_level="global",
        allows_nesting=True,
        relevant_patterns=list(CSHARP_PATTERNS.keys())
    )

def get_csharp_pattern_relationships(pattern_name: str) -> List[PatternRelationship]:
    """Get relationships for a specific pattern."""
    return CSHARP_PATTERN_RELATIONSHIPS.get(pattern_name, [])

def update_csharp_pattern_metrics(pattern_name: str, metrics: Dict[str, Any]) -> None:
    """Update performance metrics for a pattern."""
    if pattern_name in CSHARP_PATTERN_METRICS:
        pattern_metrics = CSHARP_PATTERN_METRICS[pattern_name]
        pattern_metrics.execution_time = metrics.get("execution_time", 0.0)
        pattern_metrics.memory_usage = metrics.get("memory_usage", 0)
        pattern_metrics.cache_hits = metrics.get("cache_hits", 0)
        pattern_metrics.cache_misses = metrics.get("cache_misses", 0)
        pattern_metrics.error_count = metrics.get("error_count", 0)
        
        total = pattern_metrics.cache_hits + pattern_metrics.cache_misses
        if total > 0:
            pattern_metrics.success_rate = pattern_metrics.cache_hits / total

def get_csharp_pattern_match_result(
    pattern_name: str,
    matches: List[Dict[str, Any]],
    context: PatternContext
) -> PatternMatchResult:
    """Create a pattern match result with relationships and metrics."""
    return PatternMatchResult(
        pattern_name=pattern_name,
        matches=matches,
        context=context,
        relationships=get_csharp_pattern_relationships(pattern_name),
        performance=CSHARP_PATTERN_METRICS.get(pattern_name, PatternPerformanceMetrics()),
        validation=PatternValidationResult(is_valid=True),
        metadata={"language": "c_sharp"}
    )

class CSharpPatternLearner(CrossProjectPatternLearner):
    """Enhanced C# pattern learner with full system integration."""
    
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
        self._feature_extractor = await BaseFeatureExtractor.create("c_sharp", FileType.CODE)
        self._unified_parser = await get_unified_parser()
        self._ai_processor = await get_ai_pattern_processor()
        
        # Register with pattern processor
        await self._pattern_processor.register_language_patterns(
            "c_sharp", 
            CSHARP_PATTERNS,
            self
        )

    async def _get_parser(self) -> BaseParser:
        """Get appropriate parser for C#."""
        # Try tree-sitter first
        tree_sitter_parser = await get_tree_sitter_parser("c_sharp")
        if tree_sitter_parser:
            return tree_sitter_parser
            
        # Fallback to base parser
        return await BaseParser.create(
            language_id="c_sharp",
            file_type=FileType.CODE,
            parser_type=ParserType.CUSTOM
        )

    async def learn_from_project(self, project_path: str) -> List[Dict[str, Any]]:
        """Learn patterns with AI assistance."""
        if not self._ai_processor:
            await self.initialize()
            
        # Try AI-assisted learning first
        ai_context = AIContext(
            language_id="c_sharp",
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
        async with AsyncErrorBoundary("csharp_pattern_learning"):
            # Extract blocks using block extractor
            blocks = await self._block_extractor.extract_from_project(
                project_path,
                language_id="c_sharp"
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
csharp_pattern_learner = CSharpPatternLearner()

@handle_async_errors(error_types=ProcessingError)
async def process_csharp_pattern(
    pattern: Union[AdaptivePattern, ResilientPattern],
    source_code: str,
    context: Optional[PatternContext] = None
) -> List[Dict[str, Any]]:
    """Process a C# pattern with full system integration."""
    async with AsyncErrorBoundary(
        operation_name=f"process_pattern_{pattern.name}",
        error_types=ProcessingError,
        severity=ErrorSeverity.ERROR
    ):
        # Get all required components
        block_extractor = await get_block_extractor()
        feature_extractor = await BaseFeatureExtractor.create("c_sharp", FileType.CODE)
        unified_parser = await get_unified_parser()
        
        # Parse if needed
        if not context or not context.code_structure:
            parse_result = await unified_parser.parse(source_code, "c_sharp", FileType.CODE)
            if parse_result and parse_result.ast:
                context = await create_pattern_context(
                    "",
                    parse_result.ast
                )
        
        # Extract and process blocks
        blocks = await block_extractor.get_child_blocks(
            "c_sharp",
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
        await update_csharp_pattern_metrics(
            pattern.name,
            {
                "execution_time": time.time() - start_time,
                "matches": len(matches)
            }
        )
        
        return matches

# Update initialization
async def initialize_csharp_patterns():
    """Initialize C# patterns during app startup."""
    global csharp_pattern_learner
    
    # Initialize pattern processor first
    await pattern_processor.initialize()
    
    # Register C# patterns
    await pattern_processor.register_language_patterns(
        "c_sharp",
        CSHARP_PATTERNS,
        metadata={
            "parser_type": ParserType.TREE_SITTER,
            "supports_learning": True,
            "supports_adaptation": True,
            "capabilities": CSHARP_CAPABILITIES
        }
    )
    
    # Create and initialize learner
    csharp_pattern_learner = await CSharpPatternLearner.create()
    
    # Register learner with pattern processor
    await pattern_processor.register_pattern_learner(
        "c_sharp",
        csharp_pattern_learner
    )
    
    await global_health_monitor.update_component_status(
        "csharp_patterns",
        ComponentStatus.HEALTHY,
        details={
            "patterns_loaded": len(CSHARP_PATTERNS),
            "capabilities": list(CSHARP_CAPABILITIES)
        }
    )

async def extract_csharp_features(
    pattern: Union[AdaptivePattern, ResilientPattern],
    matches: List[Dict[str, Any]],
    context: PatternContext
) -> ExtractedFeatures:
    """Extract features from pattern matches."""
    feature_extractor = await BaseFeatureExtractor.create("c_sharp", FileType.CODE)
    
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

async def validate_csharp_pattern(
    pattern: Union[AdaptivePattern, ResilientPattern],
    context: Optional[PatternContext] = None
) -> PatternValidationResult:
    """Validate a C# pattern with system integration."""
    async with AsyncErrorBoundary("csharp_pattern_validation"):
        # Get pattern processor
        validation_result = await pattern_processor.validate_pattern(
            pattern,
            language_id="c_sharp",
            context=context
        )
        
        # Update pattern metrics
        if not validation_result.is_valid:
            pattern_metrics = CSHARP_PATTERN_METRICS.get(pattern.name)
            if pattern_metrics:
                pattern_metrics.error_count += 1
        
        return validation_result

# Export public interfaces
__all__ = [
    'CSHARP_PATTERNS',
    'CSHARP_PATTERN_RELATIONSHIPS',
    'CSHARP_PATTERN_METRICS',
    'create_pattern_context',
    'get_csharp_pattern_relationships',
    'update_csharp_pattern_metrics',
    'get_csharp_pattern_match_result',
    'csharp_pattern_learner',
    'process_csharp_pattern',
    'initialize_csharp_patterns',
    'extract_csharp_features',
    'validate_csharp_pattern'
]

# Module identification
LANGUAGE = "c_sharp" 