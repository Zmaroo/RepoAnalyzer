"""Elixir-specific patterns with enhanced type system and relationships.

This module provides Elixir-specific patterns that integrate with the enhanced
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

# Pattern relationships for Elixir
ELIXIR_PATTERN_RELATIONSHIPS = {
    "function": [
        PatternRelationship(
            source_pattern="function",
            target_pattern="module",
            relationship_type=PatternRelationType.BELONGS_TO,
            confidence=0.95,
            metadata={"module_function": True}
        ),
        PatternRelationship(
            source_pattern="function",
            target_pattern="comment",
            relationship_type=PatternRelationType.COMPLEMENTS,
            confidence=0.8,
            metadata={"documentation": True}
        )
    ],
    "module": [
        PatternRelationship(
            source_pattern="module",
            target_pattern="function",
            relationship_type=PatternRelationType.CONTAINS,
            confidence=0.95,
            metadata={"functions": True}
        ),
        PatternRelationship(
            source_pattern="module",
            target_pattern="behaviour",
            relationship_type=PatternRelationType.IMPLEMENTS,
            confidence=0.9,
            metadata={"behaviours": True}
        )
    ]
}

# Performance metrics tracking for Elixir patterns
ELIXIR_PATTERN_METRICS = {
    "function": PatternPerformanceMetrics(
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

# Enhanced Elixir patterns with proper typing and relationships
ELIXIR_PATTERNS = {
    **COMMON_PATTERNS,  # Inherit common patterns
    
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "function": ResilientPattern(
                name="function",
                pattern="""
                [
                    (stab_clause
                        left: (arguments
                            [
                                (identifier) @syntax.function.name
                                (binary_operator) @syntax.function.operator
                            ]) @syntax.function.params
                        right: (body) @syntax.function.body) @syntax.function.def,
                        
                    (call
                        target: (identifier) @syntax.macro.name
                        (#match? @syntax.macro.name "^(def|defp|defmacro|defmacrop)$")
                        arguments: (arguments
                            (identifier) @syntax.function.name
                            parameters: (_)? @syntax.function.params
                            body: (do_block)? @syntax.function.body)) @syntax.macro.def
                ]
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="elixir",
                confidence=0.95,
                metadata={
                    "relationships": ELIXIR_PATTERN_RELATIONSHIPS["function"],
                    "metrics": ELIXIR_PATTERN_METRICS["function"],
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    )
                }
            ),
            
            "module": ResilientPattern(
                name="module",
                pattern="""
                [
                    (call
                        target: (identifier) @semantics.module.keyword
                        (#match? @semantics.module.keyword "^(defmodule)$")
                        arguments: (arguments
                            (alias) @semantics.module.name
                            (do_block)? @semantics.module.body)) @semantics.module.def
                ]
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="elixir",
                confidence=0.95,
                metadata={
                    "relationships": ELIXIR_PATTERN_RELATIONSHIPS["module"],
                    "metrics": ELIXIR_PATTERN_METRICS["module"],
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
            "namespace": QueryPattern(
                pattern="""
                (block
                    (_)* @block.content) @namespace
                """,
                extract=lambda node: {
                    "type": "namespace",
                    "content": node["node"].text.decode('utf8')
                }
            )
        }
    },
    
    PatternCategory.SEMANTICS: {
        PatternPurpose.UNDERSTANDING: {
            "variable": AdaptivePattern(
                name="variable",
                pattern="""
                (string
                    quoted_content: (_)? @string.content
                    interpolation: (_)* @string.interpolation) @variable
                """,
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="elixir",
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
            "module": QueryPattern(
                pattern="""
                [
                    (call
                        target: (identifier) @semantics.module.keyword
                        (#match? @semantics.module.keyword "^(defmodule)$")
                        arguments: (arguments
                            (alias) @semantics.module.name
                            (do_block)? @semantics.module.body)) @semantics.module.def
                ]
                """,
                extract=lambda node: {
                    "name": node["captures"].get("semantics.module.name", {}).get("text", ""),
                    "type": "module"
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
                language_id="elixir",
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
    
    PatternCategory.LEARNING: {
        PatternPurpose.BEST_PRACTICES: {
            "naming_conventions": QueryPattern(
                pattern="""
                [
                    (call
                        target: (identifier) @naming.module.keyword
                        (#match? @naming.module.keyword "^(defmodule)$")
                        arguments: (arguments
                            (alias) @naming.module.name
                            (_)* @naming.module.rest)) @naming.module,
                    (call
                        target: (identifier) @naming.func.keyword
                        (#match? @naming.func.keyword "^(def|defp|defmacro|defmacrop)$")
                        arguments: (arguments
                            (identifier) @naming.func.name
                            (_)* @naming.func.rest)) @naming.func,
                    (call
                        target: (identifier) @naming.struct.keyword
                        (#match? @naming.struct.keyword "^(defstruct)$")
                        (_)* @naming.struct.fields) @naming.struct,
                    (call
                        target: (identifier) @naming.protocol.keyword
                        (#match? @naming.protocol.keyword "^(defprotocol)$")
                        arguments: (arguments
                            (alias) @naming.protocol.name
                            (_)* @naming.protocol.rest)) @naming.protocol
                ]
                """,
                extract=lambda node: {
                    "module_name": node["captures"].get("naming.module.name", {}).get("text", ""),
                    "function_name": node["captures"].get("naming.func.name", {}).get("text", ""),
                    "protocol_name": node["captures"].get("naming.protocol.name", {}).get("text", ""),
                    "uses_pascal_case_for_modules": bool(
                        name and name[0].isupper() and "_" not in name 
                        for name in [
                            node["captures"].get("naming.module.name", {}).get("text", ""),
                            node["captures"].get("naming.protocol.name", {}).get("text", "")
                        ] if name
                    ),
                    "uses_snake_case_for_functions": bool(
                        name and name[0].islower() and "_" in name and name == name.lower()
                        for name in [node["captures"].get("naming.func.name", {}).get("text", "")] 
                        if name
                    )
                }
            )
        },
        PatternPurpose.CODE_ORGANIZATION: {
            "module_organization": QueryPattern(
                pattern="""
                [
                    (call
                        target: (identifier) @org.module.keyword
                        (#match? @org.module.keyword "^(defmodule)$")
                        arguments: (arguments
                            (alias) @org.module.name
                            (do_block
                                (call
                                    target: (identifier) @org.use.keyword
                                    (#match? @org.use.keyword "^(use|import|alias|require)$")
                                    arguments: (arguments
                                        (_) @org.use.arg
                                        (_)* @org.use.opts)) @org.use)* @org.module.body)) @org.module,
                    (call
                        target: (identifier) @org.behaviour.keyword
                        (#match? @org.behaviour.keyword "^(@behaviour|@impl)$")
                        arguments: (arguments
                            (_) @org.behaviour.arg)) @org.behaviour
                ]
                """,
                extract=lambda node: {
                    "has_use_declarations": bool(node["captures"].get("org.use.keyword", {}).get("text") == "use"),
                    "has_import_declarations": bool(node["captures"].get("org.use.keyword", {}).get("text") == "import"),
                    "has_alias_declarations": bool(node["captures"].get("org.use.keyword", {}).get("text") == "alias"),
                    "has_require_declarations": bool(node["captures"].get("org.use.keyword", {}).get("text") == "require"),
                    "implements_behaviour": bool(node["captures"].get("org.behaviour.keyword", {}).get("text") == "@behaviour"),
                    "has_impl_annotation": bool(node["captures"].get("org.behaviour.keyword", {}).get("text") == "@impl")
                }
            )
        },
        PatternPurpose.FUNCTIONAL_PATTERNS: {
            "functional_patterns": QueryPattern(
                pattern="""
                [
                    (pipe_operator
                        left: (_) @fp.pipe.left
                        right: (_) @fp.pipe.right) @fp.pipe,
                    (call
                        target: (identifier) @fp.enum.module
                        (#match? @fp.enum.module "^(Enum|Stream)$")
                        arguments: (arguments
                            function: (identifier) @fp.enum.function
                            (_)* @fp.enum.args)) @fp.enum,
                    (call
                        target: (identifier) @fp.pattern.keyword
                        (#match? @fp.pattern.keyword "^(case|cond|with|for|if|unless)$")
                        arguments: (arguments
                            (_) @fp.pattern.expression
                            (do_block) @fp.pattern.block)) @fp.pattern,
                    (binary_operator
                        operator: (operator) @fp.capture.op
                        (#match? @fp.capture.op "^&$")
                        right: (_) @fp.capture.function) @fp.capture
                ]
                """,
                extract=lambda node: {
                    "uses_pipe_operator": bool(node["captures"].get("fp.pipe", {}).get("text", "")),
                    "uses_enum_functions": bool(node["captures"].get("fp.enum.module", {}).get("text", "")),
                    "enum_function": node["captures"].get("fp.enum.function", {}).get("text", ""),
                    "uses_pattern_matching": bool(node["captures"].get("fp.pattern.keyword", {}).get("text", "")),
                    "pattern_type": node["captures"].get("fp.pattern.keyword", {}).get("text", ""),
                    "uses_function_capture": bool(node["captures"].get("fp.capture.op", {}).get("text", "") == "&")
                }
            )
        },
        PatternPurpose.CONCURRENCY: {
            "concurrency_patterns": QueryPattern(
                pattern="""
                [
                    (call
                        target: (identifier) @concurrency.process.keyword
                        (#match? @concurrency.process.keyword "^(spawn|spawn_link|spawn_monitor)$")
                        arguments: (arguments
                            (_)* @concurrency.process.args)) @concurrency.process,
                    (call
                        target: (identifier) @concurrency.msg.keyword
                        (#match? @concurrency.msg.keyword "^(send|receive)$")
                        arguments: (arguments
                            (_)* @concurrency.msg.args)) @concurrency.msg,
                    (call
                        target: (identifier) @concurrency.genserver.keyword
                        (#match? @concurrency.genserver.keyword "^(GenServer\\.(start_link|call|cast))$")
                        arguments: (arguments
                            (_)* @concurrency.genserver.args)) @concurrency.genserver,
                    (call
                        target: (identifier) @concurrency.task.keyword
                        (#match? @concurrency.task.keyword "^(Task\\.(async|await|yield|start_link))$")
                        arguments: (arguments
                            (_)* @concurrency.task.args)) @concurrency.task
                ]
                """,
                extract=lambda node: {
                    "uses_spawn": bool(node["captures"].get("concurrency.process.keyword", {}).get("text", "") in ["spawn", "spawn_link", "spawn_monitor"]),
                    "uses_message_passing": bool(node["captures"].get("concurrency.msg.keyword", {}).get("text", "") in ["send", "receive"]),
                    "uses_genserver": bool(node["captures"].get("concurrency.genserver.keyword", {}).get("text", "")),
                    "uses_tasks": bool(node["captures"].get("concurrency.task.keyword", {}).get("text", "")),
                    "concurrency_paradigm": (
                        "genserver" if node["captures"].get("concurrency.genserver.keyword", {}).get("text", "") else
                        "task" if node["captures"].get("concurrency.task.keyword", {}).get("text", "") else
                        "process" if node["captures"].get("concurrency.process.keyword", {}).get("text", "") else
                        "message_passing" if node["captures"].get("concurrency.msg.keyword", {}).get("text", "") else
                        None
                    )
                }
            )
        }
    }
}

def create_pattern_context(file_path: str, code_structure: Dict[str, Any]) -> PatternContext:
    """Create pattern context for Elixir files."""
    return PatternContext(
        code_structure=code_structure,
        language_stats={"language": "elixir"},
        project_patterns=[],
        file_location=file_path,
        dependencies=set(),
        recent_changes=[],
        scope_level="global",
        allows_nesting=True,
        relevant_patterns=list(ELIXIR_PATTERNS.keys())
    )

def get_elixir_pattern_relationships(pattern_name: str) -> List[PatternRelationship]:
    """Get relationships for a specific pattern."""
    return ELIXIR_PATTERN_RELATIONSHIPS.get(pattern_name, [])

def update_elixir_pattern_metrics(pattern_name: str, metrics: Dict[str, Any]) -> None:
    """Update performance metrics for a pattern."""
    if pattern_name in ELIXIR_PATTERN_METRICS:
        pattern_metrics = ELIXIR_PATTERN_METRICS[pattern_name]
        pattern_metrics.execution_time = metrics.get("execution_time", 0.0)
        pattern_metrics.memory_usage = metrics.get("memory_usage", 0)
        pattern_metrics.cache_hits = metrics.get("cache_hits", 0)
        pattern_metrics.cache_misses = metrics.get("cache_misses", 0)
        pattern_metrics.error_count = metrics.get("error_count", 0)
        
        total = pattern_metrics.cache_hits + pattern_metrics.cache_misses
        if total > 0:
            pattern_metrics.success_rate = pattern_metrics.cache_hits / total

def get_elixir_pattern_match_result(
    pattern_name: str,
    matches: List[Dict[str, Any]],
    context: PatternContext
) -> PatternMatchResult:
    """Create a pattern match result with relationships and metrics."""
    return PatternMatchResult(
        pattern_name=pattern_name,
        matches=matches,
        context=context,
        relationships=get_elixir_pattern_relationships(pattern_name),
        performance=ELIXIR_PATTERN_METRICS.get(pattern_name, PatternPerformanceMetrics()),
        validation=PatternValidationResult(is_valid=True),
        metadata={"language": "elixir"}
    )

# Export public interfaces
__all__ = [
    'ELIXIR_PATTERNS',
    'ELIXIR_PATTERN_RELATIONSHIPS',
    'ELIXIR_PATTERN_METRICS',
    'create_pattern_context',
    'get_elixir_pattern_relationships',
    'update_elixir_pattern_metrics',
    'get_elixir_pattern_match_result'
]

# Module identification
LANGUAGE = "elixir" 