"""Elm-specific patterns with enhanced type system and relationships.

This module provides Elm-specific patterns that integrate with the enhanced
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

# Pattern relationships for Elm
ELM_PATTERN_RELATIONSHIPS = {
    "function": [
        PatternRelationship(
            source_pattern="function",
            target_pattern="type",
            relationship_type=PatternRelationType.USES,
            confidence=0.95,
            metadata={"type_annotation": True}
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
            target_pattern="type_variable",
            relationship_type=PatternRelationType.USES,
            confidence=0.95,
            metadata={"type_variables": True}
        ),
        PatternRelationship(
            source_pattern="type",
            target_pattern="constructor",
            relationship_type=PatternRelationType.DEFINES,
            confidence=0.9,
            metadata={"constructors": True}
        )
    ],
    "module": [
        PatternRelationship(
            source_pattern="module",
            target_pattern="import",
            relationship_type=PatternRelationType.USES,
            confidence=0.95,
            metadata={"imports": True}
        ),
        PatternRelationship(
            source_pattern="module",
            target_pattern="export",
            relationship_type=PatternRelationType.DEFINES,
            confidence=0.9,
            metadata={"exports": True}
        )
    ]
}

# Performance metrics tracking for Elm patterns
ELM_PATTERN_METRICS = {
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

# Enhanced Elm patterns with proper typing and relationships
ELM_PATTERNS = {
    **COMMON_PATTERNS,  # Inherit common patterns
    
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "function": ResilientPattern(
                name="function",
                pattern="""
                (value_declaration
                  pattern: (lower_pattern) @syntax.function.name
                  type_annotation: (type_annotation)? @syntax.function.type
                  value: (value_expr) @syntax.function.body) @syntax.function.def
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="elm",
                confidence=0.95,
                metadata={
                    "relationships": ELM_PATTERN_RELATIONSHIPS["function"],
                    "metrics": ELM_PATTERN_METRICS["function"],
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
                        name: (upper_case_identifier) @syntax.type.name
                        type_variables: (lower_pattern)* @syntax.type.type_vars
                        constructors: (union_variant)+ @syntax.type.constructors) @syntax.type.def,
                    (type_alias_declaration
                        name: (upper_case_identifier) @syntax.type.name
                        type_variables: (lower_pattern)* @syntax.type.type_vars
                        type_expression: (_) @syntax.type.type) @syntax.type.def
                ]
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="elm",
                confidence=0.95,
                metadata={
                    "relationships": ELM_PATTERN_RELATIONSHIPS["type"],
                    "metrics": ELM_PATTERN_METRICS["type"],
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
            "module": ResilientPattern(
                name="module",
                pattern="""
                (module_declaration
                    name: (upper_case_qid) @structure.module.name
                    exposing: (exposed_values)? @structure.module.exports) @structure.module.def
                """,
                category=PatternCategory.STRUCTURE,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="elm",
                confidence=0.95,
                metadata={
                    "relationships": ELM_PATTERN_RELATIONSHIPS["module"],
                    "metrics": ELM_PATTERN_METRICS["module"],
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    )
                }
            ),
            
            "import": AdaptivePattern(
                name="import",
                pattern="""
                (import_declaration
                    module_name: (upper_case_qid) @structure.import.module
                    as_name: (upper_case_identifier)? @structure.import.alias
                    exposing: (exposed_values)? @structure.import.exposed) @structure.import.def
                """,
                category=PatternCategory.STRUCTURE,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="elm",
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
                    (line_comment) @documentation.comment.line,
                    (block_comment) @documentation.comment.block
                ]
                """,
                category=PatternCategory.DOCUMENTATION,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="elm",
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
            ),
            
            "docstring": AdaptivePattern(
                name="docstring",
                pattern="""
                (block_comment
                    content: (_) @documentation.docstring.content
                    (#match? @documentation.docstring.content "^\\|\\s*@docs")) @documentation.docstring.def
                """,
                category=PatternCategory.DOCUMENTATION,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="elm",
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
    """Create pattern context for Elm files."""
    return PatternContext(
        code_structure=code_structure,
        language_stats={"language": "elm"},
        project_patterns=[],
        file_location=file_path,
        dependencies=set(),
        recent_changes=[],
        scope_level="global",
        allows_nesting=True,
        relevant_patterns=list(ELM_PATTERNS.keys())
    )

def get_elm_pattern_relationships(pattern_name: str) -> List[PatternRelationship]:
    """Get relationships for a specific pattern."""
    return ELM_PATTERN_RELATIONSHIPS.get(pattern_name, [])

def update_elm_pattern_metrics(pattern_name: str, metrics: Dict[str, Any]) -> None:
    """Update performance metrics for a pattern."""
    if pattern_name in ELM_PATTERN_METRICS:
        pattern_metrics = ELM_PATTERN_METRICS[pattern_name]
        pattern_metrics.execution_time = metrics.get("execution_time", 0.0)
        pattern_metrics.memory_usage = metrics.get("memory_usage", 0)
        pattern_metrics.cache_hits = metrics.get("cache_hits", 0)
        pattern_metrics.cache_misses = metrics.get("cache_misses", 0)
        pattern_metrics.error_count = metrics.get("error_count", 0)
        
        total = pattern_metrics.cache_hits + pattern_metrics.cache_misses
        if total > 0:
            pattern_metrics.success_rate = pattern_metrics.cache_hits / total

def get_elm_pattern_match_result(
    pattern_name: str,
    matches: List[Dict[str, Any]],
    context: PatternContext
) -> PatternMatchResult:
    """Create a pattern match result with relationships and metrics."""
    return PatternMatchResult(
        pattern_name=pattern_name,
        matches=matches,
        context=context,
        relationships=get_elm_pattern_relationships(pattern_name),
        performance=ELM_PATTERN_METRICS.get(pattern_name, PatternPerformanceMetrics()),
        validation=PatternValidationResult(is_valid=True),
        metadata={"language": "elm"}
    )

# Export public interfaces
__all__ = [
    'ELM_PATTERNS',
    'ELM_PATTERN_RELATIONSHIPS',
    'ELM_PATTERN_METRICS',
    'create_pattern_context',
    'get_elm_pattern_relationships',
    'update_elm_pattern_metrics',
    'get_elm_pattern_match_result'
]

# Module identification
LANGUAGE = "elm" 