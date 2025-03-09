"""Bash-specific patterns with enhanced type system and relationships.

This module provides Bash-specific patterns that integrate with the enhanced
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

# Pattern relationships for Bash
BASH_PATTERN_RELATIONSHIPS = {
    "function_definition": [
        PatternRelationship(
            source_pattern="function_definition",
            target_pattern="comments",
            relationship_type=PatternRelationType.COMPLEMENTS,
            confidence=0.8,
            metadata={"documentation": True}
        )
    ],
    "variable_assignment": [
        PatternRelationship(
            source_pattern="variable_assignment",
            target_pattern="comments",
            relationship_type=PatternRelationType.COMPLEMENTS,
            confidence=0.8,
            metadata={"documentation": True}
        )
    ],
    "control_flow": [
        PatternRelationship(
            source_pattern="control_flow",
            target_pattern="comments",
            relationship_type=PatternRelationType.COMPLEMENTS,
            confidence=0.8,
            metadata={"documentation": True}
        )
    ]
}

# Performance metrics tracking for Bash patterns
BASH_PATTERN_METRICS = {
    "function_definition": PatternPerformanceMetrics(
        execution_time=0.0,
        memory_usage=0,
        cache_hits=0,
        cache_misses=0,
        error_count=0,
        success_rate=0.0,
        pattern_stats={"matches": 0, "failures": 0}
    ),
    "variable_assignment": PatternPerformanceMetrics(
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
    )
}

# Enhanced Bash patterns with proper typing and relationships
BASH_PATTERNS = {
    **COMMON_PATTERNS,  # Inherit common patterns
    
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "function_definition": ResilientPattern(
                name="function_definition",
                pattern="""
                [
                    (function_definition
                        name: (word) @syntax.function.name
                        body: (compound_statement) @syntax.function.body) @syntax.function.def
                ]
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="bash",
                confidence=0.95,
                metadata={
                    "relationships": BASH_PATTERN_RELATIONSHIPS["function_definition"],
                    "metrics": BASH_PATTERN_METRICS["function_definition"],
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
                    (if_statement
                        condition: (_) @syntax.if.condition
                        consequence: (_) @syntax.if.then
                        alternative: (_)? @syntax.if.else) @syntax.if.statement,
                    
                    (for_statement
                        variable: (_) @syntax.for.variable
                        value: (_) @syntax.for.value
                        body: (_) @syntax.for.body) @syntax.for.statement,
                    
                    (while_statement
                        condition: (_) @syntax.while.condition
                        body: (_) @syntax.while.body) @syntax.while.statement,
                    
                    (case_statement
                        value: (_) @syntax.case.value
                        body: (_) @syntax.case.body) @syntax.case.statement
                ]
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="bash",
                confidence=0.95,
                metadata={
                    "relationships": BASH_PATTERN_RELATIONSHIPS["control_flow"],
                    "metrics": BASH_PATTERN_METRICS["control_flow"],
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
            "variable_assignment": AdaptivePattern(
                name="variable_assignment",
                pattern="""
                [
                    (variable_assignment
                        name: (_) @semantics.var.name
                        value: (_) @semantics.var.value) @semantics.var.assignment,
                    
                    (command_substitution
                        command: (_) @semantics.var.command) @semantics.var.substitution
                ]
                """,
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="bash",
                confidence=0.9,
                metadata={
                    "relationships": BASH_PATTERN_RELATIONSHIPS["variable_assignment"],
                    "metrics": BASH_PATTERN_METRICS["variable_assignment"],
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
                language_id="bash",
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
    """Create pattern context for Bash files."""
    return PatternContext(
        code_structure=code_structure,
        language_stats={"language": "bash", "version": "5.0+"},
        project_patterns=[],
        file_location=file_path,
        dependencies=set(),
        recent_changes=[],
        scope_level="global",
        allows_nesting=True,
        relevant_patterns=list(BASH_PATTERNS.keys())
    )

def get_bash_pattern_relationships(pattern_name: str) -> List[PatternRelationship]:
    """Get relationships for a specific pattern."""
    return BASH_PATTERN_RELATIONSHIPS.get(pattern_name, [])

def update_bash_pattern_metrics(pattern_name: str, metrics: Dict[str, Any]) -> None:
    """Update performance metrics for a pattern."""
    if pattern_name in BASH_PATTERN_METRICS:
        pattern_metrics = BASH_PATTERN_METRICS[pattern_name]
        pattern_metrics.execution_time = metrics.get("execution_time", 0.0)
        pattern_metrics.memory_usage = metrics.get("memory_usage", 0)
        pattern_metrics.cache_hits = metrics.get("cache_hits", 0)
        pattern_metrics.cache_misses = metrics.get("cache_misses", 0)
        pattern_metrics.error_count = metrics.get("error_count", 0)
        
        total = pattern_metrics.cache_hits + pattern_metrics.cache_misses
        if total > 0:
            pattern_metrics.success_rate = pattern_metrics.cache_hits / total

def get_bash_pattern_match_result(
    pattern_name: str,
    matches: List[Dict[str, Any]],
    context: PatternContext
) -> PatternMatchResult:
    """Create a pattern match result with relationships and metrics."""
    return PatternMatchResult(
        pattern_name=pattern_name,
        matches=matches,
        context=context,
        relationships=get_bash_pattern_relationships(pattern_name),
        performance=BASH_PATTERN_METRICS.get(pattern_name, PatternPerformanceMetrics()),
        validation=PatternValidationResult(is_valid=True),
        metadata={"language": "bash"}
    )

# Export public interfaces
__all__ = [
    'BASH_PATTERNS',
    'BASH_PATTERN_RELATIONSHIPS',
    'BASH_PATTERN_METRICS',
    'create_pattern_context',
    'get_bash_pattern_relationships',
    'update_bash_pattern_metrics',
    'get_bash_pattern_match_result'
]

# Module identification
LANGUAGE = "bash" 