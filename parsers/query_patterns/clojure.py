"""Clojure-specific patterns with enhanced type system and relationships.

This module provides Clojure-specific patterns that integrate with the enhanced
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

# Pattern relationships for Clojure
CLOJURE_PATTERN_RELATIONSHIPS = {
    "function_definition": [
        PatternRelationship(
            source_pattern="function_definition",
            target_pattern="docstring",
            relationship_type=PatternRelationType.COMPLEMENTS,
            confidence=0.8,
            metadata={"best_practice": True}
        )
    ],
    "class_definition": [
        PatternRelationship(
            source_pattern="class_definition",
            target_pattern="function_definition",
            relationship_type=PatternRelationType.IMPLEMENTS,
            confidence=0.9,
            metadata={"methods": True}
        ),
        PatternRelationship(
            source_pattern="class_definition",
            target_pattern="docstring",
            relationship_type=PatternRelationType.COMPLEMENTS,
            confidence=0.8,
            metadata={"best_practice": True}
        )
    ],
    "namespace": [
        PatternRelationship(
            source_pattern="namespace",
            target_pattern="function_definition",
            relationship_type=PatternRelationType.CONTAINS,
            confidence=0.95,
            metadata={"namespace_members": True}
        ),
        PatternRelationship(
            source_pattern="namespace",
            target_pattern="class_definition",
            relationship_type=PatternRelationType.CONTAINS,
            confidence=0.95,
            metadata={"namespace_members": True}
        )
    ]
}

# Performance metrics tracking for Clojure patterns
CLOJURE_PATTERN_METRICS = {
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
    "namespace": PatternPerformanceMetrics(
        execution_time=0.0,
        memory_usage=0,
        cache_hits=0,
        cache_misses=0,
        error_count=0,
        success_rate=0.0,
        pattern_stats={"matches": 0, "failures": 0}
    )
}

# Enhanced Clojure patterns with proper typing and relationships
CLOJURE_PATTERNS = {
    **COMMON_PATTERNS,  # Inherit common patterns
    
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "function_definition": ResilientPattern(
                name="function_definition",
                pattern="""
                [
                    (list_lit
                        .
                        (sym_lit) @syntax.function.type
                        (#match? @syntax.function.type "^(defn|defn-|fn)$")
                        .
                        (sym_lit) @syntax.function.name
                        .
                        (vec_lit)? @syntax.function.params
                        .
                        (_)* @syntax.function.body) @syntax.function.def,
                    
                    (list_lit
                        .
                        (sym_lit) @syntax.macro.type
                        (#match? @syntax.macro.type "^defmacro$")
                        .
                        (sym_lit) @syntax.macro.name
                        .
                        (vec_lit)? @syntax.macro.params
                        .
                        (_)* @syntax.macro.body) @syntax.macro.def
                ]
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="clojure",
                confidence=0.95,
                metadata={
                    "relationships": CLOJURE_PATTERN_RELATIONSHIPS["function_definition"],
                    "metrics": CLOJURE_PATTERN_METRICS["function_definition"],
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
                    (list_lit
                        .
                        (sym_lit) @syntax.class.type
                        (#match? @syntax.class.type "^(defrecord|defprotocol|deftype)$")
                        .
                        (sym_lit) @syntax.class.name
                        .
                        [(vec_lit) @syntax.class.fields
                         (_)* @syntax.class.body]) @syntax.class.def
                ]
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="clojure",
                confidence=0.95,
                metadata={
                    "relationships": CLOJURE_PATTERN_RELATIONSHIPS["class_definition"],
                    "metrics": CLOJURE_PATTERN_METRICS["class_definition"],
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
                    (list_lit
                        .
                        (sym_lit) @semantics.var.type
                        (#match? @semantics.var.type "^(def|defonce)$")
                        .
                        (sym_lit) @semantics.var.name
                        .
                        (_)? @semantics.var.value) @semantics.var.def
                ]
                """,
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="clojure",
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
            "namespace": ResilientPattern(
                name="namespace",
                pattern="""
                [
                    (list_lit
                        .
                        (sym_lit) @structure.ns.type
                        (#match? @structure.ns.type "^(ns|in-ns)$")
                        .
                        [(sym_lit) @structure.ns.name
                         (quote) @structure.ns.quoted]
                        .
                        (_)* @structure.ns.body) @structure.ns.def
                ]
                """,
                category=PatternCategory.STRUCTURE,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="clojure",
                confidence=0.95,
                metadata={
                    "relationships": CLOJURE_PATTERN_RELATIONSHIPS["namespace"],
                    "metrics": CLOJURE_PATTERN_METRICS["namespace"],
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
                    (dis_expr) @documentation.disabled
                ]
                """,
                category=PatternCategory.DOCUMENTATION,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="clojure",
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
    """Create pattern context for Clojure files."""
    return PatternContext(
        code_structure=code_structure,
        language_stats={"language": "clojure", "version": "1.11+"},
        project_patterns=[],
        file_location=file_path,
        dependencies=set(),
        recent_changes=[],
        scope_level="global",
        allows_nesting=True,
        relevant_patterns=list(CLOJURE_PATTERNS.keys())
    )

def get_clojure_pattern_relationships(pattern_name: str) -> List[PatternRelationship]:
    """Get relationships for a specific pattern."""
    return CLOJURE_PATTERN_RELATIONSHIPS.get(pattern_name, [])

def update_clojure_pattern_metrics(pattern_name: str, metrics: Dict[str, Any]) -> None:
    """Update performance metrics for a pattern."""
    if pattern_name in CLOJURE_PATTERN_METRICS:
        pattern_metrics = CLOJURE_PATTERN_METRICS[pattern_name]
        pattern_metrics.execution_time = metrics.get("execution_time", 0.0)
        pattern_metrics.memory_usage = metrics.get("memory_usage", 0)
        pattern_metrics.cache_hits = metrics.get("cache_hits", 0)
        pattern_metrics.cache_misses = metrics.get("cache_misses", 0)
        pattern_metrics.error_count = metrics.get("error_count", 0)
        
        total = pattern_metrics.cache_hits + pattern_metrics.cache_misses
        if total > 0:
            pattern_metrics.success_rate = pattern_metrics.cache_hits / total

def get_clojure_pattern_match_result(
    pattern_name: str,
    matches: List[Dict[str, Any]],
    context: PatternContext
) -> PatternMatchResult:
    """Create a pattern match result with relationships and metrics."""
    return PatternMatchResult(
        pattern_name=pattern_name,
        matches=matches,
        context=context,
        relationships=get_clojure_pattern_relationships(pattern_name),
        performance=CLOJURE_PATTERN_METRICS.get(pattern_name, PatternPerformanceMetrics()),
        validation=PatternValidationResult(is_valid=True),
        metadata={"language": "clojure"}
    )

# Export public interfaces
__all__ = [
    'CLOJURE_PATTERNS',
    'CLOJURE_PATTERN_RELATIONSHIPS',
    'CLOJURE_PATTERN_METRICS',
    'create_pattern_context',
    'get_clojure_pattern_relationships',
    'update_clojure_pattern_metrics',
    'get_clojure_pattern_match_result'
]

# Module identification
LANGUAGE = "clojure" 