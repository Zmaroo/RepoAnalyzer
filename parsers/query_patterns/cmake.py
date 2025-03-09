"""CMake-specific patterns with enhanced type system and relationships.

This module provides CMake-specific patterns that integrate with the enhanced
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

# Pattern relationships for CMake
CMAKE_PATTERN_RELATIONSHIPS = {
    "function_definition": [
        PatternRelationship(
            source_pattern="function_definition",
            target_pattern="command",
            relationship_type=PatternRelationType.IMPLEMENTS,
            confidence=0.9,
            metadata={"commands": True}
        ),
        PatternRelationship(
            source_pattern="function_definition",
            target_pattern="comment",
            relationship_type=PatternRelationType.COMPLEMENTS,
            confidence=0.8,
            metadata={"best_practice": True}
        )
    ],
    "control_flow": [
        PatternRelationship(
            source_pattern="control_flow",
            target_pattern="command",
            relationship_type=PatternRelationType.USES,
            confidence=0.9,
            metadata={"flow_control": True}
        )
    ],
    "variable": [
        PatternRelationship(
            source_pattern="variable",
            target_pattern="command",
            relationship_type=PatternRelationType.USES,
            confidence=0.95,
            metadata={"variable_usage": True}
        )
    ]
}

# Performance metrics tracking for CMake patterns
CMAKE_PATTERN_METRICS = {
    "function_definition": PatternPerformanceMetrics(
        execution_time=0.0,
        memory_usage=0,
        cache_hits=0,
        cache_misses=0,
        error_count=0,
        success_rate=0.0,
        pattern_stats={"matches": 0, "failures": 0}
    ),
    "control_flow": PatternPerformanceMetrics(
        execution_time=0.0,
        memory_usage=0,
        cache_hits=0,
        cache_misses=0,
        error_count=0,
        success_rate=0.0,
        pattern_stats={"matches": 0, "failures": 0}
    ),
    "variable": PatternPerformanceMetrics(
        execution_time=0.0,
        memory_usage=0,
        cache_hits=0,
        cache_misses=0,
        error_count=0,
        success_rate=0.0,
        pattern_stats={"matches": 0, "failures": 0}
    )
}

# Enhanced CMake patterns with proper typing and relationships
CMAKE_PATTERNS = {
    **COMMON_PATTERNS,  # Inherit common patterns
    
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "function_definition": ResilientPattern(
                name="function_definition",
                pattern="""
                [
                    (function_def
                        (function_command
                            (argument_list) @syntax.function.args) @syntax.function.header
                        (body) @syntax.function.body
                        (endfunction_command) @syntax.function.end) @syntax.function.def,
                    
                    (macro_def
                        (macro_command
                            (argument_list) @syntax.macro.args) @syntax.macro.header
                        (body) @syntax.macro.body
                        (endmacro_command) @syntax.macro.end) @syntax.macro.def,
                    
                    (normal_command
                        (identifier) @syntax.command.name
                        (argument_list) @syntax.command.args) @syntax.command.def
                ]
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="cmake",
                confidence=0.95,
                metadata={
                    "relationships": CMAKE_PATTERN_RELATIONSHIPS["function_definition"],
                    "metrics": CMAKE_PATTERN_METRICS["function_definition"],
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    )
                }
            ),
            
            "control_flow": ResilientPattern(
                name="control_flow",
                pattern="""
                [
                    (if_condition
                        (if_command
                            (argument_list) @syntax.if.condition) @syntax.if.start
                        (body) @syntax.if.body
                        [(elseif_command
                            (argument_list) @syntax.if.elseif.condition) @syntax.if.elseif
                         (else_command) @syntax.if.else]*
                        (endif_command) @syntax.if.end) @syntax.if.def,
                    
                    (foreach_loop
                        (foreach_command
                            (argument_list) @syntax.foreach.args) @syntax.foreach.start
                        (body) @syntax.foreach.body
                        (endforeach_command) @syntax.foreach.end) @syntax.foreach.def,
                    
                    (while_loop
                        (while_command
                            (argument_list) @syntax.while.condition) @syntax.while.start
                        (body) @syntax.while.body
                        (endwhile_command) @syntax.while.end) @syntax.while.def
                ]
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="cmake",
                confidence=0.95,
                metadata={
                    "relationships": CMAKE_PATTERN_RELATIONSHIPS["control_flow"],
                    "metrics": CMAKE_PATTERN_METRICS["control_flow"],
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
            "variable": QueryPattern(
                name="variable",
                pattern="""
                [
                    (variable_ref
                        [(normal_var
                            (variable) @semantics.var.name) @semantics.var.normal
                         (env_var
                            (variable) @semantics.var.env.name) @semantics.var.env
                         (cache_var
                            (variable) @semantics.var.cache.name) @semantics.var.cache]) @semantics.var.ref
                ]
                """,
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="cmake",
                confidence=0.95,
                metadata={
                    "relationships": CMAKE_PATTERN_RELATIONSHIPS["variable"],
                    "metrics": CMAKE_PATTERN_METRICS["variable"],
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
            "block": AdaptivePattern(
                name="block",
                pattern="""
                [
                    (block_def
                        (block_command
                            (argument_list) @structure.block.args) @structure.block.start
                            (body) @structure.block.body
                            (endblock_command) @structure.block.end) @structure.block.def
                ]
                """,
                category=PatternCategory.STRUCTURE,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="cmake",
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
                    (bracket_comment) @documentation.comment.bracket
                ]
                """,
                category=PatternCategory.DOCUMENTATION,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="cmake",
                confidence=0.9,
                metadata={
                    "relationships": [
                        PatternRelationship(
                            source_pattern="comments",
                            target_pattern="function_definition",
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
    """Create pattern context for CMake files."""
    return PatternContext(
        code_structure=code_structure,
        language_stats={"language": "cmake", "version": "3.0+"},
        project_patterns=[],
        file_location=file_path,
        dependencies=set(),
        recent_changes=[],
        scope_level="global",
        allows_nesting=True,
        relevant_patterns=list(CMAKE_PATTERNS.keys())
    )

def get_cmake_pattern_relationships(pattern_name: str) -> List[PatternRelationship]:
    """Get relationships for a specific pattern."""
    return CMAKE_PATTERN_RELATIONSHIPS.get(pattern_name, [])

def update_cmake_pattern_metrics(pattern_name: str, metrics: Dict[str, Any]) -> None:
    """Update performance metrics for a pattern."""
    if pattern_name in CMAKE_PATTERN_METRICS:
        pattern_metrics = CMAKE_PATTERN_METRICS[pattern_name]
        pattern_metrics.execution_time = metrics.get("execution_time", 0.0)
        pattern_metrics.memory_usage = metrics.get("memory_usage", 0)
        pattern_metrics.cache_hits = metrics.get("cache_hits", 0)
        pattern_metrics.cache_misses = metrics.get("cache_misses", 0)
        pattern_metrics.error_count = metrics.get("error_count", 0)
        
        total = pattern_metrics.cache_hits + pattern_metrics.cache_misses
        if total > 0:
            pattern_metrics.success_rate = pattern_metrics.cache_hits / total

def get_cmake_pattern_match_result(
    pattern_name: str,
    matches: List[Dict[str, Any]],
    context: PatternContext
) -> PatternMatchResult:
    """Create a pattern match result with relationships and metrics."""
    return PatternMatchResult(
        pattern_name=pattern_name,
        matches=matches,
        context=context,
        relationships=get_cmake_pattern_relationships(pattern_name),
        performance=CMAKE_PATTERN_METRICS.get(pattern_name, PatternPerformanceMetrics()),
        validation=PatternValidationResult(is_valid=True),
        metadata={"language": "cmake"}
    )

# Export public interfaces
__all__ = [
    'CMAKE_PATTERNS',
    'CMAKE_PATTERN_RELATIONSHIPS',
    'CMAKE_PATTERN_METRICS',
    'create_pattern_context',
    'get_cmake_pattern_relationships',
    'update_cmake_pattern_metrics',
    'get_cmake_pattern_match_result'
]

# Module identification
LANGUAGE = "cmake" 