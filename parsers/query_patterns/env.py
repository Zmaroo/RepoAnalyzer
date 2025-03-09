"""Environment file patterns with enhanced type system and relationships.

This module provides environment file-specific patterns that integrate with the enhanced
pattern processing system, including proper typing, relationships, and context.
"""

from typing import Dict, Any, List, Optional, Match
from dataclasses import dataclass, field
from parsers.types import (
    PatternCategory, PatternPurpose, PatternType, PatternRelationType,
    PatternContext, PatternRelationship, PatternPerformanceMetrics,
    PatternValidationResult, PatternMatchResult, QueryPattern
)
from parsers.models import PATTERN_CATEGORIES
from .common import COMMON_PATTERNS
from .enhanced_patterns import AdaptivePattern, ResilientPattern

# Pattern relationships for environment files
ENV_PATTERN_RELATIONSHIPS = {
    "variable": [
        PatternRelationship(
            source_pattern="variable",
            target_pattern="comment",
            relationship_type=PatternRelationType.COMPLEMENTS,
            confidence=0.8,
            metadata={"documentation": True}
        ),
        PatternRelationship(
            source_pattern="variable",
            target_pattern="reference",
            relationship_type=PatternRelationType.USES,
            confidence=0.9,
            metadata={"variable_references": True}
        )
    ],
    "group": [
        PatternRelationship(
            source_pattern="group",
            target_pattern="variable",
            relationship_type=PatternRelationType.CONTAINS,
            confidence=0.95,
            metadata={"group_variables": True}
        ),
        PatternRelationship(
            source_pattern="group",
            target_pattern="comment",
            relationship_type=PatternRelationType.COMPLEMENTS,
            confidence=0.8,
            metadata={"documentation": True}
        )
    ]
}

# Performance metrics tracking for environment file patterns
ENV_PATTERN_METRICS = {
    "variable": PatternPerformanceMetrics(
        execution_time=0.0,
        memory_usage=0,
        cache_hits=0,
        cache_misses=0,
        error_count=0,
        success_rate=0.0,
        pattern_stats={"matches": 0, "failures": 0}
    ),
    "group": PatternPerformanceMetrics(
        execution_time=0.0,
        memory_usage=0,
        cache_hits=0,
        cache_misses=0,
        error_count=0,
        success_rate=0.0,
        pattern_stats={"matches": 0, "failures": 0}
    )
}

# Enhanced environment file patterns with proper typing and relationships
ENV_PATTERNS = {
    **COMMON_PATTERNS,  # Inherit common patterns
    
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "variable": ResilientPattern(
                name="variable",
                pattern=r'^([A-Za-z0-9_]+)=(.*)$',
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="env",
                confidence=0.95,
                metadata={
                    "relationships": ENV_PATTERN_RELATIONSHIPS["variable"],
                    "metrics": ENV_PATTERN_METRICS["variable"],
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    )
                }
            ),
            
            "export": ResilientPattern(
                name="export",
                pattern=r'^export\s+([A-Za-z0-9_]+)=(.*)$',
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="env",
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
            
            "unset": ResilientPattern(
                name="unset",
                pattern=r'^unset\s+([A-Za-z0-9_]+)\s*$',
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="env",
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
    },
    
    PatternCategory.STRUCTURE: {
        PatternPurpose.UNDERSTANDING: {
            "group": ResilientPattern(
                name="group",
                pattern=r'^#\s*\[(.*?)\]\s*$',
                category=PatternCategory.STRUCTURE,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="env",
                confidence=0.95,
                metadata={
                    "relationships": ENV_PATTERN_RELATIONSHIPS["group"],
                    "metrics": ENV_PATTERN_METRICS["group"],
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    )
                }
            ),
            
            "quoted_value": AdaptivePattern(
                name="quoted_value",
                pattern=r'^[A-Za-z_][A-Za-z0-9_]*\s*=\s*([\'"](.*)[\'"])$',
                category=PatternCategory.STRUCTURE,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="env",
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
            
            "multiline": AdaptivePattern(
                name="multiline",
                pattern=r'^[A-Za-z_][A-Za-z0-9_]*\s*=\s*`(.*)`$',
                category=PatternCategory.STRUCTURE,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="env",
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
                pattern=r'^#\s*(.*)$',
                category=PatternCategory.DOCUMENTATION,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="env",
                confidence=0.9,
                metadata={
                    "relationships": [
                        PatternRelationship(
                            source_pattern="comments",
                            target_pattern="variable",
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
            
            "section_comment": AdaptivePattern(
                name="section_comment",
                pattern=r'^#\s*={3,}\s*([^=]+?)\s*={3,}\s*$',
                category=PatternCategory.DOCUMENTATION,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="env",
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
            "url": AdaptivePattern(
                name="url",
                pattern=r'^([A-Za-z_][A-Za-z0-9_]*_URL)\s*=\s*([^#\n]+)',
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="env",
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
            
            "path": AdaptivePattern(
                name="path",
                pattern=r'^([A-Za-z_][A-Za-z0-9_]*_PATH)\s*=\s*([^#\n]+)',
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="env",
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
            
            "reference": AdaptivePattern(
                name="reference",
                pattern=r'\$\{([^}]+)\}',
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="env",
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
    """Create pattern context for environment files."""
    return PatternContext(
        code_structure=code_structure,
        language_stats={"language": "env"},
        project_patterns=[],
        file_location=file_path,
        dependencies=set(),
        recent_changes=[],
        scope_level="global",
        allows_nesting=True,
        relevant_patterns=list(ENV_PATTERNS.keys())
    )

def get_env_pattern_relationships(pattern_name: str) -> List[PatternRelationship]:
    """Get relationships for a specific pattern."""
    return ENV_PATTERN_RELATIONSHIPS.get(pattern_name, [])

def update_env_pattern_metrics(pattern_name: str, metrics: Dict[str, Any]) -> None:
    """Update performance metrics for a pattern."""
    if pattern_name in ENV_PATTERN_METRICS:
        pattern_metrics = ENV_PATTERN_METRICS[pattern_name]
        pattern_metrics.execution_time = metrics.get("execution_time", 0.0)
        pattern_metrics.memory_usage = metrics.get("memory_usage", 0)
        pattern_metrics.cache_hits = metrics.get("cache_hits", 0)
        pattern_metrics.cache_misses = metrics.get("cache_misses", 0)
        pattern_metrics.error_count = metrics.get("error_count", 0)
        
        total = pattern_metrics.cache_hits + pattern_metrics.cache_misses
        if total > 0:
            pattern_metrics.success_rate = pattern_metrics.cache_hits / total

def get_env_pattern_match_result(
    pattern_name: str,
    matches: List[Dict[str, Any]],
    context: PatternContext
) -> PatternMatchResult:
    """Create a pattern match result with relationships and metrics."""
    return PatternMatchResult(
        pattern_name=pattern_name,
        matches=matches,
        context=context,
        relationships=get_env_pattern_relationships(pattern_name),
        performance=ENV_PATTERN_METRICS.get(pattern_name, PatternPerformanceMetrics()),
        validation=PatternValidationResult(is_valid=True),
        metadata={"language": "env"}
    )

# Export public interfaces
__all__ = [
    'ENV_PATTERNS',
    'ENV_PATTERN_RELATIONSHIPS',
    'ENV_PATTERN_METRICS',
    'create_pattern_context',
    'get_env_pattern_relationships',
    'update_env_pattern_metrics',
    'get_env_pattern_match_result'
]

# Module identification
LANGUAGE = "env" 