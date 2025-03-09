"""Dockerfile-specific patterns with enhanced type system and relationships.

This module provides Dockerfile-specific patterns that integrate with the enhanced
pattern processing system, including proper typing, relationships, and context.
The module is named 'dockerfil' to avoid conflicts with 'dockerfile' while maintaining
alignment with tree-sitter-language-pack's 'dockerfile' grammar.
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

# Pattern relationships for Dockerfile
DOCKERFILE_PATTERN_RELATIONSHIPS = {
    "instruction": [
        PatternRelationship(
            source_pattern="instruction",
            target_pattern="variable",
            relationship_type=PatternRelationType.USES,
            confidence=0.9,
            metadata={"variables": True}
        ),
        PatternRelationship(
            source_pattern="instruction",
            target_pattern="comment",
            relationship_type=PatternRelationType.COMPLEMENTS,
            confidence=0.8,
            metadata={"documentation": True}
        )
    ],
    "base_image": [
        PatternRelationship(
            source_pattern="base_image",
            target_pattern="instruction",
            relationship_type=PatternRelationType.DEPENDS_ON,
            confidence=0.95,
            metadata={"from": True}
        )
    ],
    "expose": [
        PatternRelationship(
            source_pattern="expose",
            target_pattern="variable",
            relationship_type=PatternRelationType.USES,
            confidence=0.85,
            metadata={"port_vars": True}
        )
    ]
}

# Performance metrics tracking for Dockerfile patterns
DOCKERFILE_PATTERN_METRICS = {
    "instruction": PatternPerformanceMetrics(
        execution_time=0.0,
        memory_usage=0,
        cache_hits=0,
        cache_misses=0,
        error_count=0,
        success_rate=0.0,
        pattern_stats={"matches": 0, "failures": 0}
    ),
    "base_image": PatternPerformanceMetrics(
        execution_time=0.0,
        memory_usage=0,
        cache_hits=0,
        cache_misses=0,
        error_count=0,
        success_rate=0.0,
        pattern_stats={"matches": 0, "failures": 0}
    ),
    "expose": PatternPerformanceMetrics(
        execution_time=0.0,
        memory_usage=0,
        cache_hits=0,
        cache_misses=0,
        error_count=0,
        success_rate=0.0,
        pattern_stats={"matches": 0, "failures": 0}
    )
}

# Enhanced Dockerfile patterns with proper typing and relationships
DOCKERFILE_PATTERNS = {
    **COMMON_PATTERNS,  # Inherit common patterns
    
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "instruction": ResilientPattern(
                name="instruction",
                pattern="""
                [
                    (instruction
                        name: (identifier) @syntax.instruction.name
                        value: (_) @syntax.instruction.value) @syntax.instruction.def
                ]
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="dockerfile",
                confidence=0.95,
                metadata={
                    "relationships": DOCKERFILE_PATTERN_RELATIONSHIPS["instruction"],
                    "metrics": DOCKERFILE_PATTERN_METRICS["instruction"],
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    )
                }
            ),
            
            "base_image": ResilientPattern(
                name="base_image",
                pattern="""
                [
                    (from_instruction
                        image: (image_spec
                            name: (image_name) @syntax.image.name
                            tag: (image_tag)? @syntax.image.tag
                            digest: (image_digest)? @syntax.image.digest)
                        platform: (platform)? @syntax.image.platform
                        as: (image_alias)? @syntax.image.alias) @syntax.image.def
                ]
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="dockerfile",
                confidence=0.95,
                metadata={
                    "relationships": DOCKERFILE_PATTERN_RELATIONSHIPS["base_image"],
                    "metrics": DOCKERFILE_PATTERN_METRICS["base_image"],
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    )
                }
            ),
            
            "expose": ResilientPattern(
                name="expose",
                pattern="""
                [
                    (expose_instruction
                        ports: (port_list
                            (port) @syntax.port.value
                            (port_protocol)? @syntax.port.protocol)*) @syntax.expose.def
                ]
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="dockerfile",
                confidence=0.95,
                metadata={
                    "relationships": DOCKERFILE_PATTERN_RELATIONSHIPS["expose"],
                    "metrics": DOCKERFILE_PATTERN_METRICS["expose"],
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
                    (comment_line) @documentation.comment.line
                ]
                """,
                category=PatternCategory.DOCUMENTATION,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="dockerfile",
                confidence=0.9,
                metadata={
                    "relationships": [
                        PatternRelationship(
                            source_pattern="comments",
                            target_pattern="instruction",
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
    
    PatternCategory.SEMANTICS: {
        PatternPurpose.UNDERSTANDING: {
            "variable": AdaptivePattern(
                name="variable",
                pattern="""
                [
                    (expansion
                        name: (variable) @semantics.var.name
                        default: (default_value)? @semantics.var.default) @semantics.var.def
                ]
                """,
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="dockerfile",
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
    """Create pattern context for Dockerfile files."""
    return PatternContext(
        code_structure=code_structure,
        language_stats={"language": "dockerfile"},
        project_patterns=[],
        file_location=file_path,
        dependencies=set(),
        recent_changes=[],
        scope_level="global",
        allows_nesting=True,
        relevant_patterns=list(DOCKERFILE_PATTERNS.keys())
    )

def get_dockerfile_pattern_relationships(pattern_name: str) -> List[PatternRelationship]:
    """Get relationships for a specific pattern."""
    return DOCKERFILE_PATTERN_RELATIONSHIPS.get(pattern_name, [])

def update_dockerfile_pattern_metrics(pattern_name: str, metrics: Dict[str, Any]) -> None:
    """Update performance metrics for a pattern."""
    if pattern_name in DOCKERFILE_PATTERN_METRICS:
        pattern_metrics = DOCKERFILE_PATTERN_METRICS[pattern_name]
        pattern_metrics.execution_time = metrics.get("execution_time", 0.0)
        pattern_metrics.memory_usage = metrics.get("memory_usage", 0)
        pattern_metrics.cache_hits = metrics.get("cache_hits", 0)
        pattern_metrics.cache_misses = metrics.get("cache_misses", 0)
        pattern_metrics.error_count = metrics.get("error_count", 0)
        
        total = pattern_metrics.cache_hits + pattern_metrics.cache_misses
        if total > 0:
            pattern_metrics.success_rate = pattern_metrics.cache_hits / total

def get_dockerfile_pattern_match_result(
    pattern_name: str,
    matches: List[Dict[str, Any]],
    context: PatternContext
) -> PatternMatchResult:
    """Create a pattern match result with relationships and metrics."""
    return PatternMatchResult(
        pattern_name=pattern_name,
        matches=matches,
        context=context,
        relationships=get_dockerfile_pattern_relationships(pattern_name),
        performance=DOCKERFILE_PATTERN_METRICS.get(pattern_name, PatternPerformanceMetrics()),
        validation=PatternValidationResult(is_valid=True),
        metadata={"language": "dockerfile"}
    )

# Export public interfaces
__all__ = [
    'DOCKERFILE_PATTERNS',
    'DOCKERFILE_PATTERN_RELATIONSHIPS',
    'DOCKERFILE_PATTERN_METRICS',
    'create_pattern_context',
    'get_dockerfile_pattern_relationships',
    'update_dockerfile_pattern_metrics',
    'get_dockerfile_pattern_match_result'
]

# Module identification
LANGUAGE = "dockerfile" 