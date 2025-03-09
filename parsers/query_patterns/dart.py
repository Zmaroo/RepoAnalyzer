"""Dart-specific patterns with enhanced type system and relationships.

This module provides Dart-specific patterns that integrate with the enhanced
pattern processing system, including proper typing, relationships, and context.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from parsers.types import (
    PatternCategory, PatternPurpose, PatternType, PatternRelationType,
    PatternContext, PatternRelationship, PatternPerformanceMetrics,
    PatternValidationResult, PatternMatchResult, QueryPattern
)
from parsers.models import PATTERN_CATEGORIES
from .common import COMMON_PATTERNS
from .enhanced_patterns import AdaptivePattern, ResilientPattern

# Pattern relationships for Dart
DART_PATTERN_RELATIONSHIPS = {
    "class_definition": [
        PatternRelationship(
            source_pattern="class_definition",
            target_pattern="method_definition",
            relationship_type=PatternRelationType.IMPLEMENTS,
            confidence=0.95,
            metadata={"methods": True}
        ),
        PatternRelationship(
            source_pattern="class_definition",
            target_pattern="comment",
            relationship_type=PatternRelationType.COMPLEMENTS,
            confidence=0.8,
            metadata={"best_practice": True}
        )
    ],
    "method_definition": [
        PatternRelationship(
            source_pattern="method_definition",
            target_pattern="type_annotation",
            relationship_type=PatternRelationType.USES,
            confidence=0.9,
            metadata={"types": True}
        )
    ],
    "widget": [
        PatternRelationship(
            source_pattern="widget",
            target_pattern="build_method",
            relationship_type=PatternRelationType.REQUIRES,
            confidence=0.95,
            metadata={"flutter": True}
        )
    ]
}

# Performance metrics tracking for Dart patterns
DART_PATTERN_METRICS = {
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
    "widget": PatternPerformanceMetrics(
        execution_time=0.0,
        memory_usage=0,
        cache_hits=0,
        cache_misses=0,
        error_count=0,
        success_rate=0.0,
        pattern_stats={"matches": 0, "failures": 0}
    )
}

# Enhanced Dart patterns with proper typing and relationships
DART_PATTERNS = {
    **COMMON_PATTERNS,  # Inherit common patterns
    
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "class_definition": ResilientPattern(
                name="class_definition",
                pattern="""
                [
                    (class_declaration
                        metadata: (metadata)* @syntax.class.metadata
                        modifiers: [(abstract)]* @syntax.class.modifier
                        name: (identifier) @syntax.class.name
                        type_parameters: (type_parameters)? @syntax.class.type_params
                        superclass: (superclass)? @syntax.class.extends
                        interfaces: (interfaces)? @syntax.class.implements
                        mixins: (mixins)? @syntax.class.with
                        body: (class_body) @syntax.class.body) @syntax.class.def,
                        
                    (mixin_declaration
                        metadata: (metadata)* @syntax.mixin.metadata
                        name: (identifier) @syntax.mixin.name
                        on: (on_clause)? @syntax.mixin.on
                        interfaces: (interfaces)? @syntax.mixin.implements
                        body: (class_body) @syntax.mixin.body) @syntax.mixin.def
                ]
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="dart",
                confidence=0.95,
                metadata={
                    "relationships": DART_PATTERN_RELATIONSHIPS["class_definition"],
                    "metrics": DART_PATTERN_METRICS["class_definition"],
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
                        metadata: (metadata)* @syntax.method.metadata
                        modifiers: [(static) (abstract) (external)]* @syntax.method.modifier
                        return_type: (_)? @syntax.method.return_type
                        name: (identifier) @syntax.method.name
                        parameters: (formal_parameter_list) @syntax.method.params
                        body: [(block) (arrow_body)]? @syntax.method.body) @syntax.method.def
                ]
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="dart",
                confidence=0.95,
                metadata={
                    "relationships": DART_PATTERN_RELATIONSHIPS["method_definition"],
                    "metrics": DART_PATTERN_METRICS["method_definition"],
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
            "async": AdaptivePattern(
                name="async",
                pattern="""
                [
                    (function_declaration
                        body: (block
                            (async_marker) @semantics.async.marker)) @semantics.async.function,
                            
                    (method_declaration
                        body: (block
                            (async_marker) @semantics.async.method.marker)) @semantics.async.method,
                            
                    (await_expression
                        expression: (_) @semantics.async.await.expr) @semantics.async.await,
                        
                    (yield_statement
                        expression: (_)? @semantics.async.yield.expr) @semantics.async.yield
                ]
                """,
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="dart",
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
            
            "widget": ResilientPattern(
                name="widget",
                pattern="""
                [
                    (class_declaration
                        metadata: (metadata
                            (identifier) @semantics.widget.annotation
                            (#match? @semantics.widget.annotation "^Widget$")) @semantics.widget.metadata
                        name: (identifier) @semantics.widget.name) @semantics.widget.class,
                        
                    (method_declaration
                        name: (identifier) @semantics.widget.build
                        (#match? @semantics.widget.build "^build$")
                        body: (block
                            (return_statement
                                expression: (_) @semantics.widget.build.return))) @semantics.widget.build_method
                ]
                """,
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="dart",
                confidence=0.95,
                metadata={
                    "relationships": DART_PATTERN_RELATIONSHIPS["widget"],
                    "metrics": DART_PATTERN_METRICS["widget"],
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
                    (comment) @documentation.comment,
                    (documentation_comment
                        content: (_)* @documentation.doc.content) @documentation.doc,
                    (documentation_comment
                        reference: (identifier) @documentation.doc.reference) @documentation.doc.ref
                ]
                """,
                category=PatternCategory.DOCUMENTATION,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="dart",
                confidence=0.9,
                metadata={
                    "relationships": [
                        PatternRelationship(
                            source_pattern="comments",
                            target_pattern="class_definition",
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
    """Create pattern context for Dart files."""
    return PatternContext(
        code_structure=code_structure,
        language_stats={"language": "dart", "version": "2.19+"},
        project_patterns=[],
        file_location=file_path,
        dependencies=set(),
        recent_changes=[],
        scope_level="global",
        allows_nesting=True,
        relevant_patterns=list(DART_PATTERNS.keys())
    )

def get_dart_pattern_relationships(pattern_name: str) -> List[PatternRelationship]:
    """Get relationships for a specific pattern."""
    return DART_PATTERN_RELATIONSHIPS.get(pattern_name, [])

def update_dart_pattern_metrics(pattern_name: str, metrics: Dict[str, Any]) -> None:
    """Update performance metrics for a pattern."""
    if pattern_name in DART_PATTERN_METRICS:
        pattern_metrics = DART_PATTERN_METRICS[pattern_name]
        pattern_metrics.execution_time = metrics.get("execution_time", 0.0)
        pattern_metrics.memory_usage = metrics.get("memory_usage", 0)
        pattern_metrics.cache_hits = metrics.get("cache_hits", 0)
        pattern_metrics.cache_misses = metrics.get("cache_misses", 0)
        pattern_metrics.error_count = metrics.get("error_count", 0)
        
        total = pattern_metrics.cache_hits + pattern_metrics.cache_misses
        if total > 0:
            pattern_metrics.success_rate = pattern_metrics.cache_hits / total

def get_dart_pattern_match_result(
    pattern_name: str,
    matches: List[Dict[str, Any]],
    context: PatternContext
) -> PatternMatchResult:
    """Create a pattern match result with relationships and metrics."""
    return PatternMatchResult(
        pattern_name=pattern_name,
        matches=matches,
        context=context,
        relationships=get_dart_pattern_relationships(pattern_name),
        performance=DART_PATTERN_METRICS.get(pattern_name, PatternPerformanceMetrics()),
        validation=PatternValidationResult(is_valid=True),
        metadata={"language": "dart"}
    )

# Export public interfaces
__all__ = [
    'DART_PATTERNS',
    'DART_PATTERN_RELATIONSHIPS',
    'DART_PATTERN_METRICS',
    'create_pattern_context',
    'get_dart_pattern_relationships',
    'update_dart_pattern_metrics',
    'get_dart_pattern_match_result'
] 