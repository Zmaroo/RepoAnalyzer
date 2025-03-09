"""CSS-specific patterns with enhanced type system and relationships.

This module provides CSS-specific patterns that integrate with the enhanced
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

# Pattern relationships for CSS
CSS_PATTERN_RELATIONSHIPS = {
    "class_definition": [
        PatternRelationship(
            source_pattern="class_definition",
            target_pattern="property",
            relationship_type=PatternRelationType.CONTAINS,
            confidence=0.95,
            metadata={"styles": True}
        ),
        PatternRelationship(
            source_pattern="class_definition",
            target_pattern="comment",
            relationship_type=PatternRelationType.COMPLEMENTS,
            confidence=0.8,
            metadata={"best_practice": True}
        )
    ],
    "property": [
        PatternRelationship(
            source_pattern="property",
            target_pattern="variable",
            relationship_type=PatternRelationType.USES,
            confidence=0.9,
            metadata={"custom_properties": True}
        )
    ],
    "media_query": [
        PatternRelationship(
            source_pattern="media_query",
            target_pattern="class_definition",
            relationship_type=PatternRelationType.CONTAINS,
            confidence=0.95,
            metadata={"responsive": True}
        )
    ]
}

# Performance metrics tracking for CSS patterns
CSS_PATTERN_METRICS = {
    "class_definition": PatternPerformanceMetrics(
        execution_time=0.0,
        memory_usage=0,
        cache_hits=0,
        cache_misses=0,
        error_count=0,
        success_rate=0.0,
        pattern_stats={"matches": 0, "failures": 0}
    ),
    "property": PatternPerformanceMetrics(
        execution_time=0.0,
        memory_usage=0,
        cache_hits=0,
        cache_misses=0,
        error_count=0,
        success_rate=0.0,
        pattern_stats={"matches": 0, "failures": 0}
    ),
    "media_query": PatternPerformanceMetrics(
        execution_time=0.0,
        memory_usage=0,
        cache_hits=0,
        cache_misses=0,
        error_count=0,
        success_rate=0.0,
        pattern_stats={"matches": 0, "failures": 0}
    )
}

# Enhanced CSS patterns with proper typing and relationships
CSS_PATTERNS = {
    **COMMON_PATTERNS,  # Inherit common patterns
    
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "class_definition": ResilientPattern(
                name="class_definition",
                pattern="""
                (class_selector
                    name: (class_name) @syntax.class.name) @syntax.class.def
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="css",
                confidence=0.95,
                metadata={
                    "relationships": CSS_PATTERN_RELATIONSHIPS["class_definition"],
                    "metrics": CSS_PATTERN_METRICS["class_definition"],
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    )
                }
            ),
            
            "property": ResilientPattern(
                name="property",
                pattern="""
                (declaration
                    name: (property_name) @syntax.property.name
                    value: (property_value) @syntax.property.value) @syntax.property.def
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="css",
                confidence=0.95,
                metadata={
                    "relationships": CSS_PATTERN_RELATIONSHIPS["property"],
                    "metrics": CSS_PATTERN_METRICS["property"],
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
            "type": AdaptivePattern(
                name="type",
                pattern="""
                [
                    (id_selector) @semantics.type.id,
                    (type_selector) @semantics.type.element,
                    (universal_selector) @semantics.type.universal
                ]
                """,
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="css",
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
            
            "variable": AdaptivePattern(
                name="variable",
                pattern="""
                (custom_property_name) @semantics.variable.name
                """,
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="css",
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
            "import": ResilientPattern(
                name="import",
                pattern="""
                [
                    (import_statement
                        source: (string_value) @structure.import.path) @structure.import.def,
                    (media_statement
                        query: (media_query) @structure.import.query) @structure.import.def
                ]
                """,
                category=PatternCategory.STRUCTURE,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="css",
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
            
            "media_query": ResilientPattern(
                name="media_query",
                pattern="""
                (media_statement
                    query: (media_query) @structure.media.query
                    body: (block) @structure.media.body) @structure.media.def
                """,
                category=PatternCategory.STRUCTURE,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="css",
                confidence=0.95,
                metadata={
                    "relationships": CSS_PATTERN_RELATIONSHIPS["media_query"],
                    "metrics": CSS_PATTERN_METRICS["media_query"],
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
            "comment": AdaptivePattern(
                name="comment",
                pattern="""
                [
                    (comment) @documentation.comment
                ]
                """,
                category=PatternCategory.DOCUMENTATION,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="css",
                confidence=0.9,
                metadata={
                    "relationships": [
                        PatternRelationship(
                            source_pattern="comment",
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
    """Create pattern context for CSS files."""
    return PatternContext(
        code_structure=code_structure,
        language_stats={"language": "css", "version": "3"},
        project_patterns=[],
        file_location=file_path,
        dependencies=set(),
        recent_changes=[],
        scope_level="global",
        allows_nesting=True,
        relevant_patterns=list(CSS_PATTERNS.keys())
    )

def get_css_pattern_relationships(pattern_name: str) -> List[PatternRelationship]:
    """Get relationships for a specific pattern."""
    return CSS_PATTERN_RELATIONSHIPS.get(pattern_name, [])

def update_css_pattern_metrics(pattern_name: str, metrics: Dict[str, Any]) -> None:
    """Update performance metrics for a pattern."""
    if pattern_name in CSS_PATTERN_METRICS:
        pattern_metrics = CSS_PATTERN_METRICS[pattern_name]
        pattern_metrics.execution_time = metrics.get("execution_time", 0.0)
        pattern_metrics.memory_usage = metrics.get("memory_usage", 0)
        pattern_metrics.cache_hits = metrics.get("cache_hits", 0)
        pattern_metrics.cache_misses = metrics.get("cache_misses", 0)
        pattern_metrics.error_count = metrics.get("error_count", 0)
        
        total = pattern_metrics.cache_hits + pattern_metrics.cache_misses
        if total > 0:
            pattern_metrics.success_rate = pattern_metrics.cache_hits / total

def get_css_pattern_match_result(
    pattern_name: str,
    matches: List[Dict[str, Any]],
    context: PatternContext
) -> PatternMatchResult:
    """Create a pattern match result with relationships and metrics."""
    return PatternMatchResult(
        pattern_name=pattern_name,
        matches=matches,
        context=context,
        relationships=get_css_pattern_relationships(pattern_name),
        performance=CSS_PATTERN_METRICS.get(pattern_name, PatternPerformanceMetrics()),
        validation=PatternValidationResult(is_valid=True),
        metadata={"language": "css"}
    )

# Export public interfaces
__all__ = [
    'CSS_PATTERNS',
    'CSS_PATTERN_RELATIONSHIPS',
    'CSS_PATTERN_METRICS',
    'create_pattern_context',
    'get_css_pattern_relationships',
    'update_css_pattern_metrics',
    'get_css_pattern_match_result'
] 