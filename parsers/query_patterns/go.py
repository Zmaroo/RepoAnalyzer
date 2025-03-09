"""Go-specific patterns with enhanced type system and relationships.

This module provides Go-specific patterns that integrate with the enhanced
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

# Pattern relationships for Go
GO_PATTERN_RELATIONSHIPS = {
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
    "type": [
        PatternRelationship(
            source_pattern="type",
            target_pattern="interface",
            relationship_type=PatternRelationType.IMPLEMENTS,
            confidence=0.95,
            metadata={"interfaces": True}
        ),
        PatternRelationship(
            source_pattern="type",
            target_pattern="struct",
            relationship_type=PatternRelationType.DEFINES,
            confidence=0.9,
            metadata={"struct_fields": True}
        )
    ],
    "package": [
        PatternRelationship(
            source_pattern="package",
            target_pattern="import",
            relationship_type=PatternRelationType.USES,
            confidence=0.95,
            metadata={"imports": True}
        ),
        PatternRelationship(
            source_pattern="package",
            target_pattern="function",
            relationship_type=PatternRelationType.CONTAINS,
            confidence=0.9,
            metadata={"package_functions": True}
        )
    ]
}

# Performance metrics tracking for Go patterns
GO_PATTERN_METRICS = {
    "function": PatternPerformanceMetrics(
        execution_time=0.0,
        memory_usage=0,
        cache_hits=0,
        cache_misses=0,
        error_count=0,
        success_rate=0.0,
        pattern_stats={"matches": 0, "failures": 0}
    ),
    "type": PatternPerformanceMetrics(
        execution_time=0.0,
        memory_usage=0,
        cache_hits=0,
        cache_misses=0,
        error_count=0,
        success_rate=0.0,
        pattern_stats={"matches": 0, "failures": 0}
    ),
    "package": PatternPerformanceMetrics(
        execution_time=0.0,
        memory_usage=0,
        cache_hits=0,
        cache_misses=0,
        error_count=0,
        success_rate=0.0,
        pattern_stats={"matches": 0, "failures": 0}
    )
}

# Enhanced Go patterns with proper typing and relationships
GO_PATTERNS = {
    **COMMON_PATTERNS,  # Inherit common patterns
    
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "function": ResilientPattern(
                name="function",
                pattern="""
                [
                    (function_declaration
                        name: (_) @syntax.function.name
                        parameters: (_) @syntax.function.params
                        result: (_)? @syntax.function.result
                        body: (_) @syntax.function.body) @syntax.function.def,
                    (method_declaration
                        name: (_) @syntax.function.name
                        receiver: (_) @syntax.function.receiver
                        parameters: (_) @syntax.function.params
                        result: (_)? @syntax.function.result
                        body: (_) @syntax.function.body) @syntax.function.method
                ]
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="go",
                confidence=0.95,
                metadata={
                    "relationships": GO_PATTERN_RELATIONSHIPS["function"],
                    "metrics": GO_PATTERN_METRICS["function"],
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    )
                }
            ),
            
            "type": ResilientPattern(
                name="type",
                pattern="""
                [
                    (type_declaration
                        name: (_) @syntax.type.name
                        type: (_) @syntax.type.def) @syntax.type.decl,
                    (struct_type
                        fields: (_) @syntax.type.struct.fields) @syntax.type.struct,
                    (interface_type
                        methods: (_) @syntax.type.interface.methods) @syntax.type.interface
                ]
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="go",
                confidence=0.95,
                metadata={
                    "relationships": GO_PATTERN_RELATIONSHIPS["type"],
                    "metrics": GO_PATTERN_METRICS["type"],
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
                    (var_declaration
                        name: (_) @semantics.variable.name
                        type: (_)? @semantics.variable.type
                        value: (_)? @semantics.variable.value) @semantics.variable.def,
                    (const_declaration
                        name: (_) @semantics.variable.const.name
                        type: (_)? @semantics.variable.const.type
                        value: (_)? @semantics.variable.const.value) @semantics.variable.const,
                    (short_var_declaration
                        left: (_) @semantics.variable.short.name
                        right: (_) @semantics.variable.short.value) @semantics.variable.short
                ]
                """,
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="go",
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
                    (binary_expression
                        left: (_) @semantics.expression.binary.left
                        operator: (_) @semantics.expression.binary.op
                        right: (_) @semantics.expression.binary.right) @semantics.expression.binary,
                    (call_expression
                        function: (_) @semantics.expression.call.func
                        arguments: (_) @semantics.expression.call.args) @semantics.expression.call
                ]
                """,
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="go",
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
                    (comment) @documentation.comment,
                    (interpreted_string_literal) @documentation.string
                ]
                """,
                category=PatternCategory.DOCUMENTATION,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="go",
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
    },
    
    PatternCategory.STRUCTURE: {
        PatternPurpose.UNDERSTANDING: {
            "package": ResilientPattern(
                name="package",
                pattern="""
                (package_clause
                    name: (_) @structure.package.name) @structure.package.def
                """,
                category=PatternCategory.STRUCTURE,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="go",
                confidence=0.95,
                metadata={
                    "relationships": GO_PATTERN_RELATIONSHIPS["package"],
                    "metrics": GO_PATTERN_METRICS["package"],
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    )
                }
            ),
            
            "import": AdaptivePattern(
                name="import",
                pattern="""
                [
                    (import_declaration
                        import_spec: (_) @structure.import.spec) @structure.import.def,
                    (import_spec
                        name: (_)? @structure.import.name
                        path: (_) @structure.import.path) @structure.import.spec
                ]
                """,
                category=PatternCategory.STRUCTURE,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="go",
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
    """Create pattern context for Go files."""
    return PatternContext(
        code_structure=code_structure,
        language_stats={"language": "go"},
        project_patterns=[],
        file_location=file_path,
        dependencies=set(),
        recent_changes=[],
        scope_level="global",
        allows_nesting=True,
        relevant_patterns=list(GO_PATTERNS.keys())
    )

def get_go_pattern_relationships(pattern_name: str) -> List[PatternRelationship]:
    """Get relationships for a specific pattern."""
    return GO_PATTERN_RELATIONSHIPS.get(pattern_name, [])

def update_go_pattern_metrics(pattern_name: str, metrics: Dict[str, Any]) -> None:
    """Update performance metrics for a pattern."""
    if pattern_name in GO_PATTERN_METRICS:
        pattern_metrics = GO_PATTERN_METRICS[pattern_name]
        pattern_metrics.execution_time = metrics.get("execution_time", 0.0)
        pattern_metrics.memory_usage = metrics.get("memory_usage", 0)
        pattern_metrics.cache_hits = metrics.get("cache_hits", 0)
        pattern_metrics.cache_misses = metrics.get("cache_misses", 0)
        pattern_metrics.error_count = metrics.get("error_count", 0)
        
        total = pattern_metrics.cache_hits + pattern_metrics.cache_misses
        if total > 0:
            pattern_metrics.success_rate = pattern_metrics.cache_hits / total

def get_go_pattern_match_result(
    pattern_name: str,
    matches: List[Dict[str, Any]],
    context: PatternContext
) -> PatternMatchResult:
    """Create a pattern match result with relationships and metrics."""
    return PatternMatchResult(
        pattern_name=pattern_name,
        matches=matches,
        context=context,
        relationships=get_go_pattern_relationships(pattern_name),
        performance=GO_PATTERN_METRICS.get(pattern_name, PatternPerformanceMetrics()),
        validation=PatternValidationResult(is_valid=True),
        metadata={"language": "go"}
    )

# Export public interfaces
__all__ = [
    'GO_PATTERNS',
    'GO_PATTERN_RELATIONSHIPS',
    'GO_PATTERN_METRICS',
    'create_pattern_context',
    'get_go_pattern_relationships',
    'update_go_pattern_metrics',
    'get_go_pattern_match_result'
]

# Module identification
LANGUAGE = "go" 