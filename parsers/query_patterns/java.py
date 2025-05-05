"""Java-specific patterns with enhanced type system and relationships.

This module provides Java-specific patterns that integrate with the enhanced
pattern processing system, including proper typing, relationships, and context.
"""

import os
import time
import json
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple, Union, Any, Callable

from parsers.types import (
    PatternCategory, PatternPurpose, PatternType, PatternRelationType,
    PatternContext, PatternNode, PatternRelationship, PatternValidationResult,
    PatternMatchResult, PatternPerformanceMetrics, QueryPattern,
    AICapability, AIContext, ExtractedFeatures, FileType, ParserType
)
from parsers.pattern_processor import register_pattern, pattern_processor
from utils.logger import log
from utils.health_monitor import global_health_monitor, ComponentStatus
from utils.error_handling import AsyncErrorBoundary, handle_async_errors, ProcessingError, ErrorSeverity
from utils.shutdown import register_shutdown_handler
from parsers.block_extractor import get_block_extractor
from parsers.feature_extractor import BaseFeatureExtractor
from parsers.unified_parser import get_unified_parser
from parsers.base_parser import BaseParser
from parsers.tree_sitter_parser import get_tree_sitter_parser
from parsers.ai_pattern_processor import get_ai_pattern_processor
from .common import (
    COMMON_PATTERNS, create_tree_sitter_context, 
    process_tree_sitter_pattern, validate_tree_sitter_pattern
)
from .enhanced_patterns import (
    TreeSitterPattern, TreeSitterAdaptivePattern, TreeSitterResilientPattern, 
    TreeSitterCrossProjectPatternLearner, DATA_DIR
)
from .tree_sitter_utils import execute_tree_sitter_query, count_nodes, extract_captures
from .recovery_strategies import get_recovery_strategies
from .learning_strategies import get_learning_strategies

# Constants
LANGUAGE = "java"
JAVA_CAPABILITIES = {
    "syntax_analysis",
    "semantic_analysis",
    "documentation_extraction",
    "best_practices_detection",
    "common_issues_identification"
}

# Pattern relationships (to be populated)
JAVA_PATTERN_RELATIONSHIPS = {
    "class_definition": [
        PatternRelationship(source="class_definition", target="method_definition", relationship_type="contains", weight=1.0),
        PatternRelationship(source="class_definition", target="field_declaration", relationship_type="contains", weight=0.8),
        PatternRelationship(source="class_definition", target="javadoc", relationship_type="documented_by", weight=0.5)
    ],
    "method_definition": [
        PatternRelationship(source="method_definition", target="javadoc", relationship_type="documented_by", weight=0.5)
    ],
    "interface_definition": [
        PatternRelationship(source="interface_definition", target="method_definition", relationship_type="declares", weight=0.9),
        PatternRelationship(source="interface_definition", target="javadoc", relationship_type="documented_by", weight=0.5)
    ]
}

# Pattern metrics (to be populated)
JAVA_PATTERN_METRICS = {
    "class_definition": PatternPerformanceMetrics(
        avg_match_time=0.005,
        avg_extraction_time=0.002,
        success_rate=0.98,
        memory_usage=50 # KB
    ),
    "method_definition": PatternPerformanceMetrics(
        avg_match_time=0.003,
        avg_extraction_time=0.001,
        success_rate=0.99,
        memory_usage=30 # KB
    ),
    "interface_definition": PatternPerformanceMetrics(
        avg_match_time=0.004,
        avg_extraction_time=0.002,
        success_rate=0.97,
        memory_usage=45 # KB
    )
}

# Enhanced Java patterns with proper typing and relationships
JAVA_PATTERNS = {
    **COMMON_PATTERNS,  # Inherit common patterns
    
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "class_definition": TreeSitterResilientPattern(
                name="class_definition",
                pattern="""
                [
                    (class_declaration
                        name: (identifier) @syntax.class.name
                        superclass: (superclass)? @syntax.class.superclass
                        interfaces: (super_interfaces)? @syntax.class.interfaces
                        body: (class_body) @syntax.class.body) @syntax.class.def
                ]
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="java",
                confidence=0.95,
                extract=lambda m: {
                    "type": "class",
                    "name": m["captures"]["syntax.class.name"]["text"] if "syntax.class.name" in m.get("captures", {}) else "",
                    "superclass": m["captures"]["syntax.class.superclass"]["text"] if "syntax.class.superclass" in m.get("captures", {}) else None,
                    "has_interfaces": "syntax.class.interfaces" in m.get("captures", {}),
                    "body_content": m["captures"]["syntax.class.body"]["text"] if "syntax.class.body" in m.get("captures", {}) else ""
                },
                block_type="class",
                contains_blocks=["method", "field", "constructor"],
                is_nestable=True,
                extraction_priority=20,
                metadata={
                    "relationships": JAVA_PATTERN_RELATIONSHIPS["class_definition"],
                    "metrics": JAVA_PATTERN_METRICS["class_definition"],
                    "validation": {
                        "is_valid": True,
                        "validation_time": 0.0
                    },
                    "description": "Matches Java class declarations",
                    "examples": [
                        "class MyClass { }",
                        "class Child extends Parent implements Interface { }"
                    ],
                    "version": "1.0",
                    "tags": ["class", "declaration", "oop"]
                },
                test_cases=[
                    {
                        "input": "class Example { }",
                        "expected": {
                            "type": "class",
                            "name": "Example",
                            "superclass": None
                        }
                    },
                    {
                        "input": "class Child extends Parent { }",
                        "expected": {
                            "type": "class",
                            "name": "Child",
                            "superclass": "Parent"
                        }
                    }
                ]
            ),
            
            "method_definition": TreeSitterResilientPattern(
                name="method_definition",
                pattern="""
                [
                    (method_declaration
                        modifiers: (modifiers)? @syntax.method.modifiers
                        type: (_) @syntax.method.return_type
                        name: (identifier) @syntax.method.name
                        parameters: (formal_parameters) @syntax.method.params
                        body: (block)? @syntax.method.body) @syntax.method.def
                ]
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="java",
                confidence=0.95,
                extract=lambda m: {
                    "type": "method",
                    "name": m["captures"]["syntax.method.name"]["text"] if "syntax.method.name" in m.get("captures", {}) else "",
                    "return_type": m["captures"]["syntax.method.return_type"]["text"] if "syntax.method.return_type" in m.get("captures", {}) else "",
                    "modifiers": m["captures"]["syntax.method.modifiers"]["text"] if "syntax.method.modifiers" in m.get("captures", {}) else "",
                    "is_public": "public" in m["captures"]["syntax.method.modifiers"]["text"] if "syntax.method.modifiers" in m.get("captures", {}) else False,
                    "is_static": "static" in m["captures"]["syntax.method.modifiers"]["text"] if "syntax.method.modifiers" in m.get("captures", {}) else False,
                    "parameters": m["captures"]["syntax.method.params"]["text"] if "syntax.method.params" in m.get("captures", {}) else "()"
                },
                block_type="method",
                contains_blocks=["statement", "expression", "conditional"],
                is_nestable=True,
                extraction_priority=15,
                metadata={
                    "relationships": JAVA_PATTERN_RELATIONSHIPS["method_definition"],
                    "metrics": JAVA_PATTERN_METRICS["method_definition"],
                    "validation": {
                        "is_valid": True,
                        "validation_time": 0.0
                    },
                    "description": "Matches Java method declarations",
                    "examples": [
                        "public void example() { }",
                        "private String getName(String param) { return param; }"
                    ],
                    "version": "1.0",
                    "tags": ["method", "function", "declaration"]
                },
                test_cases=[
                    {
                        "input": "public void test() { }",
                        "expected": {
                            "type": "method",
                            "name": "test",
                            "return_type": "void",
                            "is_public": True
                        }
                    },
                    {
                        "input": "private String getName(String name) { return name; }",
                        "expected": {
                            "type": "method",
                            "name": "getName",
                            "return_type": "String"
                        }
                    }
                ]
            ),
            
            "interface_definition": TreeSitterPattern(
                name="interface_definition",
                pattern="""
                [
                    (interface_declaration
                        name: (identifier) @syntax.interface.name
                        extends: (extends_interfaces)? @syntax.interface.extends
                        body: (interface_body) @syntax.interface.body) @syntax.interface.def
                ]
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="java",
                confidence=0.95,
                extract=lambda m: {
                    "type": "interface",
                    "name": m["captures"]["syntax.interface.name"]["text"] if "syntax.interface.name" in m.get("captures", {}) else "",
                    "extends": m["captures"]["syntax.interface.extends"]["text"] if "syntax.interface.extends" in m.get("captures", {}) else None,
                    "body_content": m["captures"]["syntax.interface.body"]["text"] if "syntax.interface.body" in m.get("captures", {}) else ""
                },
                block_type="interface",
                contains_blocks=["method_declaration"],
                is_nestable=True,
                extraction_priority=18,
                metadata={
                    "relationships": JAVA_PATTERN_RELATIONSHIPS["interface_definition"],
                    "metrics": JAVA_PATTERN_METRICS["interface_definition"],
                    "validation": {
                        "is_valid": True,
                        "validation_time": 0.0
                    },
                    "description": "Matches Java interface declarations",
                    "examples": [
                        "interface MyInterface { }",
                        "interface Service extends Repository { }"
                    ],
                    "version": "1.0",
                    "tags": ["interface", "declaration", "oop"]
                },
                test_cases=[
                    {
                        "input": "interface Example { void test(); }",
                        "expected": {
                            "type": "interface",
                            "name": "Example"
                        }
                    },
                    {
                        "input": "interface Child extends Parent { }",
                        "expected": {
                            "type": "interface",
                            "name": "Child",
                            "extends": "Parent"
                        }
                    }
                ]
            ),
            
            "enum_definition": TreeSitterPattern(
                name="enum_definition",
                pattern="""
                [
                    (enum_declaration
                        name: (identifier) @syntax.enum.name
                        extends: (extends_interfaces)? @syntax.enum.extends
                        body: (enum_body) @syntax.enum.body) @syntax.enum.def
                ]
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="java",
                confidence=0.95,
                extract=lambda m: {
                    "type": "enum",
                    "name": m["captures"]["syntax.enum.name"]["text"] if "syntax.enum.name" in m.get("captures", {}) else "",
                    "extends": m["captures"]["syntax.enum.extends"]["text"] if "syntax.enum.extends" in m.get("captures", {}) else None,
                    "body_content": m["captures"]["syntax.enum.body"]["text"] if "syntax.enum.body" in m.get("captures", {}) else ""
                },
                block_type="enum",
                contains_blocks=["enum_body"],
                is_nestable=True,
                extraction_priority=18,
                metadata={
                    "relationships": [],
                    "metrics": PatternPerformanceMetrics(),
                    "validation": {
                        "is_valid": True,
                        "validation_time": 0.0
                    },
                    "description": "Matches Java enum declarations",
                    "examples": [
                        "enum MyEnum { VALUE1, VALUE2 }"
                    ],
                    "version": "1.0",
                    "tags": ["enum", "declaration"]
                },
                test_cases=[
                    {
                        "input": "enum MyEnum { VALUE1, VALUE2 }",
                        "expected": {
                            "type": "enum",
                            "name": "MyEnum",
                            "extends": None
                        }
                    }
                ]
            ),
            
            "annotation_definition": TreeSitterPattern(
                name="annotation_definition",
                pattern="""
                [
                    (annotation
                        name: (_) @semantics.annotation.name
                        arguments: (annotation_argument_list)? @semantics.annotation.args) @semantics.annotation.def
                ]
                """,
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="java",
                confidence=0.9,
                extract=lambda m: {
                    "type": "annotation",
                    "name": m["captures"]["semantics.annotation.name"]["text"] if "semantics.annotation.name" in m.get("captures", {}) else "",
                    "has_args": "semantics.annotation.args" in m.get("captures", {}),
                    "args": m["captures"]["semantics.annotation.args"]["text"] if "semantics.annotation.args" in m.get("captures", {}) else ""
                },
                block_type="annotation",
                is_nestable=False,
                extraction_priority=5,
                metadata={
                    "relationships": [],
                    "metrics": PatternPerformanceMetrics(),
                    "validation": {
                        "is_valid": True,
                        "validation_time": 0.0
                    },
                    "description": "Matches Java annotations",
                    "examples": [
                        "@Override",
                        "@SuppressWarnings(\"unchecked\")"
                    ],
                    "version": "1.0",
                    "tags": ["annotation", "metadata", "decorator"]
                },
                test_cases=[
                    {
                        "input": "@Override",
                        "expected": {
                            "type": "annotation",
                            "name": "Override",
                            "has_args": False
                        }
                    },
                    {
                        "input": "@SuppressWarnings(\"unchecked\")",
                        "expected": {
                            "type": "annotation",
                            "name": "SuppressWarnings",
                            "has_args": True
                        }
                    }
                ]
            )
        }
    },
    
    PatternCategory.SEMANTICS: {
        PatternPurpose.UNDERSTANDING: {
            "field_declaration": QueryPattern(
                name="field_declaration",
                pattern="""
                [
                    (field_declaration
                        modifiers: (modifiers)? @semantics.field.modifiers
                        type: (_) @semantics.field.type
                        declarator: (variable_declarator
                            name: (identifier) @semantics.field.name
                            value: (_)? @semantics.field.value)) @semantics.field.def
                ]
                """,
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="java",
                confidence=0.9,
                extract=lambda m: {
                    "type": "field",
                    "name": m["captures"]["semantics.field.name"]["text"] if "semantics.field.name" in m.get("captures", {}) else "",
                    "field_type": m["captures"]["semantics.field.type"]["text"] if "semantics.field.type" in m.get("captures", {}) else "",
                    "modifiers": m["captures"]["semantics.field.modifiers"]["text"] if "semantics.field.modifiers" in m.get("captures", {}) else "",
                    "is_final": "final" in m["captures"]["semantics.field.modifiers"]["text"] if "semantics.field.modifiers" in m.get("captures", {}) else False,
                    "is_static": "static" in m["captures"]["semantics.field.modifiers"]["text"] if "semantics.field.modifiers" in m.get("captures", {}) else False,
                    "has_value": "semantics.field.value" in m.get("captures", {})
                },
                block_type="field",
                is_nestable=False,
                extraction_priority=10,
                metadata={
                    "relationships": [],
                    "metrics": PatternPerformanceMetrics(),
                    "validation": {
                        "is_valid": True,
                        "validation_time": 0.0
                    },
                    "description": "Matches Java field declarations",
                    "examples": [
                        "private int count;",
                        "public static final String NAME = \"value\";"
                    ],
                    "version": "1.0",
                    "tags": ["field", "property", "attribute", "variable"]
                },
                test_cases=[
                    {
                        "input": "private int count;",
                        "expected": {
                            "type": "field",
                            "name": "count",
                            "field_type": "int"
                        }
                    },
                    {
                        "input": "public static final String NAME = \"value\";",
                        "expected": {
                            "type": "field",
                            "name": "NAME",
                            "field_type": "String",
                            "is_final": True,
                            "is_static": True,
                            "has_value": True
                        }
                    }
                ]
            ),
            
            "annotation": QueryPattern(
                name="annotation",
                pattern="""
                [
                    (annotation
                        name: (_) @semantics.annotation.name
                        arguments: (annotation_argument_list)? @semantics.annotation.args) @semantics.annotation.def
                ]
                """,
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="java",
                confidence=0.9,
                extract=lambda m: {
                    "type": "annotation",
                    "name": m["captures"]["semantics.annotation.name"]["text"] if "semantics.annotation.name" in m.get("captures", {}) else "",
                    "has_args": "semantics.annotation.args" in m.get("captures", {}),
                    "args": m["captures"]["semantics.annotation.args"]["text"] if "semantics.annotation.args" in m.get("captures", {}) else ""
                },
                block_type="annotation",
                is_nestable=False,
                extraction_priority=5,
                metadata={
                    "relationships": [],
                    "metrics": PatternPerformanceMetrics(),
                    "validation": {
                        "is_valid": True,
                        "validation_time": 0.0
                    },
                    "description": "Matches Java annotations",
                    "examples": [
                        "@Override",
                        "@SuppressWarnings(\"unchecked\")"
                    ],
                    "version": "1.0",
                    "tags": ["annotation", "metadata", "decorator"]
                },
                test_cases=[
                    {
                        "input": "@Override",
                        "expected": {
                            "type": "annotation",
                            "name": "Override",
                            "has_args": False
                        }
                    },
                    {
                        "input": "@SuppressWarnings(\"unchecked\")",
                        "expected": {
                            "type": "annotation",
                            "name": "SuppressWarnings",
                            "has_args": True
                        }
                    }
                ]
            )
        }
    },
    
    PatternCategory.DOCUMENTATION: {
        PatternPurpose.UNDERSTANDING: {
            "javadoc": QueryPattern(
                name="javadoc",
                pattern="""
                [
                    (block_comment) @documentation.javadoc
                ]
                """,
                category=PatternCategory.DOCUMENTATION,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="java",
                confidence=0.9,
                extract=lambda m: {
                    "type": "javadoc",
                    "content": m["captures"]["documentation.javadoc"]["text"] if "documentation.javadoc" in m.get("captures", {}) else "",
                    "is_javadoc": m["captures"]["documentation.javadoc"]["text"].startswith("/**") if "documentation.javadoc" in m.get("captures", {}) else False,
                    "has_param": "@param" in m["captures"]["documentation.javadoc"]["text"] if "documentation.javadoc" in m.get("captures", {}) else False,
                    "has_return": "@return" in m["captures"]["documentation.javadoc"]["text"] if "documentation.javadoc" in m.get("captures", {}) else False,
                    "line": m.get("line", 0)
                },
                block_type="javadoc",
                is_nestable=False,
                extraction_priority=2,
                metadata={
                    "relationships": [],
                    "metrics": PatternPerformanceMetrics(),
                    "validation": {
                        "is_valid": True,
                        "validation_time": 0.0
                    },
                    "description": "Matches Java documentation comments",
                    "examples": [
                        "/** This is a basic Javadoc */",
                        "/**\n * @param name User name\n * @return User object\n */"
                    ],
                    "version": "1.0",
                    "tags": ["javadoc", "documentation", "comment"]
                },
                test_cases=[
                    {
                        "input": "/** This is a basic Javadoc */",
                        "expected": {
                            "type": "javadoc",
                            "is_javadoc": True
                        }
                    },
                    {
                        "input": "/**\n * @param name User name\n * @return User object\n */",
                        "expected": {
                            "type": "javadoc",
                            "is_javadoc": True,
                            "has_param": True,
                            "has_return": True
                        }
                    }
                ]
            ),
            
            "comments": QueryPattern(
                name="comments",
                pattern="""
                [
                    (line_comment) @documentation.comment,
                    (block_comment) @documentation.block_comment
                ]
                """,
                category=PatternCategory.DOCUMENTATION,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="java",
                confidence=0.9,
                extract=lambda m: {
                    "type": "comment",
                    "content": m["captures"]["documentation.comment"]["text"] if "documentation.comment" in m.get("captures", {}) 
                             else m["captures"]["documentation.block_comment"]["text"] if "documentation.block_comment" in m.get("captures", {}) 
                             else "",
                    "is_line": "documentation.comment" in m.get("captures", {}),
                    "is_block": "documentation.block_comment" in m.get("captures", {}),
                    "is_todo": "TODO" in (m["captures"]["documentation.comment"]["text"] if "documentation.comment" in m.get("captures", {}) 
                                         else m["captures"]["documentation.block_comment"]["text"] if "documentation.block_comment" in m.get("captures", {}) 
                                         else ""),
                    "line": m.get("line", 0)
                },
                block_type="comment",
                is_nestable=False,
                extraction_priority=1,
                metadata={
                    "relationships": [],
                    "metrics": PatternPerformanceMetrics(),
                    "validation": {
                        "is_valid": True,
                        "validation_time": 0.0
                    },
                    "description": "Matches Java comments",
                    "examples": [
                        "// Line comment",
                        "/* Block comment */"
                    ],
                    "version": "1.0",
                    "tags": ["comment", "documentation"]
                },
                test_cases=[
                    {
                        "input": "// TODO: Fix this later",
                        "expected": {
                            "type": "comment",
                            "is_line": True,
                            "is_todo": True
                        }
                    },
                    {
                        "input": "/* This is a block comment */",
                        "expected": {
                            "type": "comment",
                            "is_block": True
                        }
                    }
                ]
            )
        }
    },

    PatternCategory.BEST_PRACTICES: {
        # ... existing patterns ...
    },

    PatternCategory.COMMON_ISSUES: {
        "unchecked_exception": QueryPattern(
            name="unchecked_exception",
            pattern=r'throw\s+new\s+(?:Runtime|Null|Array|Class|Illegal|Security)Exception',
            extract=lambda m: {
                "type": "unchecked_exception",
                "content": m.group(0),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "confidence": 0.9
            },
            category=PatternCategory.COMMON_ISSUES,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            metadata={"description": "Detects unchecked exceptions", "examples": ["throw new RuntimeException()"]}
        ),
        "resource_leak": QueryPattern(
            name="resource_leak",
            pattern=r'new\s+(?:File|Socket|Connection|Stream)[^;]*;(?!\s*try)',
            extract=lambda m: {
                "type": "resource_leak",
                "content": m.group(0),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "confidence": 0.85
            },
            category=PatternCategory.COMMON_ISSUES,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            metadata={"description": "Detects potential resource leaks", "examples": ["FileInputStream fis = new FileInputStream(file);"]}
        ),
        "null_pointer": QueryPattern(
            name="null_pointer",
            pattern=r'([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\.\s*[a-zA-Z_$][a-zA-Z0-9_$]*\s*\([^)]*\)\s*;',
            extract=lambda m: {
                "type": "null_pointer",
                "object": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "needs_verification": True
            },
            category=PatternCategory.COMMON_ISSUES,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            metadata={"description": "Detects potential null pointer dereferences", "examples": ["obj.method();"]}
        ),
        "unclosed_resource": QueryPattern(
            name="unclosed_resource",
            pattern=r'(?:implements\s+AutoCloseable|extends\s+(?:InputStream|OutputStream|Reader|Writer))[^{]*\{(?![^}]*close\(\))',
            extract=lambda m: {
                "type": "unclosed_resource",
                "content": m.group(0),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "confidence": 0.8
            },
            category=PatternCategory.COMMON_ISSUES,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            metadata={"description": "Detects unclosed resources", "examples": ["class MyResource implements AutoCloseable { }"]}
        ),
        "concurrent_modification": QueryPattern(
            name="concurrent_modification",
            pattern=r'for\s*\([^)]+:\s*([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\)[^{]*\{\s*[^}]*\1\.(?:add|remove|clear)\(',
            extract=lambda m: {
                "type": "concurrent_modification",
                "collection": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "confidence": 0.9
            },
            category=PatternCategory.COMMON_ISSUES,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            metadata={"description": "Detects concurrent modification in loops", "examples": ["for (Item item : list) { list.remove(item); }"]}
        )
    }
}

def create_pattern_context(file_path: str, code_structure: Dict[str, Any]) -> PatternContext:
    """Create pattern context for Java files."""
    return PatternContext(
        code_structure=code_structure,
        language_stats={"language": "java", "version": "17+"},
        project_patterns=[],
        file_location=file_path,
        dependencies=set(),
        recent_changes=[],
        scope_level="global",
        allows_nesting=True,
        relevant_patterns=list(JAVA_PATTERNS.keys())
    )

def get_java_pattern_relationships(pattern_name: str) -> List[PatternRelationship]:
    """Get relationships for a specific pattern."""
    return JAVA_PATTERN_RELATIONSHIPS.get(pattern_name, [])

def update_java_pattern_metrics(pattern_name: str, metrics: Dict[str, Any]) -> None:
    """Update performance metrics for a pattern."""
    if pattern_name in JAVA_PATTERN_METRICS:
        pattern_metrics = JAVA_PATTERN_METRICS[pattern_name]
        pattern_metrics.execution_time = metrics.get("execution_time", 0.0)
        pattern_metrics.memory_usage = metrics.get("memory_usage", 0)
        pattern_metrics.cache_hits = metrics.get("cache_hits", 0)
        pattern_metrics.cache_misses = metrics.get("cache_misses", 0)
        pattern_metrics.error_count = metrics.get("error_count", 0)
        
        total = pattern_metrics.cache_hits + pattern_metrics.cache_misses
        if total > 0:
            pattern_metrics.success_rate = pattern_metrics.cache_hits / total

def get_java_pattern_match_result(
    pattern_name: str,
    matches: List[Dict[str, Any]],
    context: PatternContext
) -> PatternMatchResult:
    """Create a pattern match result with relationships and metrics."""
    return PatternMatchResult(
        pattern_name=pattern_name,
        matches=matches,
        context=context,
        relationships=get_java_pattern_relationships(pattern_name),
        performance=JAVA_PATTERN_METRICS.get(pattern_name, PatternPerformanceMetrics()),
        validation=PatternValidationResult(is_valid=True),
        metadata={"language": "java"}
    )

# Export public interfaces
__all__ = [
    'JAVA_PATTERNS',
    'JAVA_PATTERN_RELATIONSHIPS',
    'JAVA_PATTERN_METRICS',
    'create_pattern_context',
    'get_java_pattern_relationships',
    'update_java_pattern_metrics',
    'get_java_pattern_match_result'
]

class JavaPatternLearner(TreeSitterCrossProjectPatternLearner):
    """Pattern learner specialized for Java code."""
    
    def __init__(self):
        super().__init__(language_id=LANGUAGE)
        self.project_insights = defaultdict(dict)
        self.insights_path = os.path.join(DATA_DIR, "java_pattern_insights.json")
        os.makedirs(DATA_DIR, exist_ok=True)
        
    async def initialize(self):
        """Initialize with Java-specific components."""
        await super().initialize()  # Initialize TreeSitterCrossProjectPatternLearner components
        
        # Load previously saved insights
        await self._load_insights()
        
        # Initialize core components
        self._block_extractor = await self._factory.create_block_extractor(LANGUAGE)
        self._feature_extractor = await self._factory.create_feature_extractor(LANGUAGE)
        self._unified_parser = await self._factory.create_unified_parser(LANGUAGE)
        self._ai_processor = await self._factory.create_ai_pattern_processor(LANGUAGE)
        
        # Register Java patterns
        for category, purpose_dict in JAVA_PATTERNS.items():
            for purpose, patterns in purpose_dict.items():
                for name, pattern in patterns.items():
                    pattern_key = f"{category}:{purpose}:{name}"
                    await register_pattern(pattern_key, pattern)
        
        # Initialize health monitoring
        await global_health_monitor.update_component_status(
            "java_pattern_learner",
            ComponentStatus.HEALTHY,
            details={
                "patterns_loaded": len(JAVA_PATTERNS),
                "capabilities": list(JAVA_CAPABILITIES),
                "insights_loaded": len(self.project_insights) if hasattr(self, "project_insights") else 0
            }
        )
    
    async def _load_insights(self):
        """Load insights from the saved file."""
        try:
            if os.path.exists(self.insights_path):
                with open(self.insights_path, 'r') as f:
                    data = json.load(f)
                    self.project_insights = defaultdict(dict, data)
                    
                # Log the load operation
                logger = log(__name__)
                logger.info(f"Loaded {len(self.project_insights)} Java pattern insights from {self.insights_path}")
            else:
                # Initialize empty insights if file doesn't exist
                self.project_insights = defaultdict(dict)
        except Exception as e:
            # Handle any errors during loading
            logger = log(__name__)
            logger.error(f"Error loading Java pattern insights: {str(e)}")
            self.project_insights = defaultdict(dict)
    
    async def _save_insights(self):
        """Save insights to a file."""
        try:
            # Prepare data for serialization (convert defaultdict to dict)
            data_to_save = dict(self.project_insights)
            
            # Save to file
            with open(self.insights_path, 'w') as f:
                json.dump(data_to_save, f, indent=2)
                
            # Log the save operation
            logger = log(__name__)
            logger.info(f"Saved {len(self.project_insights)} Java pattern insights to {self.insights_path}")
            
            return True
        except Exception as e:
            # Handle any errors during saving
            logger = log(__name__)
            logger.error(f"Error saving Java pattern insights: {str(e)}")
            return False
    
    async def cleanup(self):
        """Clean up resources."""
        # Save insights before cleaning up
        await self._save_insights()
        
        # Clean up other resources
        if hasattr(self, '_block_extractor'):
            await self._block_extractor.cleanup()
        if hasattr(self, '_feature_extractor'):
            await self._feature_extractor.cleanup()
        if hasattr(self, '_unified_parser'):
            await self._unified_parser.cleanup()
        if hasattr(self, '_ai_processor'):
            await self._ai_processor.cleanup()
            
        await super().cleanup()
    
    async def learn_from_project(self, project_id: str, code_blocks: List[Dict[str, Any]]):
        """Learn patterns from project-specific code blocks."""
        start_time = time.time()
        
        # Process each code block
        insights = {}
        for block in code_blocks:
            if block["language"].lower() != LANGUAGE.lower():
                continue
                
            # Extract features
            block_features = await self._feature_extractor.extract_features(block["content"])
            
            # Analyze patterns
            pattern_matches = await self._unified_parser.parse_content(
                block["content"], 
                create_pattern_context(project_id=project_id)
            )
            
            # Process insights
            for match in pattern_matches:
                pattern_name = match.get("pattern_name", "unknown")
                if pattern_name not in insights:
                    insights[pattern_name] = {
                        "count": 0,
                        "contexts": [],
                        "features": []
                    }
                
                insights[pattern_name]["count"] += 1
                insights[pattern_name]["contexts"].append(match.get("context", {}))
                insights[pattern_name]["features"].append(block_features)
        
        # Update project insights
        if project_id not in self.project_insights:
            self.project_insights[project_id] = {}
            
        self.project_insights[project_id].update(insights)
        
        # Log performance
        elapsed_time = time.time() - start_time
        logger = log(__name__)
        logger.info(f"Learned {len(insights)} Java patterns from project {project_id} in {elapsed_time:.2f}s")
        
        return {"patterns_learned": len(insights), "processing_time": elapsed_time}
    
    async def apply_learnings(self):
        """Apply learned insights to improve pattern matching."""
        # Implement pattern refinement logic here
        pass

# Initialize pattern learner
java_pattern_learner = JavaPatternLearner()

@handle_async_errors(error_types=ProcessingError)
async def process_java_pattern(
    pattern: Union[TreeSitterAdaptivePattern, TreeSitterResilientPattern],
    source_code: str,
    context: Optional[PatternContext] = None
) -> List[Dict[str, Any]]:
    """Process a Java pattern with full system integration."""
    async with AsyncErrorBoundary(
        operation_name=f"process_pattern_{pattern.name}",
        error_types=ProcessingError,
        severity=ErrorSeverity.ERROR
    ):
        # Get all required components
        block_extractor = await get_block_extractor()
        feature_extractor = await BaseFeatureExtractor.create("java", FileType.CODE)
        unified_parser = await get_unified_parser()
        
        # Parse if needed
        if not context or not context.code_structure:
            parse_result = await unified_parser.parse(source_code, "java", FileType.CODE)
            if parse_result and parse_result.ast:
                context = await create_pattern_context(
                    "",
                    parse_result.ast
                )
        
        # Extract and process blocks
        blocks = await block_extractor.get_child_blocks(
            "java",
            source_code,
            context.code_structure if context else None
        )
        
        # Process blocks and extract features
        matches = []
        start_time = time.time()
        
        for block in blocks:
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
        
        # Update pattern metrics
        await update_java_pattern_metrics(
            pattern.name,
            {
                "execution_time": time.time() - start_time,
                "matches": len(matches)
            }
        )
        
        return matches

# Update initialization
async def initialize_java_patterns():
    """Initialize Java patterns during app startup."""
    global java_pattern_learner
    
    # Initialize pattern processor first
    await pattern_processor.initialize()
    
    # Register Java patterns
    await pattern_processor.register_language_patterns(
        "java",
        JAVA_PATTERNS,
        metadata={
            "parser_type": ParserType.TREE_SITTER,
            "supports_learning": True,
            "supports_adaptation": True,
            "capabilities": JAVA_CAPABILITIES
        }
    )
    
    # Create and initialize learner
    java_pattern_learner = await JavaPatternLearner.create()
    
    # Register learner with pattern processor
    await pattern_processor.register_pattern_learner(
        "java",
        java_pattern_learner
    )
    
    await global_health_monitor.update_component_status(
        "java_patterns",
        ComponentStatus.HEALTHY,
        details={
            "patterns_loaded": len(JAVA_PATTERNS),
            "capabilities": list(JAVA_CAPABILITIES)
        }
    )

async def extract_java_features(
    pattern: Union[TreeSitterAdaptivePattern, TreeSitterResilientPattern],
    matches: List[Dict[str, Any]],
    context: PatternContext
) -> ExtractedFeatures:
    """Extract features from pattern matches."""
    feature_extractor = await BaseFeatureExtractor.create("java", FileType.CODE)
    
    features = ExtractedFeatures()
    
    for match in matches:
        # Extract features based on pattern category
        if pattern.category == PatternCategory.SYNTAX:
            syntax_features = await feature_extractor._extract_syntax_features(
                match,
                context
            )
            features.update(syntax_features)
            
        elif pattern.category == PatternCategory.SEMANTICS:
            semantic_features = await feature_extractor._extract_semantic_features(
                match,
                context
            )
            features.update(semantic_features)
    
    return features

async def validate_java_pattern(
    pattern: Union[TreeSitterAdaptivePattern, TreeSitterResilientPattern],
    context: Optional[PatternContext] = None
) -> PatternValidationResult:
    """Validate a Java pattern with system integration."""
    async with AsyncErrorBoundary("java_pattern_validation"):
        # Get pattern processor
        validation_result = await pattern_processor.validate_pattern(
            pattern,
            language_id="java",
            context=context
        )
        
        # Update pattern metrics
        if not validation_result.is_valid:
            pattern_metrics = JAVA_PATTERN_METRICS.get(pattern.name)
            if pattern_metrics:
                pattern_metrics.error_count += 1
        
        return validation_result 