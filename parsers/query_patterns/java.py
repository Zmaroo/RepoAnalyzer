"""Java-specific patterns with enhanced type system and relationships.

This module provides Java-specific patterns that integrate with the enhanced
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

# Java capabilities
JAVA_CAPABILITIES = {
    AICapability.CODE_UNDERSTANDING,
    AICapability.CODE_GENERATION,
    AICapability.CODE_MODIFICATION,
    AICapability.CODE_REVIEW,
    AICapability.LEARNING
}

# Pattern relationships for Java
JAVA_PATTERN_RELATIONSHIPS = {
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
            target_pattern="field_declaration",
            relationship_type=PatternRelationType.CONTAINS,
            confidence=0.95,
            metadata={"class_members": True}
        ),
        PatternRelationship(
            source_pattern="class_definition",
            target_pattern="javadoc",
            relationship_type=PatternRelationType.COMPLEMENTS,
            confidence=0.9,
            metadata={"documentation": True}
        )
    ],
    "method_definition": [
        PatternRelationship(
            source_pattern="method_definition",
            target_pattern="javadoc",
            relationship_type=PatternRelationType.COMPLEMENTS,
            confidence=0.9,
            metadata={"documentation": True}
        )
    ],
    "interface_definition": [
        PatternRelationship(
            source_pattern="interface_definition",
            target_pattern="method_declaration",
            relationship_type=PatternRelationType.CONTAINS,
            confidence=0.95,
            metadata={"interface_members": True}
        ),
        PatternRelationship(
            source_pattern="interface_definition",
            target_pattern="javadoc",
            relationship_type=PatternRelationType.COMPLEMENTS,
            confidence=0.9,
            metadata={"documentation": True}
        )
    ]
}

# Performance metrics tracking for Java patterns
JAVA_PATTERN_METRICS = {
    "class_definition": PatternPerformanceMetrics(
        execution_time=0.0,
        memory_usage=0,
        cache_hits=0,
        cache_misses=0,
        error_count=0,
        success_rate=0.0,
        pattern_stats={"matches": 0, "failures": 0}
    ),
    "method_definition": PatternPerformanceMetrics(
        execution_time=0.0,
        memory_usage=0,
        cache_hits=0,
        cache_misses=0,
        error_count=0,
        success_rate=0.0,
        pattern_stats={"matches": 0, "failures": 0}
    ),
    "interface_definition": PatternPerformanceMetrics(
        execution_time=0.0,
        memory_usage=0,
        cache_hits=0,
        cache_misses=0,
        error_count=0,
        success_rate=0.0,
        pattern_stats={"matches": 0, "failures": 0}
    )
}

# Enhanced Java patterns with proper typing and relationships
JAVA_PATTERNS = {
    **COMMON_PATTERNS,  # Inherit common patterns
    
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "class_definition": ResilientPattern(
                name="class_definition",
                pattern="""
                [
                    (class_declaration
                        name: (identifier) @syntax.class.name
                        superclass: (superclass)? @syntax.class.superclass
                        interfaces: (super_interfaces)? @syntax.class.interfaces
                        body: (class_body) @syntax.class.body) @syntax.class.def
                ]
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="java",
                confidence=0.95,
                metadata={
                    "relationships": JAVA_PATTERN_RELATIONSHIPS["class_definition"],
                    "metrics": JAVA_PATTERN_METRICS["class_definition"],
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    )
                }
            ),
            
            "method_definition": ResilientPattern(
                name="method_definition",
                pattern="""
                [
                    (method_declaration
                        modifiers: (modifiers)? @syntax.method.modifiers
                        type: (_) @syntax.method.return_type
                        name: (identifier) @syntax.method.name
                        parameters: (formal_parameters) @syntax.method.params
                        body: (block)? @syntax.method.body) @syntax.method.def
                ]
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="java",
                confidence=0.95,
                metadata={
                    "relationships": JAVA_PATTERN_RELATIONSHIPS["method_definition"],
                    "metrics": JAVA_PATTERN_METRICS["method_definition"],
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    )
                }
            ),
            
            "interface_definition": ResilientPattern(
                name="interface_definition",
                pattern="""
                [
                    (interface_declaration
                        name: (identifier) @syntax.interface.name
                        extends: (extends_interfaces)? @syntax.interface.extends
                        body: (interface_body) @syntax.interface.body) @syntax.interface.def
                ]
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="java",
                confidence=0.95,
                metadata={
                    "relationships": JAVA_PATTERN_RELATIONSHIPS["interface_definition"],
                    "metrics": JAVA_PATTERN_METRICS["interface_definition"],
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
            "field_declaration": AdaptivePattern(
                name="field_declaration",
                pattern="""
                [
                    (field_declaration
                        modifiers: (modifiers)? @semantics.field.modifiers
                        type: (_) @semantics.field.type
                        declarator: (variable_declarator
                            name: (identifier) @semantics.field.name
                            value: (_)? @semantics.field.value)) @semantics.field.def
                ]
                """,
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="java",
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
            
            "annotation": AdaptivePattern(
                name="annotation",
                pattern="""
                [
                    (annotation
                        name: (_) @semantics.annotation.name
                        arguments: (annotation_argument_list)? @semantics.annotation.args) @semantics.annotation.def
                ]
                """,
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="java",
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
            "javadoc": AdaptivePattern(
                name="javadoc",
                pattern="""
                [
                    (block_comment) @documentation.javadoc
                ]
                """,
                category=PatternCategory.DOCUMENTATION,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="java",
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
            
            "comments": AdaptivePattern(
                name="comments",
                pattern="""
                [
                    (line_comment) @documentation.comment,
                    (block_comment) @documentation.block_comment
                ]
                """,
                category=PatternCategory.DOCUMENTATION,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="java",
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
    """Create pattern context for Java files."""
    return PatternContext(
        code_structure=code_structure,
        language_stats={"language": "java", "version": "17+"},
        project_patterns=[],
        file_location=file_path,
        dependencies=set(),
        recent_changes=[],
        scope_level="global",
        allows_nesting=True,
        relevant_patterns=list(JAVA_PATTERNS.keys())
    )

def get_java_pattern_relationships(pattern_name: str) -> List[PatternRelationship]:
    """Get relationships for a specific pattern."""
    return JAVA_PATTERN_RELATIONSHIPS.get(pattern_name, [])

def update_java_pattern_metrics(pattern_name: str, metrics: Dict[str, Any]) -> None:
    """Update performance metrics for a pattern."""
    if pattern_name in JAVA_PATTERN_METRICS:
        pattern_metrics = JAVA_PATTERN_METRICS[pattern_name]
        pattern_metrics.execution_time = metrics.get("execution_time", 0.0)
        pattern_metrics.memory_usage = metrics.get("memory_usage", 0)
        pattern_metrics.cache_hits = metrics.get("cache_hits", 0)
        pattern_metrics.cache_misses = metrics.get("cache_misses", 0)
        pattern_metrics.error_count = metrics.get("error_count", 0)
        
        total = pattern_metrics.cache_hits + pattern_metrics.cache_misses
        if total > 0:
            pattern_metrics.success_rate = pattern_metrics.cache_hits / total

def get_java_pattern_match_result(
    pattern_name: str,
    matches: List[Dict[str, Any]],
    context: PatternContext
) -> PatternMatchResult:
    """Create a pattern match result with relationships and metrics."""
    return PatternMatchResult(
        pattern_name=pattern_name,
        matches=matches,
        context=context,
        relationships=get_java_pattern_relationships(pattern_name),
        performance=JAVA_PATTERN_METRICS.get(pattern_name, PatternPerformanceMetrics()),
        validation=PatternValidationResult(is_valid=True),
        metadata={"language": "java"}
    )

# Export public interfaces
__all__ = [
    'JAVA_PATTERNS',
    'JAVA_PATTERN_RELATIONSHIPS',
    'JAVA_PATTERN_METRICS',
    'create_pattern_context',
    'get_java_pattern_relationships',
    'update_java_pattern_metrics',
    'get_java_pattern_match_result'
]

# Module identification
LANGUAGE = "java"

class JavaPatternLearner(CrossProjectPatternLearner):
    """Enhanced Java pattern learner with full system integration."""
    
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
        self._feature_extractor = await BaseFeatureExtractor.create("java", FileType.CODE)
        self._unified_parser = await get_unified_parser()
        self._ai_processor = await get_ai_pattern_processor()
        
        # Register with pattern processor
        await self._pattern_processor.register_language_patterns(
            "java", 
            JAVA_PATTERNS,
            self
        )

    async def _get_parser(self) -> BaseParser:
        """Get appropriate parser for Java."""
        # Try tree-sitter first
        tree_sitter_parser = await get_tree_sitter_parser("java")
        if tree_sitter_parser:
            return tree_sitter_parser
            
        # Fallback to base parser
        return await BaseParser.create(
            language_id="java",
            file_type=FileType.CODE,
            parser_type=ParserType.CUSTOM
        )

    async def learn_from_project(self, project_path: str) -> List[Dict[str, Any]]:
        """Learn patterns with AI assistance."""
        if not self._ai_processor:
            await self.initialize()
            
        # Try AI-assisted learning first
        ai_context = AIContext(
            language_id="java",
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
        async with AsyncErrorBoundary("java_pattern_learning"):
            # Extract blocks using block extractor
            blocks = await self._block_extractor.extract_from_project(
                project_path,
                language_id="java"
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
java_pattern_learner = JavaPatternLearner()

@handle_async_errors(error_types=ProcessingError)
async def process_java_pattern(
    pattern: Union[AdaptivePattern, ResilientPattern],
    source_code: str,
    context: Optional[PatternContext] = None
) -> List[Dict[str, Any]]:
    """Process a Java pattern with full system integration."""
    async with AsyncErrorBoundary(
        operation_name=f"process_pattern_{pattern.name}",
        error_types=ProcessingError,
        severity=ErrorSeverity.ERROR
    ):
        # Get all required components
        block_extractor = await get_block_extractor()
        feature_extractor = await BaseFeatureExtractor.create("java", FileType.CODE)
        unified_parser = await get_unified_parser()
        
        # Parse if needed
        if not context or not context.code_structure:
            parse_result = await unified_parser.parse(source_code, "java", FileType.CODE)
            if parse_result and parse_result.ast:
                context = await create_pattern_context(
                    "",
                    parse_result.ast
                )
        
        # Extract and process blocks
        blocks = await block_extractor.get_child_blocks(
            "java",
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
        await update_java_pattern_metrics(
            pattern.name,
            {
                "execution_time": time.time() - start_time,
                "matches": len(matches)
            }
        )
        
        return matches

# Update initialization
async def initialize_java_patterns():
    """Initialize Java patterns during app startup."""
    global java_pattern_learner
    
    # Initialize pattern processor first
    await pattern_processor.initialize()
    
    # Register Java patterns
    await pattern_processor.register_language_patterns(
        "java",
        JAVA_PATTERNS,
        metadata={
            "parser_type": ParserType.TREE_SITTER,
            "supports_learning": True,
            "supports_adaptation": True,
            "capabilities": JAVA_CAPABILITIES
        }
    )
    
    # Create and initialize learner
    java_pattern_learner = await JavaPatternLearner.create()
    
    # Register learner with pattern processor
    await pattern_processor.register_pattern_learner(
        "java",
        java_pattern_learner
    )
    
    await global_health_monitor.update_component_status(
        "java_patterns",
        ComponentStatus.HEALTHY,
        details={
            "patterns_loaded": len(JAVA_PATTERNS),
            "capabilities": list(JAVA_CAPABILITIES)
        }
    )

async def extract_java_features(
    pattern: Union[AdaptivePattern, ResilientPattern],
    matches: List[Dict[str, Any]],
    context: PatternContext
) -> ExtractedFeatures:
    """Extract features from pattern matches."""
    feature_extractor = await BaseFeatureExtractor.create("java", FileType.CODE)
    
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

async def validate_java_pattern(
    pattern: Union[AdaptivePattern, ResilientPattern],
    context: Optional[PatternContext] = None
) -> PatternValidationResult:
    """Validate a Java pattern with system integration."""
    async with AsyncErrorBoundary("java_pattern_validation"):
        # Get pattern processor
        validation_result = await pattern_processor.validate_pattern(
            pattern,
            language_id="java",
            context=context
        )
        
        # Update pattern metrics
        if not validation_result.is_valid:
            pattern_metrics = JAVA_PATTERN_METRICS.get(pattern.name)
            if pattern_metrics:
                pattern_metrics.error_count += 1
        
        return validation_result 