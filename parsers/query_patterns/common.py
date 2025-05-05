"""Common tree-sitter query patterns for RepoAnalyzer.

This module contains tree-sitter patterns that can be used across different languages.
These patterns focus on tree-sitter query language and require a tree-sitter parser.

The module provides:
- Core tree-sitter pattern processing functions
- Utilities for tree-sitter pattern validation
- Context creation for tree-sitter pattern matching
- Pattern learning capabilities for tree-sitter patterns

Examples:
    # Process a tree-sitter pattern against source code
    matches = await process_tree_sitter_pattern(
        pattern=pattern,
        source_code=source_code,
        context=pattern_context
    )
    
    # Validate a tree-sitter pattern
    validation = await validate_tree_sitter_pattern(
        pattern=pattern,
        context=pattern_context
    )
    
    # Create context for tree-sitter pattern processing
    context = await create_tree_sitter_context(
        file_path="path/to/file.py",
        code_structure=parsed_ast
    )
    
    # Learn tree-sitter patterns from a project
    learner = TreeSitterPatternLearner()
    await learner.initialize()
    learned_patterns = await learner.learn_from_repository("/path/to/repo")
"""

from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field
from parsers.types import (
    PatternCategory, PatternPurpose, PatternType, PatternRelationType,
    PatternContext, PatternRelationship, PatternPerformanceMetrics,
    PatternValidationResult, PatternMatchResult, QueryPattern,
    AICapability, AIContext, AIProcessingResult, InteractionType,
    ExtractedFeatures, FileType, ParserType
)
from parsers.models import PATTERN_CATEGORIES
from utils.error_handling import AsyncErrorBoundary, handle_async_errors, ProcessingError, ErrorSeverity
from utils.health_monitor import monitor_operation, global_health_monitor, ComponentStatus
from utils.request_cache import cached_in_request, get_current_request_cache
from utils.cache_analytics import get_cache_analytics
from utils.async_runner import submit_async_task, cleanup_tasks
from utils.logger import log
from utils.shutdown import register_shutdown_handler
import asyncio
from parsers.block_extractor import get_block_extractor
from parsers.feature_extractor import get_feature_extractor
from parsers.unified_parser import get_unified_parser
from parsers.base_parser import BaseParser
from parsers.tree_sitter_parser import get_tree_sitter_parser
from parsers.ai_pattern_processor import get_ai_pattern_processor
import time
from parsers.query_patterns.enhanced_patterns_custom import CrossProjectPatternLearner

# Common capabilities shared across languages
COMMON_CAPABILITIES = {
    AICapability.CODE_UNDERSTANDING,
    AICapability.CODE_GENERATION,
    AICapability.CODE_MODIFICATION,
    AICapability.CODE_REVIEW,
    AICapability.LEARNING
}

# Common pattern relationships
COMMON_PATTERN_RELATIONSHIPS = {
    "function": [
        PatternRelationship(
            source_pattern="function",
            target_pattern="comment",
            relationship_type=PatternRelationType.USES,
            confidence=0.8,
            metadata={"documentation": True}
        )
    ],
    "class": [
        PatternRelationship(
            source_pattern="class",
            target_pattern="method",
            relationship_type=PatternRelationType.USES,
            confidence=0.95,
            metadata={"class_members": True}
        ),
        PatternRelationship(
            source_pattern="class",
            target_pattern="comment",
            relationship_type=PatternRelationType.USES,
            confidence=0.8,
            metadata={"documentation": True}
        )
    ],
    "module": [
        PatternRelationship(
            source_pattern="module",
            target_pattern="import",
            relationship_type=PatternRelationType.USES,
            confidence=0.95,
            metadata={"module_system": True}
        ),
        PatternRelationship(
            source_pattern="module",
            target_pattern="export",
            relationship_type=PatternRelationType.USES,
            confidence=0.95,
            metadata={"module_system": True}
        )
    ]
}

# Performance metrics for common patterns
COMMON_PATTERN_METRICS = {
    "function": PatternPerformanceMetrics(
        execution_time=0.0,
        memory_usage=0,
        cache_hits=0,
        cache_misses=0,
        error_count=0,
        success_rate=0.0,
        pattern_stats={"matches": 0, "failures": 0}
    ),
    "class": PatternPerformanceMetrics(
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

# Enhanced common patterns with proper typing and relationships
COMMON_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "function": QueryPattern(
                name="function",
                # Tree-sitter pattern
                pattern="""
                [
                    (function_definition
                      name: (identifier) @syntax.function.name
                      parameters: (parameters) @syntax.function.params
                      body: (block) @syntax.function.body) @syntax.function.def,
                    (method_definition
                      name: (identifier) @syntax.method.name
                      parameters: (parameters) @syntax.method.params
                      body: (block) @syntax.method.body) @syntax.method.def
                ]
                """,
                # Regex pattern for custom parsers
                regex_pattern=r"(?:function|def)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]*)\)",
                extract=lambda m: {
                    "type": "function",
                    "name": (
                        # For tree-sitter
                        m["captures"].get("syntax.function.name", {}).get("text", "") or
                        m["captures"].get("syntax.method.name", {}).get("text", "")
                        if isinstance(m, dict) and "captures" in m
                        # For regex
                        else m.group(1) if hasattr(m, "group") else ""
                    ),
                    "parameters": (
                        # For tree-sitter
                        m["captures"].get("syntax.function.params", {}).get("text", "") or
                        m["captures"].get("syntax.method.params", {}).get("text", "")
                        if isinstance(m, dict) and "captures" in m
                        # For regex
                        else m.group(2) if hasattr(m, "group") else ""
                    ),
                    "line": (
                        # For tree-sitter
                        m["captures"].get("syntax.function.def", {}).get("start_point", [0])[0] or
                        m["captures"].get("syntax.method.def", {}).get("start_point", [0])[0]
                        if isinstance(m, dict) and "captures" in m
                        # For regex
                        else m.string.count('\n', 0, m.start()) + 1 if hasattr(m, "start") else 0
                    )
                },
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="*",  # Wildcard for all languages
                confidence=0.95,
                metadata={
                    "relationships": COMMON_PATTERN_RELATIONSHIPS["function"],
                    "metrics": COMMON_PATTERN_METRICS["function"],
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    ),
                    # Block extraction metadata
                    "block_type": "function",
                    "contains_blocks": ["expression", "statement", "condition"],
                    "is_nestable": False,
                    "extraction_priority": 10,
                    # AI learning support
                    "adaptable": True,
                    "confidence_threshold": 0.7,
                    "learning_examples": [
                        "function example(param1, param2) {",
                        "def example(param1, param2):",
                        "public void example(Type param1, Type param2) {"
                    ],
                    # Export format compatibility
                    "description": "Matches function and method definitions across languages",
                    "examples": [
                        "function add(a, b) { return a + b; }",
                        "def add(a, b): return a + b"
                    ],
                    "version": "1.0",
                    "tags": ["function", "method", "routine"]
                },
                # Test cases for validation
                test_cases=[
                    {
                        "input": "function example(a, b) { return a + b; }",
                        "expected": {
                            "name": "example",
                            "parameters": "a, b"
                        }
                    },
                    {
                        "input": "def example(a, b): return a + b",
                        "expected": {
                            "name": "example",
                            "parameters": "a, b"
                        }
                    }
                ]
            ),
            
            "class": QueryPattern(
                name="class",
                # Tree-sitter pattern
                pattern="""
                [
                    (class_definition
                      name: (identifier) @syntax.class.name
                      superclass: (expression)? @syntax.class.superclass
                      body: (block) @syntax.class.body) @syntax.class.def,
                    (class_declaration
                      name: (identifier) @syntax.class.decl.name
                      extends: (class_heritage)? @syntax.class.decl.extends
                      body: (class_body) @syntax.class.decl.body) @syntax.class.decl.def
                ]
                """,
                # Regex pattern for custom parsers
                regex_pattern=r"class\s+([A-Za-z_][A-Za-z0-9_]*)\s*(?:extends|:)\s*([A-Za-z_][A-Za-z0-9_,\s]*)?",
                extract=lambda m: {
                    "type": "class",
                    "name": (
                        # For tree-sitter
                        m["captures"].get("syntax.class.name", {}).get("text", "") or
                        m["captures"].get("syntax.class.decl.name", {}).get("text", "")
                        if isinstance(m, dict) and "captures" in m
                        # For regex
                        else m.group(1) if hasattr(m, "group") else ""
                    ),
                    "superclass": (
                        # For tree-sitter
                        m["captures"].get("syntax.class.superclass", {}).get("text", "") or
                        m["captures"].get("syntax.class.decl.extends", {}).get("text", "")
                        if isinstance(m, dict) and "captures" in m
                        # For regex
                        else m.group(2) if hasattr(m, "group") and m.groups() > 1 else ""
                    ),
                    "line": (
                        # For tree-sitter
                        m["captures"].get("syntax.class.def", {}).get("start_point", [0])[0] or
                        m["captures"].get("syntax.class.decl.def", {}).get("start_point", [0])[0]
                        if isinstance(m, dict) and "captures" in m
                        # For regex
                        else m.string.count('\n', 0, m.start()) + 1 if hasattr(m, "start") else 0
                    )
                },
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="*",
                confidence=0.95,
                metadata={
                    "relationships": COMMON_PATTERN_RELATIONSHIPS["class"],
                    "metrics": COMMON_PATTERN_METRICS["class"],
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    ),
                    # Block extraction metadata
                    "block_type": "class",
                    "contains_blocks": ["function", "method", "field", "constructor", "property"],
                    "is_nestable": True,
                    "extraction_priority": 20,
                    # AI learning support
                    "adaptable": True,
                    "confidence_threshold": 0.8,
                    "learning_examples": [
                        "class Example {",
                        "class Example extends Base {",
                        "class Example(BaseClass):"
                    ],
                    # Export format compatibility
                    "description": "Matches class definitions across languages",
                    "examples": [
                        "class Rectangle { constructor(width, height) { this.width = width; } }",
                        "class Circle(Shape): def __init__(self, radius): self.radius = radius"
                    ],
                    "version": "1.0",
                    "tags": ["class", "object-oriented", "type"]
                },
                # Test cases for validation
                test_cases=[
                    {
                        "input": "class Rectangle { constructor(width, height) { this.width = width; } }",
                        "expected": {
                            "name": "Rectangle",
                            "superclass": ""
                        }
                    },
                    {
                        "input": "class Circle extends Shape { }",
                        "expected": {
                            "name": "Circle",
                            "superclass": "Shape"
                        }
                    },
                    {
                        "input": "class Person(Human):",
                        "expected": {
                            "name": "Person",
                            "superclass": "Human"
                        }
                    }
                ]
            ),
            
            "module": QueryPattern(
                name="module",
                # Tree-sitter pattern
                pattern="""
                [
                    (module) @syntax.module.def,
                    (program) @syntax.module.program
                ]
                """,
                # Regex pattern for custom parsers - matching file-level modules
                regex_pattern=r"(?m)^(?:package|module|namespace)\s+([A-Za-z_][A-Za-z0-9_\.]*)",
                extract=lambda m: {
                    "type": "module",
                    "name": (
                        # For tree-sitter - get the filename or path as module name
                        m["file_path"].split("/")[-1].split(".")[0]
                        if isinstance(m, dict) and "file_path" in m
                        # For regex
                        else m.group(1) if hasattr(m, "group") else ""
                    ),
                    "scope": "file",
                    "line": (
                        # For tree-sitter
                        m["captures"].get("syntax.module.def", {}).get("start_point", [0])[0] or
                        m["captures"].get("syntax.module.program", {}).get("start_point", [0])[0]
                        if isinstance(m, dict) and "captures" in m
                        # For regex
                        else m.string.count('\n', 0, m.start()) + 1 if hasattr(m, "start") else 0
                    )
                },
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="*",
                confidence=0.95,
                metadata={
                    "relationships": COMMON_PATTERN_RELATIONSHIPS["module"],
                    "metrics": COMMON_PATTERN_METRICS["module"],
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    ),
                    # Block extraction metadata
                    "block_type": "module",
                    "contains_blocks": ["function", "class", "import", "export", "namespace"],
                    "is_nestable": True,
                    "extraction_priority": 30,
                    # AI learning support
                    "adaptable": True,
                    "confidence_threshold": 0.7,
                    "learning_examples": [
                        "package com.example",
                        "module MyModule {",
                        "namespace MyNamespace {"
                    ],
                    # Export format compatibility
                    "description": "Matches module definitions and file-level scopes across languages",
                    "examples": [
                        "package com.example.project;",
                        "module MyModule { export function example() {} }"
                    ],
                    "version": "1.0",
                    "tags": ["module", "namespace", "package", "scope"]
                },
                # Test cases for validation
                test_cases=[
                    {
                        "input": "package com.example.project;\n\npublic class Example {}",
                        "expected": {
                            "name": "com.example.project",
                            "scope": "file"
                        }
                    },
                    {
                        "input": "module MyModule {\n  export const value = 10;\n}",
                        "expected": {
                            "name": "MyModule",
                            "scope": "file"
                        }
                    }
                ]
            )
        }
    },

    PatternCategory.SEMANTICS: {
        PatternPurpose.UNDERSTANDING: {
            "variable": QueryPattern(
                name="variable",
                # Tree-sitter pattern
                pattern="""
                [
                    (variable_declaration
                      name: (identifier) @semantics.variable.name
                      value: (_)? @semantics.variable.value) @semantics.variable.def,
                    (variable_declarator
                      name: (identifier) @semantics.var.name
                      value: (_)? @semantics.var.value) @semantics.var.def,
                    (assignment_expression
                      left: (identifier) @semantics.assign.name
                      right: (_) @semantics.assign.value) @semantics.assign.def
                ]
                """,
                # Regex pattern for custom parsers
                regex_pattern=r"(?:var|let|const|int|float|double|string|char|boolean)\s+([A-Za-z_][A-Za-z0-9_]*)\s*(?:=\s*([^;]+))?",
                extract=lambda m: {
                    "type": "variable",
                    "name": (
                        # For tree-sitter
                        m["captures"].get("semantics.variable.name", {}).get("text", "") or
                        m["captures"].get("semantics.var.name", {}).get("text", "") or
                        m["captures"].get("semantics.assign.name", {}).get("text", "")
                        if isinstance(m, dict) and "captures" in m
                        # For regex
                        else m.group(1) if hasattr(m, "group") else ""
                    ),
                    "value": (
                        # For tree-sitter
                        m["captures"].get("semantics.variable.value", {}).get("text", "") or
                        m["captures"].get("semantics.var.value", {}).get("text", "") or
                        m["captures"].get("semantics.assign.value", {}).get("text", "")
                        if isinstance(m, dict) and "captures" in m
                        # For regex
                        else m.group(2) if hasattr(m, "group") and m.groups() > 1 else ""
                    ),
                    "line": (
                        # For tree-sitter
                        m["captures"].get("semantics.variable.def", {}).get("start_point", [0])[0] or
                        m["captures"].get("semantics.var.def", {}).get("start_point", [0])[0] or
                        m["captures"].get("semantics.assign.def", {}).get("start_point", [0])[0]
                        if isinstance(m, dict) and "captures" in m
                        # For regex
                        else m.string.count('\n', 0, m.start()) + 1 if hasattr(m, "start") else 0
                    )
                },
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="*",
                confidence=0.9,
                metadata={
                    "relationships": [],
                    "metrics": PatternPerformanceMetrics(),
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    ),
                    # Block extraction metadata
                    "block_type": "variable",
                    "contains_blocks": [],
                    "is_nestable": False,
                    "extraction_priority": 5,
                    # AI learning support
                    "adaptable": True,
                    "confidence_threshold": 0.7,
                    "learning_examples": [
                        "var x = 10;",
                        "let name = 'example';",
                        "const PI = 3.14;",
                        "int count = 0;"
                    ],
                    # Export format compatibility
                    "description": "Matches variable declarations and assignments across languages",
                    "examples": [
                        "var x = 10;",
                        "let message = 'Hello';",
                        "const PI = 3.14159;"
                    ],
                    "version": "1.0",
                    "tags": ["variable", "assignment", "declaration"]
                },
                # Test cases for validation
                test_cases=[
                    {
                        "input": "var count = 10;",
                        "expected": {
                            "name": "count",
                            "value": "10"
                        }
                    },
                    {
                        "input": "const PI = 3.14;",
                        "expected": {
                            "name": "PI",
                            "value": "3.14"
                        }
                    },
                    {
                        "input": "let name;",
                        "expected": {
                            "name": "name",
                            "value": ""
                        }
                    }
                ]
            ),
            
            "literal": QueryPattern(
                name="literal",
                # Tree-sitter pattern
                pattern="""
                [
                    (string_literal) @semantics.literal.string,
                    (number_literal) @semantics.literal.number,
                    (boolean_literal) @semantics.literal.boolean,
                    (null_literal) @semantics.literal.null
                ]
                """,
                regex_pattern=r'(?:"([^"\\]*(?:\\.[^"\\]*)*)"|\'([^\'\\]*(?:\\.[^\'\\]*)*)\'|(\d+(?:\.\d+)?)|true|false|null)',
                extract=lambda m: {
                    "type": "literal",
                    "value": (
                        # For tree-sitter
                        m["captures"].get("semantics.literal.string", {}).get("text", "") or
                        m["captures"].get("semantics.literal.number", {}).get("text", "") or
                        m["captures"].get("semantics.literal.boolean", {}).get("text", "") or
                        m["captures"].get("semantics.literal.null", {}).get("text", "")
                        if isinstance(m, dict) and "captures" in m
                        # For regex
                        else m.group(0) if hasattr(m, "group") else ""
                    ),
                    "kind": (
                        # For tree-sitter
                        "string" if "semantics.literal.string" in m.get("captures", {}) else
                        "number" if "semantics.literal.number" in m.get("captures", {}) else
                        "boolean" if "semantics.literal.boolean" in m.get("captures", {}) else
                        "null" if "semantics.literal.null" in m.get("captures", {}) else
                        "unknown"
                        if isinstance(m, dict) and "captures" in m
                        # For regex
                        else ("string" if m.group(0).startswith('"') or m.group(0).startswith("'") else
                              "number" if m.group(0).replace(".", "", 1).isdigit() else
                              "boolean" if m.group(0) in ("true", "false") else
                              "null" if m.group(0) == "null" else
                              "unknown")
                        if hasattr(m, "group") else "unknown"
                    ),
                    "line": (
                        # For tree-sitter
                        m["captures"].get("semantics.literal.string", {}).get("start_point", [0])[0] or
                        m["captures"].get("semantics.literal.number", {}).get("start_point", [0])[0] or
                        m["captures"].get("semantics.literal.boolean", {}).get("start_point", [0])[0] or
                        m["captures"].get("semantics.literal.null", {}).get("start_point", [0])[0]
                        if isinstance(m, dict) and "captures" in m
                        # For regex
                        else m.string.count('\n', 0, m.start()) + 1 if hasattr(m, "start") else 0
                    )
                },
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="*",
                confidence=0.9,
                metadata={
                    "relationships": [],
                    "metrics": PatternPerformanceMetrics(),
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    ),
                    "block_type": "literal",
                    "contains_blocks": [],
                    "is_nestable": False,
                    "extraction_priority": 2,
                    "adaptable": True,
                    "confidence_threshold": 0.8,
                    "learning_examples": [
                        '"This is a string"',
                        "'Another string'",
                        "123.45",
                        "true",
                        "false",
                        "null"
                    ],
                    "description": "Matches literal values across languages",
                    "examples": [
                        '"Example string"',
                        "42",
                        "3.14159",
                        "true",
                        "null"
                    ],
                    "version": "1.0",
                    "tags": ["literal", "string", "number", "boolean", "null"]
                },
                test_cases=[
                    {
                        "input": '"Hello world"',
                        "expected": {
                            "kind": "string",
                            "value": '"Hello world"'
                        }
                    },
                    {
                        "input": "42",
                        "expected": {
                            "kind": "number",
                            "value": "42"
                        }
                    },
                    {
                        "input": "true",
                        "expected": {
                            "kind": "boolean",
                            "value": "true"
                        }
                    },
                    {
                        "input": "null",
                        "expected": {
                            "kind": "null",
                            "value": "null"
                        }
                    }
                ]
            ),
            
            "expression": QueryPattern(
                name="expression",
                pattern="""
                [
                    (binary_expression) @semantics.expression.binary,
                    (unary_expression) @semantics.expression.unary
                ]
                """,
                # Add regex pattern for custom parsers - match basic expressions
                regex_pattern=r"(?:[^\s\w](?:\s*\w+\s*)[^\w\s](?:\s*\w+)|(?:!|~)(?:\s*\w+))",
                # Add extraction function to handle both tree-sitter and regex
                extract=lambda m: {
                    "type": (
                        # For tree-sitter
                        "binary_expression" if "semantics.expression.binary" in m.get("captures", {}) else
                        "unary_expression" if "semantics.expression.unary" in m.get("captures", {}) else
                        "expression"
                        if isinstance(m, dict) and "captures" in m
                        # For regex - determine expression type from the match
                        else "unary_expression" if m.group(0).strip().startswith(("!", "~")) else "binary_expression"
                        if hasattr(m, "group") else "expression"
                    ),
                    "value": (
                        # For tree-sitter
                        m["captures"].get("semantics.expression.binary", {}).get("text", "") or
                        m["captures"].get("semantics.expression.unary", {}).get("text", "")
                        if isinstance(m, dict) and "captures" in m
                        # For regex
                        else m.group(0) if hasattr(m, "group") else ""
                    ),
                    "line": (
                        # For tree-sitter
                        m["captures"].get("semantics.expression.binary", {}).get("start_point", [0])[0] or
                        m["captures"].get("semantics.expression.unary", {}).get("start_point", [0])[0]
                        if isinstance(m, dict) and "captures" in m
                        # For regex
                        else m.string.count('\n', 0, m.start()) + 1 if hasattr(m, "start") else 0
                    )
                },
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="*",
                confidence=0.9,
                metadata={
                    "relationships": [],
                    "metrics": PatternPerformanceMetrics(),
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    ),
                    # Block extraction metadata
                    "block_type": "expression",
                    "contains_blocks": [],
                    "is_nestable": False,
                    "extraction_priority": 7,
                    # AI learning support
                    "adaptable": True,
                    "confidence_threshold": 0.8,
                    "learning_examples": [
                        "a + b",
                        "x * y",
                        "!flag"
                    ],
                    # Export format compatibility
                    "description": "Matches expressions across languages",
                    "examples": [
                        "a + b",
                        "x * y",
                        "!flag"
                    ],
                    "version": "1.0",
                    "tags": ["expression", "binary", "unary"]
                },
                # Test cases for validation
                test_cases=[
                    {
                        "input": "a + b",
                        "expected": {
                            "type": "binary_expression"
                        }
                    },
                    {
                        "input": "x * y",
                        "expected": {
                            "type": "binary_expression"
                        }
                    },
                    {
                        "input": "!flag",
                        "expected": {
                            "type": "unary_expression"
                        }
                    }
                ]
            )
        }
    },

    PatternCategory.STRUCTURE: {
        PatternPurpose.UNDERSTANDING: {
            "import": QueryPattern(
                name="import",
                # Tree-sitter pattern
                pattern="""
                [
                    (import_statement
                      path: (string) @structure.import.path) @structure.import.stmt,
                    (import_declaration
                      source: (string) @structure.import.decl.source
                      clause: (import_clause) @structure.import.decl.clause) @structure.import.decl
                ]
                """,
                # Regex pattern for custom parsers - match various import syntaxes
                regex_pattern=r'(?:import\s+(?:[*{}\s\w,]+\s+from\s+)?["\']([^"\']+)["\']|require\s*\(\s*["\']([^"\']+)["\']\s*\)|#include\s*[<"]([^>"]+)[>"])',
                extract=lambda m: {
                    "type": "import",
                    "module": (
                        # For tree-sitter
                        m["captures"].get("structure.import.path", {}).get("text", "") or
                        m["captures"].get("structure.import.decl.source", {}).get("text", "")
                        if isinstance(m, dict) and "captures" in m
                        # For regex - get first non-empty group
                        else next((g for g in [m.group(1), m.group(2), m.group(3)] if g is not None), "")
                        if hasattr(m, "group") else ""
                    ),
                    "style": (
                        # For tree-sitter - determine style by present nodes
                        "import" if "structure.import.stmt" in m.get("captures", {}) else
                        "es6" if "structure.import.decl" in m.get("captures", {}) else
                        "unknown"
                        if isinstance(m, dict) and "captures" in m
                        # For regex - guess style from match group
                        else ("es6" if m.group(1) is not None else
                              "commonjs" if m.group(2) is not None else
                              "c-style" if m.group(3) is not None else
                              "unknown")
                        if hasattr(m, "group") else "unknown"
                    ),
                    "line": (
                        # For tree-sitter
                        m["captures"].get("structure.import.stmt", {}).get("start_point", [0])[0] or
                        m["captures"].get("structure.import.decl", {}).get("start_point", [0])[0]
                        if isinstance(m, dict) and "captures" in m
                        # For regex
                        else m.string.count('\n', 0, m.start()) + 1 if hasattr(m, "start") else 0
                    )
                },
                category=PatternCategory.STRUCTURE,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="*",
                confidence=0.9,
                metadata={
                    "relationships": [],
                    "metrics": PatternPerformanceMetrics(),
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    ),
                    # Block extraction metadata
                    "block_type": "import",
                    "contains_blocks": [],
                    "is_nestable": False,
                    "extraction_priority": 8,
                    # AI learning support
                    "adaptable": True,
                    "confidence_threshold": 0.8,
                    "learning_examples": [
                        "import { Component } from 'react';",
                        "import pandas as pd",
                        "const fs = require('fs');",
                        "#include <stdio.h>"
                    ],
                    # Export format compatibility
                    "description": "Matches import statements across languages",
                    "examples": [
                        "import { useState } from 'react';",
                        "import os",
                        "const path = require('path');",
                        "#include <iostream>"
                    ],
                    "version": "1.0",
                    "tags": ["import", "require", "include", "module", "dependency"]
                },
                # Test cases for validation
                test_cases=[
                    {
                        "input": "import { Component } from 'react';",
                        "expected": {
                            "module": "react",
                            "style": "es6"
                        }
                    },
                    {
                        "input": "const fs = require('fs');",
                        "expected": {
                            "module": "fs",
                            "style": "commonjs"
                        }
                    },
                    {
                        "input": "#include <stdio.h>",
                        "expected": {
                            "module": "stdio.h",
                            "style": "c-style"
                        }
                    }
                ]
            ),
            
            "export": QueryPattern(
                name="export",
                # Tree-sitter pattern
                pattern="""
                [
                    (export_statement
                      declaration: (_) @structure.export.declaration) @structure.export.stmt,
                    (export_declaration
                      declaration: (_) @structure.export.decl.declaration) @structure.export.decl
                ]
                """,
                # Regex pattern for custom parsers - match various export syntaxes
                regex_pattern=r'export\s+(?:default\s+)?(?:const|let|var|function|class|interface)?\s*([A-Za-z_$][A-Za-z0-9_$]*)|module\.exports\s*=\s*([A-Za-z_$][A-Za-z0-9_$]*)',
                extract=lambda m: {
                    "type": "export",
                    "name": (
                        # For tree-sitter - extract name from declaration if possible
                        # This is a simplified version and may need enhancements based on language specifics
                        m["captures"].get("structure.export.declaration", {}).get("text", "").split(" ")[0] or
                        m["captures"].get("structure.export.decl.declaration", {}).get("text", "").split(" ")[0]
                        if isinstance(m, dict) and "captures" in m
                        # For regex - get first non-empty group
                        else next((g for g in [m.group(1), m.group(2)] if g is not None), "")
                        if hasattr(m, "group") else ""
                    ),
                    "style": (
                        # For tree-sitter - determine style by present nodes
                        "es6" if "structure.export.stmt" in m.get("captures", {}) or "structure.export.decl" in m.get("captures", {}) else
                        "unknown"
                        if isinstance(m, dict) and "captures" in m
                        # For regex - guess style from match pattern
                        else "es6" if m.group(1) is not None else
                             "commonjs" if m.group(2) is not None else
                             "unknown"
                        if hasattr(m, "group") else "unknown"
                    ),
                    "line": (
                        # For tree-sitter
                        m["captures"].get("structure.export.stmt", {}).get("start_point", [0])[0] or
                        m["captures"].get("structure.export.decl", {}).get("start_point", [0])[0]
                        if isinstance(m, dict) and "captures" in m
                        # For regex
                        else m.string.count('\n', 0, m.start()) + 1 if hasattr(m, "start") else 0
                    )
                },
                category=PatternCategory.STRUCTURE,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="*",
                confidence=0.9,
                metadata={
                    "relationships": [],
                    "metrics": PatternPerformanceMetrics(),
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    ),
                    # Block extraction metadata
                    "block_type": "export",
                    "contains_blocks": [],
                    "is_nestable": False,
                    "extraction_priority": 8,
                    # AI learning support
                    "adaptable": True,
                    "confidence_threshold": 0.8,
                    "learning_examples": [
                        "export const value = 42;",
                        "export default class Component {}",
                        "module.exports = Router;"
                    ],
                    # Export format compatibility
                    "description": "Matches export statements across languages",
                    "examples": [
                        "export function sum(a, b) { return a + b; }",
                        "export default App;",
                        "module.exports = { sum, multiply };"
                    ],
                    "version": "1.0",
                    "tags": ["export", "module.exports", "expose"]
                },
                # Test cases for validation
                test_cases=[
                    {
                        "input": "export const value = 42;",
                        "expected": {
                            "style": "es6",
                            "name": "value"
                        }
                    },
                    {
                        "input": "export default class Person {}",
                        "expected": {
                            "style": "es6",
                            "name": "Person"
                        }
                    },
                    {
                        "input": "module.exports = Router;",
                        "expected": {
                            "style": "commonjs",
                            "name": "Router"
                        }
                    }
                ]
            ),
            
            "namespace": QueryPattern(
                name="namespace",
                # Tree-sitter pattern
                pattern="""
                [
                    (namespace_definition
                      name: (identifier) @structure.namespace.name
                      body: (block) @structure.namespace.body) @structure.namespace,
                    (package_declaration
                      name: (identifier) @structure.namespace.decl.name) @structure.namespace.decl
                ]
                """,
                # Regex pattern for custom parsers - match various namespace syntaxes
                regex_pattern=r'(?:namespace\s+([\w\.]+)\s*\{|package\s+([\w\.]+);)',
                extract=lambda m: {
                    "type": "namespace",
                    "name": (
                        # For tree-sitter
                        m["captures"].get("structure.namespace.name", {}).get("text", "") or
                        m["captures"].get("structure.namespace.decl.name", {}).get("text", "")
                        if isinstance(m, dict) and "captures" in m
                        # For regex - get first non-empty group
                        else next((g for g in [m.group(1), m.group(2)] if g is not None), "")
                        if hasattr(m, "group") else ""
                    ),
                    "line": (
                        # For tree-sitter
                        m["captures"].get("structure.namespace", {}).get("start_point", [0])[0] or
                        m["captures"].get("structure.namespace.decl", {}).get("start_point", [0])[0]
                        if isinstance(m, dict) and "captures" in m
                        # For regex
                        else m.string.count('\n', 0, m.start()) + 1 if hasattr(m, "start") else 0
                    )
                },
                category=PatternCategory.STRUCTURE,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="*",
                confidence=0.9,
                metadata={
                    "relationships": [],
                    "metrics": PatternPerformanceMetrics(),
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    ),
                    # Block extraction metadata
                    "block_type": "namespace",
                    "contains_blocks": [],
                    "is_nestable": False,
                    "extraction_priority": 8,
                    # AI learning support
                    "adaptable": True,
                    "confidence_threshold": 0.8,
                    "learning_examples": [
                        "namespace MyApp { ... }",
                        "package com.example.app;"
                    ],
                    # Export format compatibility
                    "description": "Matches namespace and package declarations across languages",
                    "examples": [
                        "namespace MyApp { ... }",
                        "package com.example.app;"
                    ],
                    "version": "1.0",
                    "tags": ["namespace", "package", "module", "scope"]
                },
                # Test cases for validation
                test_cases=[
                    {
                        "input": "namespace MyApp { ... }",
                        "expected": {
                            "name": "MyApp"
                        }
                    },
                    {
                        "input": "package com.example.app;",
                        "expected": {
                            "name": "com.example.app"
                        }
                    }
                ]
            )
        }
    },

    PatternCategory.DOCUMENTATION: {
        PatternPurpose.UNDERSTANDING: {
            "documentation": QueryPattern(
                name="documentation",
                # Tree-sitter pattern
                pattern="""
                [
                    (comment) @documentation.comment,
                    (block_comment) @documentation.block,
                    (line_comment) @documentation.line,
                    (documentation_comment) @documentation.doc
                ]
                """,
                # Regex pattern for custom parsers
                regex_pattern=r"(?m)(\/\*\*[\s\S]*?\*\/|\/\*[\s\S]*?\*\/|\/\/.*$|#.*$)",
                extract=lambda m: {
                    "type": "documentation",
                    "content": (
                        # For tree-sitter
                        m["captures"].get("documentation.comment", {}).get("text", "") or
                        m["captures"].get("documentation.block", {}).get("text", "") or
                        m["captures"].get("documentation.line", {}).get("text", "") or
                        m["captures"].get("documentation.doc", {}).get("text", "")
                        if isinstance(m, dict) and "captures" in m
                        # For regex
                        else m.group(1) if hasattr(m, "group") else ""
                    ),
                    "kind": (
                        # For tree-sitter
                        "doc" if "documentation.doc" in m.get("captures", {}) else
                        "block" if "documentation.block" in m.get("captures", {}) else
                        "line" if "documentation.line" in m.get("captures", {}) else
                        "comment"
                        if isinstance(m, dict) and "captures" in m
                        # For regex
                        else ("doc" if m.group(1).startswith("/**") else
                              "block" if m.group(1).startswith("/*") else
                              "line")
                        if hasattr(m, "group") else ""
                    ),
                    "line": (
                        # For tree-sitter
                        m["captures"].get("documentation.comment", {}).get("start_point", [0])[0] or
                        m["captures"].get("documentation.block", {}).get("start_point", [0])[0] or
                        m["captures"].get("documentation.line", {}).get("start_point", [0])[0] or
                        m["captures"].get("documentation.doc", {}).get("start_point", [0])[0]
                        if isinstance(m, dict) and "captures" in m
                        # For regex
                        else m.string.count('\n', 0, m.start()) + 1 if hasattr(m, "start") else 0
                    )
                },
                category=PatternCategory.DOCUMENTATION,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="*",
                confidence=0.9,
                metadata={
                    "relationships": [],
                    "metrics": PatternPerformanceMetrics(),
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    ),
                    # Block extraction metadata
                    "block_type": "documentation",
                    "contains_blocks": [],
                    "is_nestable": False,
                    "extraction_priority": 15,
                    # AI learning support
                    "adaptable": True,
                    "confidence_threshold": 0.8,
                    "learning_examples": [
                        "// Line comment",
                        "/* Block comment */",
                        "/** Documentation comment */"
                    ],
                    # Export format compatibility
                    "description": "Matches documentation and comments across languages",
                    "examples": [
                        "// This is a line comment",
                        "/* This is a block comment */",
                        "/** This is a documentation comment */"
                    ],
                    "version": "1.0",
                    "tags": ["comment", "documentation", "doc", "block", "line"]
                },
                # Test cases for validation
                test_cases=[
                    {
                        "input": "// This is a line comment",
                        "expected": {
                            "kind": "line",
                            "content": "// This is a line comment"
                        }
                    },
                    {
                        "input": "/* This is a block comment */",
                        "expected": {
                            "kind": "block",
                            "content": "/* This is a block comment */"
                        }
                    },
                    {
                        "input": "/** This is a documentation comment */",
                        "expected": {
                            "kind": "doc",
                            "content": "/** This is a documentation comment */"
                        }
                    }
                ]
            )
        }
    }
}

class TreeSitterPatternLearner(CrossProjectPatternLearner):
    """Tree-sitter pattern learner that can be used across languages.
    
    This class specializes in learning and improving tree-sitter patterns
    across multiple projects and languages.
    """
    
    def __init__(self):
        super().__init__()
        self._block_extractor = None
        self._feature_extractor = None
        self._unified_parser = None
        self._pattern_processor = None
        self._ai_processor = None
        self._metrics = {
            "total_patterns": 0,
            "learned_patterns": 0,
            "failed_patterns": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "learning_times": []
        }
        register_shutdown_handler(self.cleanup)

    async def initialize(self):
        """Initialize with all required components."""
        await super().initialize()
        
        # Initialize required components
        self._block_extractor = await get_block_extractor()
        self._feature_extractor = await get_feature_extractor("*")
        self._unified_parser = await get_unified_parser()
        self._ai_processor = await get_ai_pattern_processor()
        
        # Lazy import pattern_processor
        from parsers.pattern_processor import pattern_processor
        self._pattern_processor = pattern_processor
        
        # Register with pattern processor
        await self._pattern_processor.register_language_patterns(
            "*", 
            COMMON_PATTERNS,
            self
        )
        
        # Initialize health monitoring
        await global_health_monitor.update_component_status(
            "common_pattern_learner",
            ComponentStatus.HEALTHY,
            details={
                "patterns_loaded": len(COMMON_PATTERNS),
                "capabilities": list(COMMON_CAPABILITIES)
            }
        )

    async def _get_parser(self) -> BaseParser:
        """Get appropriate parser for common patterns."""
        # Use unified parser for common patterns
        return await get_unified_parser()

    async def learn_from_project(self, project_path: str) -> List[Dict[str, Any]]:
        """Learn common patterns with AI assistance."""
        start_time = time.time()
        self._metrics["total_patterns"] += 1
        
        try:
            # Try AI-assisted learning first
            ai_context = AIContext(
                language_id="*",
                file_type=FileType.CODE,
                interaction_type=InteractionType.LEARNING,
                repository_id=None,
                file_path=project_path
            )
            
            ai_result = await self._ai_processor.process_with_ai(
                source_code="",  # Will be filled by processor
                context=ai_context
            )
            
            learned_patterns = []
            if ai_result.success:
                learned_patterns.extend(ai_result.learned_patterns)
                self._metrics["learned_patterns"] += len(ai_result.learned_patterns)
            
            # Then do cross-project learning through base class
            project_patterns = await self._extract_project_patterns(project_path)
            await self._integrate_patterns(project_patterns, project_path)
            learned_patterns.extend(project_patterns)
            
            # Finally add common patterns
            async with AsyncErrorBoundary("common_pattern_learning"):
                # Extract blocks with caching
                blocks = await self._block_extractor.get_child_blocks(
                    "*",
                    "",  # Will be filled from files
                    None
                )
                
                # Extract features with metrics
                features = []
                for block in blocks:
                    block_features = await self._feature_extractor.extract_features(
                        block.content,
                        block.metadata
                    )
                    features.append(block_features)
                
                # Learn patterns from features
                common_patterns = await self._learn_patterns_from_features(features)
                learned_patterns.extend(common_patterns)
            
            # Update metrics
            learning_time = time.time() - start_time
            self._metrics["learning_times"].append(learning_time)
            
            # Update health status
            await global_health_monitor.update_component_status(
                "common_pattern_learner",
                ComponentStatus.HEALTHY,
                details={
                    "learned_patterns": len(learned_patterns),
                    "learning_time": learning_time
                }
            )
            
            return learned_patterns
            
        except Exception as e:
            self._metrics["failed_patterns"] += 1
            await log(f"Error learning patterns: {e}", level="error")
            
            # Update health status
            await global_health_monitor.update_component_status(
                "common_pattern_learner",
                ComponentStatus.DEGRADED,
                error=True,
                details={"error": str(e)}
            )
            
            return []

    async def cleanup(self):
        """Clean up pattern learner resources."""
        try:
            # Clean up base class resources
            await super().cleanup()
            
            # Clean up specific components
            if self._block_extractor:
                await self._block_extractor.cleanup()
            if self._feature_extractor:
                await self._feature_extractor.cleanup()
            if self._unified_parser:
                await self._unified_parser.cleanup()
            if self._ai_processor:
                await self._ai_processor.cleanup()
            
            # Update final status
            await global_health_monitor.update_component_status(
                "common_pattern_learner",
                ComponentStatus.SHUTDOWN,
                details={
                    "cleanup": "successful",
                    "final_metrics": self._metrics
                }
            )
            
        except Exception as e:
            await log(f"Error in cleanup: {e}", level="error")
            await global_health_monitor.update_component_status(
                "common_pattern_learner",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"cleanup_error": str(e)}
            )

# Initialize pattern learner
tree_sitter_pattern_learner = TreeSitterPatternLearner()

@handle_async_errors(error_types=ProcessingError)
async def process_tree_sitter_pattern(
    pattern: Union[QueryPattern, 'AdaptivePattern', 'ResilientPattern'],
    source_code: str,
    context: Optional[PatternContext] = None
) -> List[Dict[str, Any]]:
    """Process a tree-sitter pattern with full system integration.
    
    This function processes tree-sitter patterns against source code,
    handling parsing, block extraction, and feature extraction.
    While it contains legacy support for regex patterns, it is optimized
    for tree-sitter pattern processing.
    """
    async with AsyncErrorBoundary(
        operation_name=f"process_pattern_{pattern.name}",
        error_types=ProcessingError,
        severity=ErrorSeverity.ERROR
    ):
        # Get all required components
        block_extractor = await get_block_extractor()
        feature_extractor = await get_feature_extractor("*")
        unified_parser = await get_unified_parser()
        
        # Parse if needed
        if not context or not context.code_structure:
            parse_result = await unified_parser.parse(source_code, "*", FileType.CODE)
            if parse_result and parse_result.ast:
                context = await create_tree_sitter_context(
                    "",
                    parse_result.ast
                )
        
        # Extract and process blocks with caching
        cache_key = f"common_pattern_{pattern.name}_{hash(source_code)}"
        request_cache = get_current_request_cache()
        cached_result = await request_cache.get(cache_key) if request_cache else None
        if cached_result:
            update_common_pattern_metrics(
                pattern.name,
                {"cache_hits": 1}
            )
            return cached_result
        
        blocks = await block_extractor.get_child_blocks(
            "*",
            source_code,
            context.code_structure if context else None
        )
        
        # Process blocks and extract features
        matches = []
        start_time = time.time()
        
        # Determine parser type
        parser_type = context.parser_type if context and hasattr(context, "parser_type") else ParserType.TREE_SITTER
        
        # Process based on parser type
        if parser_type == ParserType.TREE_SITTER:
            # Use tree-sitter pattern
            for block in blocks:
                # For QueryPattern instances, use the matches method
                if isinstance(pattern, QueryPattern):
                    block_matches = pattern.matches(block.content)
                # For other pattern types, call matches directly
                else:
                    block_matches = await pattern.matches(block.content)
                    
                if block_matches:
                    # Extract features for each match
                    for match in block_matches:
                        features = await feature_extractor.extract_features(
                            block.content,
                            match
                        )
                        match["features"] = features
                        match["block"] = block.__dict__
                    matches.extend(block_matches)
        else:
            # Use regex pattern for custom parsers
            if hasattr(pattern, "regex_pattern") and pattern.regex_pattern:
                import re
                regex = re.compile(pattern.regex_pattern, re.MULTILINE | re.DOTALL)
                for match in regex.finditer(source_code):
                    match_data = {
                        "text": match.group(0),
                        "start": match.start(),
                        "end": match.end(),
                        "groups": match.groups(),
                        "named_groups": match.groupdict()
                    }
                    
                    # Apply extraction function if provided
                    if hasattr(pattern, "extract") and pattern.extract:
                        try:
                            extracted = pattern.extract(match)
                            if extracted:
                                match_data.update(extracted)
                        except Exception as e:
                            await log(f"Error in extraction function: {e}", level="error")
                            
                    matches.append(match_data)
        
        # Cache the result
        if request_cache:
            await request_cache.set(cache_key, matches)
            update_common_pattern_metrics(
                pattern.name,
                {"cache_misses": 1}
            )
        
        # Update pattern metrics
        execution_time = time.time() - start_time
        await update_common_pattern_metrics(
            pattern.name,
            {
                "execution_time": execution_time,
                "matches": len(matches)
            }
        )
        
        # Update health status
        await global_health_monitor.update_component_status(
            "common_pattern_processor",
            ComponentStatus.HEALTHY,
            details={
                "pattern": pattern.name,
                "matches": len(matches),
                "processing_time": execution_time,
                "parser_type": parser_type.value
            }
        )
        
        return matches

async def update_common_pattern_metrics(pattern_name: str, metrics: Dict[str, Any]) -> None:
    """Update performance metrics for a common pattern."""
    if pattern_name in COMMON_PATTERN_METRICS:
        pattern_metrics = COMMON_PATTERN_METRICS[pattern_name]
        pattern_metrics.execution_time = metrics.get("execution_time", 0.0)
        pattern_metrics.memory_usage = metrics.get("memory_usage", 0)
        pattern_metrics.cache_hits = metrics.get("cache_hits", 0)
        pattern_metrics.cache_misses = metrics.get("cache_misses", 0)
        pattern_metrics.error_count = metrics.get("error_count", 0)
        
        total = pattern_metrics.cache_hits + pattern_metrics.cache_misses
        if total > 0:
            pattern_metrics.success_rate = pattern_metrics.cache_hits / total

async def validate_tree_sitter_pattern(
    pattern: Union[QueryPattern, 'AdaptivePattern', 'ResilientPattern'],
    context: Optional[PatternContext] = None
) -> PatternValidationResult:
    """Validate a tree-sitter pattern with system integration.
    
    Validates tree-sitter patterns against their test cases and using
    the pattern processor. Optimized for tree-sitter patterns but
    maintains legacy support for regex patterns.
    
    Args:
        pattern: The tree-sitter pattern to validate
        context: Optional pattern context
        
    Returns:
        A PatternValidationResult indicating validation status
    """
    async with AsyncErrorBoundary("tree_sitter_pattern_validation"):
        # Get pattern processor
        from parsers.pattern_processor import pattern_processor
        
        # For QueryPattern with test cases, validate against test cases first
        if isinstance(pattern, QueryPattern) and hasattr(pattern, "test_cases") and pattern.test_cases:
            for test_case in pattern.test_cases:
                input_code = test_case.get("input", "")
                expected = test_case.get("expected", {})
                
                if not input_code or not expected:
                    continue
                    
                # Try matching against the test case
                matches = pattern.matches(input_code)
                
                # Check if any match contains all expected values
                match_found = False
                for match in matches:
                    match_valid = True
                    for key, value in expected.items():
                        if key not in match or match[key] != value:
                            match_valid = False
                            break
                    if match_valid:
                        match_found = True
                        break
                        
                if not match_found:
                    return PatternValidationResult(
                        is_valid=False,
                        validation_time=0.0,
                        error_message=f"Pattern failed test case: {test_case.get('input', '')}",
                        pattern_name=pattern.name
                    )
        
        # Then validate with pattern processor
        validation_result = await pattern_processor.validate_pattern(
            pattern,
            language_id="*",
            context=context
        )
        
        return validation_result

async def create_tree_sitter_context(
    file_path: str,
    code_structure: Dict[str, Any],
    learned_patterns: Optional[Dict[str, Any]] = None,
    parser_type: ParserType = ParserType.TREE_SITTER
) -> PatternContext:
    """Create tree-sitter pattern context with full system integration.
    
    Creates a context specialized for tree-sitter pattern processing,
    containing the AST and other metadata needed for pattern matching.
    
    Args:
        file_path: Path to the file being processed
        code_structure: Parsed AST or code structure
        learned_patterns: Optional patterns learned from previous runs
        parser_type: The type of parser being used (defaults to tree-sitter)
        
    Returns:
        A PatternContext instance with all necessary metadata
    """
    # Get unified parser
    unified_parser = await get_unified_parser()
    
    # Parse the code structure if needed
    if not code_structure:
        parse_result = await unified_parser.parse(
            file_path,
            language_id="*",  # Common patterns work across languages
            file_type=FileType.CODE
        )
        code_structure = parse_result.ast if parse_result else {}
    
    # Extract filename from path
    filename = file_path.split("/")[-1] if "/" in file_path else file_path
    
    context = PatternContext(
        code_structure=code_structure,
        language_stats={"language": "*"},  # Common patterns are language-agnostic
        project_patterns=list(learned_patterns.values()) if learned_patterns else [],
        file_location=file_path,
        dependencies=set(),
        recent_changes=[],
        scope_level="global",
        allows_nesting=True,
        relevant_patterns=list(COMMON_PATTERNS.keys()),
        parser_type=parser_type
    )
    
    # Add system integration metadata based on parser type
    if parser_type == ParserType.TREE_SITTER:
        context.metadata.update({
            "parser_type": ParserType.TREE_SITTER,
            "feature_extraction_enabled": True,
            "block_extraction_enabled": True,
            "pattern_learning_enabled": True,
            "ast_available": True,
            "query_capable": True
        })
    else:
        context.metadata.update({
            "parser_type": ParserType.CUSTOM,
            "feature_extraction_enabled": True,
            "block_extraction_enabled": True,
            "pattern_learning_enabled": True,
            "regex_available": True,
            "custom_parser": True
        })
    
    # Add file metadata
    context.metadata.update({
        "filename": filename,
        "file_extension": filename.split(".")[-1] if "." in filename else "",
        "timestamp": time.time()
    })
    
    return context

async def process_common_pattern(pattern, source_code, context=None):
    """Process a pattern if it is a common pattern; otherwise return None."""
    # Check if the pattern is a common pattern by name and category
    for category, purposes in COMMON_PATTERNS.items():
        for purpose, patterns in purposes.items():
            for name, common_pattern in patterns.items():
                if pattern.name == name and pattern.category == category:
                    # Use the pattern's extract method if regex, or matches if tree-sitter
                    if hasattr(common_pattern, 'matches') and callable(common_pattern.matches):
                        return await common_pattern.matches(source_code, context)
                    elif hasattr(common_pattern, 'extract') and callable(common_pattern.extract):
                        import re
                        matches = []
                        for m in re.finditer(common_pattern.pattern, source_code, re.MULTILINE):
                            matches.append(common_pattern.extract(m))
                        return matches
    return None

async def validate_common_pattern(pattern, context=None):
    """Validate a pattern if it is a common pattern; otherwise return None."""
    for category, purposes in COMMON_PATTERNS.items():
        for purpose, patterns in purposes.items():
            for name, common_pattern in patterns.items():
                if pattern.name == name and pattern.category == category:
                    # Use the validate_tree_sitter_pattern if available
                    from .common import validate_tree_sitter_pattern
                    return await validate_tree_sitter_pattern(common_pattern, context)
    return None

# Export public interfaces
__all__ = [
    'COMMON_PATTERNS',
    'COMMON_PATTERN_RELATIONSHIPS',
    'COMMON_PATTERN_METRICS',
    'COMMON_CAPABILITIES',
    'TreeSitterPatternLearner',
    'tree_sitter_pattern_learner',
    'process_tree_sitter_pattern',
    'update_common_pattern_metrics',
    'validate_tree_sitter_pattern',
    'create_tree_sitter_context',
    'process_common_pattern',
    'validate_common_pattern'
]

# Module identification
LANGUAGE = "*" 