"""Gitignore-specific patterns with enhanced type system and relationships.

This module provides gitignore-specific patterns that integrate with the enhanced
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

# Pattern relationships for gitignore
GITIGNORE_PATTERN_RELATIONSHIPS = {
    "pattern": [
        PatternRelationship(
            source_pattern="pattern",
            target_pattern="comment",
            relationship_type=PatternRelationType.COMPLEMENTS,
            confidence=0.8,
            metadata={"documentation": True}
        ),
        PatternRelationship(
            source_pattern="pattern",
            target_pattern="section",
            relationship_type=PatternRelationType.BELONGS_TO,
            confidence=0.9,
            metadata={"section_patterns": True}
        )
    ],
    "section": [
        PatternRelationship(
            source_pattern="section",
            target_pattern="pattern",
            relationship_type=PatternRelationType.CONTAINS,
            confidence=0.95,
            metadata={"section_patterns": True}
        ),
        PatternRelationship(
            source_pattern="section",
            target_pattern="comment",
            relationship_type=PatternRelationType.COMPLEMENTS,
            confidence=0.8,
            metadata={"documentation": True}
        )
    ]
}

# Performance metrics tracking for gitignore patterns
GITIGNORE_PATTERN_METRICS = {
    "pattern": PatternPerformanceMetrics(
        execution_time=0.0,
        memory_usage=0,
        cache_hits=0,
        cache_misses=0,
        error_count=0,
        success_rate=0.0,
        pattern_stats={"matches": 0, "failures": 0}
    ),
    "section": PatternPerformanceMetrics(
        execution_time=0.0,
        memory_usage=0,
        cache_hits=0,
        cache_misses=0,
        error_count=0,
        success_rate=0.0,
        pattern_stats={"matches": 0, "failures": 0}
    )
}

# Enhanced gitignore patterns with proper typing and relationships
GITIGNORE_PATTERNS = {
    **COMMON_PATTERNS,  # Inherit common patterns
    
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "pattern": ResilientPattern(
                name="pattern",
                pattern="""
                [
                    (pattern) @syntax.pattern.def,
                    (negated_pattern) @syntax.pattern.negated,
                    (directory_pattern) @syntax.pattern.directory
                ]
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="gitignore",
                confidence=0.95,
                metadata={
                    "relationships": GITIGNORE_PATTERN_RELATIONSHIPS["pattern"],
                    "metrics": GITIGNORE_PATTERN_METRICS["pattern"],
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    )
                }
            ),
            
            "comment": AdaptivePattern(
                name="comment",
                pattern="(comment) @syntax.comment",
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="gitignore",
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
    
    PatternCategory.SEMANTICS: {
        PatternPurpose.UNDERSTANDING: {
            "section": ResilientPattern(
                name="section",
                pattern="(section_header) @semantics.section.header",
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="gitignore",
                confidence=0.95,
                metadata={
                    "relationships": GITIGNORE_PATTERN_RELATIONSHIPS["section"],
                    "metrics": GITIGNORE_PATTERN_METRICS["section"],
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
                    (blank_line) @semantics.expression.blank,
                    (pattern) @semantics.expression.pattern,
                    (negated_pattern) @semantics.expression.negated
                ]
                """,
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="gitignore",
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
                pattern="(comment) @documentation.comment",
                category=PatternCategory.DOCUMENTATION,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="gitignore",
                confidence=0.9,
                metadata={
                    "relationships": [
                        PatternRelationship(
                            source_pattern="comments",
                            target_pattern="pattern",
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
            "root": ResilientPattern(
                name="root",
                pattern="(root_gitignore) @structure.root",
                category=PatternCategory.STRUCTURE,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="gitignore",
                confidence=0.95,
                metadata={
                    "relationships": [],
                    "metrics": PatternPerformanceMetrics(),
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    )
                }
            ),
            
            "global": ResilientPattern(
                name="global",
                pattern="(global_gitignore) @structure.global",
                category=PatternCategory.STRUCTURE,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="gitignore",
                confidence=0.95,
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
    """Create pattern context for gitignore files."""
    return PatternContext(
        code_structure=code_structure,
        language_stats={"language": "gitignore"},
        project_patterns=[],
        file_location=file_path,
        dependencies=set(),
        recent_changes=[],
        scope_level="global",
        allows_nesting=True,
        relevant_patterns=list(GITIGNORE_PATTERNS.keys())
    )

def get_gitignore_pattern_relationships(pattern_name: str) -> List[PatternRelationship]:
    """Get relationships for a specific pattern."""
    return GITIGNORE_PATTERN_RELATIONSHIPS.get(pattern_name, [])

def update_gitignore_pattern_metrics(pattern_name: str, metrics: Dict[str, Any]) -> None:
    """Update performance metrics for a pattern."""
    if pattern_name in GITIGNORE_PATTERN_METRICS:
        pattern_metrics = GITIGNORE_PATTERN_METRICS[pattern_name]
        pattern_metrics.execution_time = metrics.get("execution_time", 0.0)
        pattern_metrics.memory_usage = metrics.get("memory_usage", 0)
        pattern_metrics.cache_hits = metrics.get("cache_hits", 0)
        pattern_metrics.cache_misses = metrics.get("cache_misses", 0)
        pattern_metrics.error_count = metrics.get("error_count", 0)
        
        total = pattern_metrics.cache_hits + pattern_metrics.cache_misses
        if total > 0:
            pattern_metrics.success_rate = pattern_metrics.cache_hits / total

def get_gitignore_pattern_match_result(
    pattern_name: str,
    matches: List[Dict[str, Any]],
    context: PatternContext
) -> PatternMatchResult:
    """Create a pattern match result with relationships and metrics."""
    return PatternMatchResult(
        pattern_name=pattern_name,
        matches=matches,
        context=context,
        relationships=get_gitignore_pattern_relationships(pattern_name),
        performance=GITIGNORE_PATTERN_METRICS.get(pattern_name, PatternPerformanceMetrics()),
        validation=PatternValidationResult(is_valid=True),
        metadata={"language": "gitignore"}
    )

# Export public interfaces
__all__ = [
    'GITIGNORE_PATTERNS',
    'GITIGNORE_PATTERN_RELATIONSHIPS',
    'GITIGNORE_PATTERN_METRICS',
    'create_pattern_context',
    'get_gitignore_pattern_relationships',
    'update_gitignore_pattern_metrics',
    'get_gitignore_pattern_match_result'
]

# Module identification
LANGUAGE = "gitignore" 