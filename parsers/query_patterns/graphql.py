"""Query patterns for GraphQL files with enhanced pattern support.

This module provides GraphQL-specific patterns that integrate with the enhanced
pattern processing system, including proper typing, relationships, and context.
"""

import re
from typing import Dict, Any, List, Optional, Union, Match
from dataclasses import dataclass, field
from parsers.types import (
    PatternCategory, PatternPurpose, PatternType, PatternRelationType,
    PatternContext, PatternRelationship, PatternPerformanceMetrics,
    PatternValidationResult, PatternMatchResult, QueryPattern,
    AICapability, AIContext, AIProcessingResult, InteractionType,
    ExtractedFeatures, FileType, ParserType
)
from parsers.models import PATTERN_CATEGORIES
from .common import COMMON_PATTERNS, COMMON_CAPABILITIES, process_common_pattern
from .enhanced_patterns import TreeSitterAdaptivePattern, TreeSitterResilientPattern, TreeSitterCrossProjectPatternLearner
from utils.error_handling import AsyncErrorBoundary, handle_async_errors, ProcessingError, ErrorSeverity
from utils.health_monitor import monitor_operation, global_health_monitor, ComponentStatus
from utils.request_cache import cached_in_request, get_current_request_cache
from utils.cache_analytics import get_cache_analytics
from utils.async_runner import submit_async_task, cleanup_tasks
from utils.logger import log
from utils.shutdown import register_shutdown_handler
import asyncio
from parsers.block_extractor import get_block_extractor
from parsers.feature_extractor import FeatureExtractor
from parsers.unified_parser import get_unified_parser
from parsers.base_parser import BaseParser
from parsers.tree_sitter_parser import get_tree_sitter_parser
from parsers.ai_pattern_processor import get_ai_pattern_processor
import time

# Module identification
LANGUAGE = "graphql"

# GraphQL capabilities (extends common capabilities)
GRAPHQL_CAPABILITIES = COMMON_CAPABILITIES | {
    AICapability.API_DESIGN,
    AICapability.SCHEMA_VALIDATION,
    AICapability.TYPE_SYSTEM
}

# Performance metrics tracking for GraphQL patterns
GRAPHQL_PATTERN_METRICS = {
    "operation": PatternPerformanceMetrics(
        execution_time=0.0,
        memory_usage=0,
        cache_hits=0,
        cache_misses=0,
        error_count=0,
        success_rate=0.0,
        pattern_stats={"matches": 0, "failures": 0}
    ),
    "fragment": PatternPerformanceMetrics(
        execution_time=0.0,
        memory_usage=0,
        cache_hits=0,
        cache_misses=0,
        error_count=0,
        success_rate=0.0,
        pattern_stats={"matches": 0, "failures": 0}
    ),
    "type_definition": PatternPerformanceMetrics(
        execution_time=0.0,
        memory_usage=0,
        cache_hits=0,
        cache_misses=0,
        error_count=0,
        success_rate=0.0,
        pattern_stats={"matches": 0, "failures": 0}
    )
}

def extract_type(match: Match) -> Dict[str, Any]:
    """Extract type definition information."""
    return {
        "type": "type_definition",
        "name": match.group(1),
        "fields": match.group(2),
        "line_number": match.string.count('\n', 0, match.start()) + 1
    }

def extract_field(match: Match) -> Dict[str, Any]:
    """Extract field information."""
    return {
        "type": "field",
        "name": match.group(1),
        "field_type": match.group(2),
        "line_number": match.string.count('\n', 0, match.start()) + 1
    }

def extract_argument(match: Match) -> Dict[str, Any]:
    """Extract argument information."""
    return {
        "type": "argument",
        "name": match.group(1),
        "arg_type": match.group(2),
        "line_number": match.string.count('\n', 0, match.start()) + 1
    }

GRAPHQL_PATTERNS = {
    **COMMON_PATTERNS,  # Keep as fallback for basic patterns
    
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "operation": QueryPattern(
                name="operation",
                pattern="""
                [
                    (operation_definition
                        operation_type: (_)? @syntax.operation.type
                        name: (name)? @syntax.operation.name
                        variable_definitions: (variable_definitions)? @syntax.operation.vars
                        selection_set: (selection_set) @syntax.operation.selections) @syntax.operation.def
                ]
                """,
                extract=lambda node: {
                    "name": node["captures"].get("syntax.operation.name", {}).get("text", ""),
                    "type": node["captures"].get("syntax.operation.type", {}).get("text", "query"),
                    "has_vars": bool(node["captures"].get("syntax.operation.vars", {}))
                },
                metadata={
                    "description": "Matches GraphQL operation definitions",
                    "examples": [
                        "query GetUser { user { name } }",
                        "mutation CreateUser($name: String!) { createUser(name: $name) { id } }"
                    ]
                },
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE
            ),
            "fragment": QueryPattern(
                name="fragment",
                pattern="""
                [
                    (fragment_definition
                        name: (name) @syntax.fragment.name
                        type_condition: (type_condition
                            type: (named_type) @syntax.fragment.type)
                        selection_set: (selection_set) @syntax.fragment.selections) @syntax.fragment.def
                ]
                """,
                extract=lambda node: {
                    "name": node["captures"].get("syntax.fragment.name", {}).get("text", ""),
                    "type": node["captures"].get("syntax.fragment.type", {}).get("text", "")
                },
                metadata={
                    "description": "Matches GraphQL fragment definitions",
                    "examples": [
                        "fragment UserFields on User { name email }"
                    ]
                },
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE
            )
        },
        "type_definition": QueryPattern(
            name="type_definition",
            pattern=r'type\\s+(\\w+)\\s*\\{([^}]+)\\}',
            extract=extract_type,
            metadata={
                "description": "Matches GraphQL type definitions",
                "examples": ["type User { id: ID! name: String }"]
            },
            category=PatternCategory.SYNTAX,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE
        ),
        "interface": QueryPattern(
            name="interface",
            pattern=r'interface\\s+(\\w+)\\s*\\{([^}]+)\\}',
            extract=lambda m: {
                "type": "interface",
                "name": m.group(1),
                "fields": m.group(2),
                "line_number": m.string.count('\\n', 0, m.start()) + 1
            },
            metadata={
                "description": "Matches GraphQL interfaces",
                "examples": ["interface Node { id: ID! }"]
            },
            category=PatternCategory.SYNTAX,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE
        ),
        "enum": QueryPattern(
            name="enum",
            pattern=r'enum\\s+(\\w+)\\s*\\{([^}]+)\\}',
            extract=lambda m: {
                "type": "enum",
                "name": m.group(1),
                "values": m.group(2),
                "line_number": m.string.count('\\n', 0, m.start()) + 1
            },
            metadata={
                "description": "Matches GraphQL enums",
                "examples": ["enum Role { USER ADMIN }"]
            },
            category=PatternCategory.SYNTAX,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE
        ),
        "input": QueryPattern(
            name="input",
            pattern=r'input\\s+(\\w+)\\s*\\{([^}]+)\\}',
            extract=lambda m: {
                "type": "input",
                "name": m.group(1),
                "fields": m.group(2),
                "line_number": m.string.count('\\n', 0, m.start()) + 1
            },
            metadata={
                "description": "Matches GraphQL input types",
                "examples": ["input UserInput { name: String! }"]
            },
            category=PatternCategory.SYNTAX,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE
        )
    },
    
    PatternCategory.STRUCTURE: {
        "field": QueryPattern(
            name="field",
            pattern=r'(\w+)(?:\(([^)]+)\))?\s*:\s*([\w\[\]!]+)',
            extract=extract_field,
            metadata={
                "description": "Matches GraphQL fields",
                "examples": ["name: String", "age: Int!"]
            },
            category=PatternCategory.STRUCTURE,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE
        ),
        "argument": QueryPattern(
            name="argument",
            pattern=r'(\w+):\s*([\w\[\]!]+)(?:\s*=\s*([^,\s]+))?',
            extract=extract_argument,
            metadata={
                "description": "Matches GraphQL arguments",
                "examples": ["id: ID!", "limit: Int = 10"]
            },
            category=PatternCategory.STRUCTURE,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE
        ),
        "directive": QueryPattern(
            name="directive",
            pattern=r'@(\w+)(?:\(([^)]+)\))?',
            extract=lambda m: {
                "type": "directive",
                "name": m.group(1),
                "arguments": m.group(2) if m.group(2) else None,
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            metadata={
                "description": "Matches GraphQL directives",
                "examples": ["@deprecated", "@include(if: $flag)"]
            },
            category=PatternCategory.STRUCTURE,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE
        )
    },
    
    PatternCategory.DOCUMENTATION: {
        PatternPurpose.UNDERSTANDING: {
            "description": QueryPattern(
                name="description",
                pattern="""
                [
                    (description) @documentation.desc
                ]
                """,
                extract=lambda node: {
                    "text": node["text"].strip('"\' ')
                },
                metadata={
                    "description": "Matches GraphQL descriptions",
                    "examples": [
                        '"""User type"""',
                        '"User ID field"'
                    ]
                },
                category=PatternCategory.DOCUMENTATION,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE
            )
        },
        "comment": QueryPattern(
            name="comment",
            pattern=r'#\s*(.+)$',
            extract=lambda m: {
                "type": "comment",
                "content": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            metadata={
                "description": "Matches GraphQL comments",
                "examples": ["# This is a comment"]
            },
            category=PatternCategory.DOCUMENTATION,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE
        ),
        "deprecated": QueryPattern(
            name="deprecated",
            pattern=r'@deprecated\\(reason:\s*"([^"]+)"\\)',
            extract=lambda m: {
                "type": "deprecated",
                "reason": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            metadata={
                "description": "Matches deprecation notices",
                "examples": ["@deprecated(reason: \"Use newField instead\")"]
            },
            category=PatternCategory.DOCUMENTATION,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE
        )
    },
    
    PatternCategory.SEMANTICS: {
        PatternPurpose.UNDERSTANDING: {
            "field": QueryPattern(
                name="field",
                pattern="""
                [
                    (field
                        alias: (name)? @semantics.field.alias
                        name: (name) @semantics.field.name
                        arguments: (arguments)? @semantics.field.args
                        selection_set: (selection_set)? @semantics.field.selections) @semantics.field.def
                ]
                """,
                extract=lambda node: {
                    "name": node["captures"].get("semantics.field.name", {}).get("text", ""),
                    "alias": node["captures"].get("semantics.field.alias", {}).get("text", ""),
                    "has_args": bool(node["captures"].get("semantics.field.args", {})),
                    "has_selections": bool(node["captures"].get("semantics.field.selections", {}))
                },
                metadata={
                    "description": "Matches GraphQL field selections",
                    "examples": [
                        "user { name }",
                        "userById(id: 123) { name email }"
                    ]
                },
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE
            ),
            "type": QueryPattern(
                name="type",
                pattern="""
                [
                    (type_definition
                        description: (description)? @semantics.type.desc
                        name: (name) @semantics.type.name
                        implements: (implements_interfaces)? @semantics.type.interfaces
                        fields: (field_definition)* @semantics.type.fields) @semantics.type.def
                ]
                """,
                extract=lambda node: {
                    "name": node["captures"].get("semantics.type.name", {}).get("text", ""),
                    "has_desc": bool(node["captures"].get("semantics.type.desc", {})),
                    "has_interfaces": bool(node["captures"].get("semantics.type.interfaces", {}))
                },
                metadata={
                    "description": "Matches GraphQL type definitions",
                    "examples": [
                        "type User { id: ID! name: String! }",
                        "type Query { user(id: ID!): User }"
                    ]
                },
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE
            )
        },
        "scalar": QueryPattern(
            name="scalar",
            pattern=r'scalar\s+(\w+)',
            extract=lambda m: {
                "type": "scalar",
                "name": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            metadata={
                "description": "Matches scalar type definitions",
                "examples": ["scalar DateTime"]
            },
            category=PatternCategory.SEMANTICS,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE
        ),
        "union": QueryPattern(
            name="union",
            pattern=r'union\s+(\w+)\s*=\s*([^\{\n]+)',
            extract=lambda m: {
                "type": "union",
                "name": m.group(1),
                "types": [t.strip() for t in m.group(2).split('|')],
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            metadata={
                "description": "Matches union type definitions",
                "examples": ["union SearchResult = User | Post"]
            },
            category=PatternCategory.SEMANTICS,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE
        ),
        "implements": QueryPattern(
            name="implements",
            pattern=r'type\s+(\w+)\s+implements\s+([^\{]+)',
            extract=lambda m: {
                "type": "implements",
                "type_name": m.group(1),
                "interfaces": [i.strip() for i in m.group(2).split('&')],
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            metadata={
                "description": "Matches interface implementations",
                "examples": ["type User implements Node & Entity"]
            },
            category=PatternCategory.SEMANTICS,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE
        )
    },
    
    PatternCategory.CODE_PATTERNS: {
        "query": QueryPattern(
            name="query",
            pattern=r'(?:query|mutation|subscription)\s+(\w+)(?:\(([^)]+)\))?\s*\{([^}]+)\}',
            extract=lambda m: {
                "type": "operation",
                "name": m.group(1),
                "arguments": m.group(2) if m.group(2) else None,
                "body": m.group(3),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            metadata={
                "description": "Matches GraphQL operations",
                "examples": ["query GetUser($id: ID!) { user(id: $id) { name } }"]
            },
            category=PatternCategory.CODE_PATTERNS,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE
        ),
        "fragment": QueryPattern(
            name="fragment",
            pattern=r'fragment\s+(\w+)\s+on\s+(\w+)\s*\{([^}]+)\}',
            extract=lambda m: {
                "type": "fragment",
                "name": m.group(1),
                "on_type": m.group(2),
                "body": m.group(3),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            metadata={
                "description": "Matches GraphQL fragments",
                "examples": ["fragment UserFields on User { name email }"]
            },
            category=PatternCategory.CODE_PATTERNS,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE
        ),
        "type_patterns": QueryPattern(
            name="type_patterns",
            pattern=r'type\s+(\w+)(?:\s+implements[^\{]+)?\s*\{([^}]+)\}',
            extract=lambda m: {
                "type": "type_pattern",
                "name": m.group(1),
                "body": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "has_interfaces": "implements" in m.group(0)
            },
            metadata={
                "description": "Learns type definition patterns",
                "examples": ["type User { id: ID! }", "type Post implements Node { id: ID! }"]
            },
            category=PatternCategory.CODE_PATTERNS,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE
        ),
        "operation_patterns": QueryPattern(
            name="operation_patterns",
            pattern=r'(?:query|mutation|subscription)\s+(\w+)(?:\([^)]+\))?\s*\{([^}]+)\}',
            extract=lambda m: {
                "type": "operation_pattern",
                "name": m.group(1),
                "body": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "operation_type": re.match(r'(query|mutation|subscription)', m.group(0)).group(1)
            },
            metadata={
                "description": "Learns operation patterns",
                "examples": ["query GetUser { user { name } }", "mutation UpdateUser { updateUser { id } }"]
            },
            category=PatternCategory.CODE_PATTERNS,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE
        )
    },
    
    PatternCategory.DEPENDENCIES: {
        "type_reference": QueryPattern(
            name="type_reference",
            pattern=r':\s*([\w\[\]!]+)',
            extract=lambda m: {
                "type": "type_reference",
                "referenced_type": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "is_required": m.group(1).endswith('!')
            },
            metadata={
                "description": "Matches type references",
                "examples": ["name: String!", "posts: [Post]"]
            },
            category=PatternCategory.DEPENDENCIES,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE
        ),
        "fragment_spread": QueryPattern(
            name="fragment_spread",
            pattern=r'\.\.\.\s*(\w+)',
            extract=lambda m: {
                "type": "fragment_spread",
                "fragment_name": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            metadata={
                "description": "Matches fragment spreads",
                "examples": ["...UserFields"]
            },
            category=PatternCategory.DEPENDENCIES,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE
        )
    },
    
    PatternCategory.BEST_PRACTICES: {
        "naming_convention": QueryPattern(
            name="naming_convention",
            pattern=r'type\s+([A-Z][a-zA-Z]*)',
            extract=lambda m: {
                "type": "naming_convention",
                "name": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "follows_convention": bool(re.match(r'^[A-Z][a-zA-Z]*$', m.group(1)))
            },
            metadata={
                "description": "Checks type naming conventions",
                "examples": ["type User", "type badName"]
            },
            category=PatternCategory.BEST_PRACTICES,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE
        ),
        "field_nullability": QueryPattern(
            name="field_nullability",
            pattern=r'(\w+):\s*([\w\[\]!]+)',
            extract=lambda m: {
                "type": "field_nullability",
                "field": m.group(1),
                "field_type": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "is_nullable": not m.group(2).endswith('!')
            },
            metadata={
                "description": "Checks field nullability",
                "examples": ["id: ID!", "name: String"]
            },
            category=PatternCategory.BEST_PRACTICES,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE
        )
    },
    
    PatternCategory.COMMON_ISSUES: {
        "invalid_field": QueryPattern(
            name="invalid_field",
            pattern=r'{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*{([^}]*)}',
            extract=lambda m: {
                "type": "invalid_field",
                "type_name": m.group(1),
                "fields": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "needs_verification": True
            },
            category=PatternCategory.COMMON_ISSUES,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            metadata={"description": "Detects potentially invalid fields", "examples": ["{ User { invalid } }"]}
        ),
        "type_mismatch": QueryPattern(
            name="type_mismatch",
            pattern=r'([a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*([a-zA-Z_][a-zA-Z0-9_]*!?(?:\[[^\]]*\])?)',
            extract=lambda m: {
                "type": "type_mismatch",
                "field": m.group(1),
                "type_name": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "needs_verification": True
            },
            category=PatternCategory.COMMON_ISSUES,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            metadata={"description": "Detects potential type mismatches", "examples": ["field: String!"]}
        ),
        "circular_fragment": QueryPattern(
            name="circular_fragment",
            pattern=r'fragment\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+on\s+[a-zA-Z_][a-zA-Z0-9_]*\s*{[^}]*\.\.\.\1',
            extract=lambda m: {
                "type": "circular_fragment",
                "fragment": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "confidence": 0.95
            },
            category=PatternCategory.COMMON_ISSUES,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            metadata={"description": "Detects circular fragment spreads", "examples": ["fragment Foo on Type { ...Foo }"]}
        ),
        "unused_fragment": QueryPattern(
            name="unused_fragment",
            pattern=r'fragment\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+on\s+[a-zA-Z_][a-zA-Z0-9_]*\s*{[^}]*}(?!.*\.\.\.\1)',
            extract=lambda m: {
                "type": "unused_fragment",
                "fragment": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "confidence": 0.85
            },
            category=PatternCategory.COMMON_ISSUES,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            metadata={"description": "Detects potentially unused fragments", "examples": ["fragment Unused on Type { field }"]}
        ),
        "invalid_argument": QueryPattern(
            name="invalid_argument",
            pattern=r'([a-zA-Z_][a-zA-Z0-9_]*)\s*\(([^)]*)\)',
            extract=lambda m: {
                "type": "invalid_argument",
                "field": m.group(1),
                "args": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "needs_verification": True
            },
            category=PatternCategory.COMMON_ISSUES,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            metadata={"description": "Detects potentially invalid arguments", "examples": ["field(invalid: value)"]}
        )
    },
    
    PatternCategory.USER_PATTERNS: {
        "custom_directive": QueryPattern(
            name="custom_directive",
            pattern=r'directive\s+@(\w+)\s*(?:\(([^)]+)\))?\s+on\s+([^\n]+)',
            extract=lambda m: {
                "type": "custom_directive",
                "name": m.group(1),
                "arguments": m.group(2) if m.group(2) else None,
                "locations": [l.strip() for l in m.group(3).split('|')],
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            metadata={
                "description": "Matches custom directive definitions",
                "examples": ["directive @auth(requires: Role!) on FIELD_DEFINITION"]
            },
            category=PatternCategory.USER_PATTERNS,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE
        ),
        "custom_scalar": QueryPattern(
            name="custom_scalar",
            pattern=r'scalar\s+(\w+)(?:\s+@[^\n]+)?',
            extract=lambda m: {
                "type": "custom_scalar",
                "name": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            metadata={
                "description": "Matches custom scalar definitions",
                "examples": ["scalar DateTime @specifiedBy(url: \"url\")"]
            },
            category=PatternCategory.USER_PATTERNS,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE
        )
    }
}

# Function to extract patterns for repository learning
def extract_graphql_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """Extract patterns from GraphQL content for repository learning."""
    patterns = []
    
    # Process each pattern category
    for category in PatternCategory:
        if category in GRAPHQL_PATTERNS:
            category_patterns = GRAPHQL_PATTERNS[category]
            for pattern_name, pattern in category_patterns.items():
                if isinstance(pattern, QueryPattern):
                    if isinstance(pattern.pattern, str):
                        for match in re.finditer(pattern.pattern, content, re.MULTILINE | re.DOTALL):
                            pattern_data = pattern.extract(match)
                            patterns.append({
                                "name": pattern_name,
                                "category": category.value,
                                "content": match.group(0),
                                "metadata": pattern_data,
                                "confidence": 0.85
                            })
    
    return patterns

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "schema": {
        "can_contain": ["type", "interface", "enum", "input", "scalar", "union", "directive"],
        "can_be_contained_by": []
    },
    "type": {
        "can_contain": ["field", "directive"],
        "can_be_contained_by": ["schema"]
    },
    "interface": {
        "can_contain": ["field", "directive"],
        "can_be_contained_by": ["schema"]
    },
    "field": {
        "can_contain": ["argument", "directive"],
        "can_be_contained_by": ["type", "interface", "input"]
    },
    "operation": {
        "can_contain": ["field", "fragment_spread", "directive"],
        "can_be_contained_by": ["schema"]
    }
}

def extract_graphql_features(ast: dict) -> dict:
    """Extract features that align with pattern categories."""
    features = {
        "syntax": {
            "types": [],
            "interfaces": [],
            "enums": [],
            "inputs": []
        },
        "structure": {
            "fields": [],
            "arguments": [],
            "directives": []
        },
        "semantics": {
            "scalars": [],
            "unions": [],
            "implementations": []
        },
        "documentation": {
            "descriptions": [],
            "comments": [],
            "deprecations": []
        }
    }
    return features 

class GraphQLPatternLearner(TreeSitterCrossProjectPatternLearner):
    """Enhanced GraphQL pattern learner with cross-project learning capabilities."""
    
    def __init__(self):
        super().__init__()
        self._feature_extractor = None
        self._pattern_processor = None
        self._ai_processor = None
        self._block_extractor = None
        self._unified_parser = None
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
        """Initialize with GraphQL-specific components."""
        await super().initialize()  # Initialize TreeSitterCrossProjectPatternLearner components
        
        # Initialize core components
        self._block_extractor = await get_block_extractor()
        self._feature_extractor = FeatureExtractor("graphql")
        self._unified_parser = await get_unified_parser()
        self._ai_processor = await get_ai_pattern_processor()
        from parsers.pattern_processor import pattern_processor
        self._pattern_processor = pattern_processor
        
        # Register GraphQL patterns
        await self._pattern_processor.register_language_patterns(
            "graphql", 
            GRAPHQL_PATTERNS,
            self
        )
        
        # Initialize health monitoring
        await global_health_monitor.update_component_status(
            "graphql_pattern_learner",
            ComponentStatus.HEALTHY,
            details={
                "patterns_loaded": len(GRAPHQL_PATTERNS),
                "capabilities": list(GRAPHQL_CAPABILITIES)
            }
        )

    async def learn_from_project(self, project_path: str) -> List[Dict[str, Any]]:
        """Learn patterns with cross-project and AI assistance."""
        start_time = time.time()
        self._metrics["total_patterns"] += 1
        
        try:
            # First try AI-assisted learning
            ai_context = AIContext(
                language_id="graphql",
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
            
            # Finally add GraphQL-specific patterns
            async with AsyncErrorBoundary("graphql_pattern_learning"):
                # Extract blocks with caching
                blocks = await self._block_extractor.get_child_blocks(
                    "graphql",
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
                graphql_patterns = await self._learn_patterns_from_features(features)
                learned_patterns.extend(graphql_patterns)
            
            # Update metrics
            learning_time = time.time() - start_time
            self._metrics["learning_times"].append(learning_time)
            
            # Update health status
            await global_health_monitor.update_component_status(
                "graphql_pattern_learner",
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
                "graphql_pattern_learner",
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
            if self._feature_extractor:
                await self._feature_extractor.cleanup()
            if self._block_extractor:
                await self._block_extractor.cleanup()
            if self._unified_parser:
                await self._unified_parser.cleanup()
            if self._ai_processor:
                await self._ai_processor.cleanup()
            
            # Update final status
            await global_health_monitor.update_component_status(
                "graphql_pattern_learner",
                ComponentStatus.SHUTDOWN,
                details={
                    "cleanup": "successful",
                    "final_metrics": self._metrics
                }
            )
            
        except Exception as e:
            await log(f"Error in cleanup: {e}", level="error")
            await global_health_monitor.update_component_status(
                "graphql_pattern_learner",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"cleanup_error": str(e)}
            )

@handle_async_errors(error_types=ProcessingError)
async def process_graphql_pattern(
    pattern: Union[TreeSitterAdaptivePattern, TreeSitterResilientPattern],
    source_code: str,
    context: Optional[PatternContext] = None
) -> List[Dict[str, Any]]:
    """Process a GraphQL pattern with full system integration."""
    # First try common pattern processing
    common_result = await process_common_pattern(pattern, source_code, context)
    if common_result:
        return common_result
    
    # Fall back to GraphQL-specific processing
    async with AsyncErrorBoundary(
        operation_name=f"process_pattern_{pattern.name}",
        error_types=ProcessingError,
        severity=ErrorSeverity.ERROR
    ):
        # Get all required components
        block_extractor = await get_block_extractor()
        feature_extractor = FeatureExtractor("graphql")
        unified_parser = await get_unified_parser()
        
        # Parse if needed
        if not context or not context.code_structure:
            parse_result = await unified_parser.parse(source_code, "graphql", FileType.CODE)
            if parse_result and parse_result.ast:
                context = await create_graphql_pattern_context(
                    "",
                    parse_result.ast
                )
        
        # Extract and process blocks with caching
        cache_key = f"graphql_pattern_{pattern.name}_{hash(source_code)}"
        cached_result = await get_current_request_cache().get(cache_key)
        if cached_result:
            return cached_result
        
        blocks = await block_extractor.get_child_blocks(
            "graphql",
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
        
        # Cache the result
        await get_current_request_cache().set(cache_key, matches)
        
        # Update pattern metrics
        await update_graphql_pattern_metrics(
            pattern.name,
            {
                "execution_time": time.time() - start_time,
                "matches": len(matches)
            }
        )
        
        # Update health status
        await global_health_monitor.update_component_status(
            "graphql_pattern_processor",
            ComponentStatus.HEALTHY,
            details={
                "pattern": pattern.name,
                "matches": len(matches),
                "processing_time": time.time() - start_time
            }
        )
        
        return matches

async def create_graphql_pattern_context(
    file_path: str,
    code_structure: Dict[str, Any],
    learned_patterns: Optional[Dict[str, Any]] = None
) -> PatternContext:
    """Create pattern context with full system integration."""
    # Get unified parser
    unified_parser = await get_unified_parser()
    
    # Parse the code structure if needed
    if not code_structure:
        parse_result = await unified_parser.parse(
            file_path,
            language_id="graphql",
            file_type=FileType.CODE
        )
        code_structure = parse_result.ast if parse_result else {}
    
    context = PatternContext(
        code_structure=code_structure,
        language_stats={"language": "graphql"},
        project_patterns=list(learned_patterns.values()) if learned_patterns else [],
        file_location=file_path,
        dependencies=set(),
        recent_changes=[],
        scope_level="global",
        allows_nesting=True,
        relevant_patterns=list(GRAPHQL_PATTERNS.keys())
    )
    
    # Add system integration metadata
    context.metadata.update({
        "parser_type": ParserType.TREE_SITTER,
        "feature_extraction_enabled": True,
        "block_extraction_enabled": True,
        "pattern_learning_enabled": True
    })
    
    return context

# Initialize pattern learner
graphql_pattern_learner = GraphQLPatternLearner()

async def initialize_graphql_patterns():
    """Initialize GraphQL patterns during app startup."""
    global graphql_pattern_learner
    from parsers.pattern_processor import pattern_processor
    await pattern_processor.initialize()
    await pattern_processor.register_language_patterns(
        "graphql",
        GRAPHQL_PATTERNS,
        metadata={
            "parser_type": ParserType.TREE_SITTER,
            "supports_learning": True,
            "supports_adaptation": True,
            "capabilities": GRAPHQL_CAPABILITIES
        }
    )
    graphql_pattern_learner = await GraphQLPatternLearner.create()
    await pattern_processor.register_pattern_learner(
        "graphql",
        graphql_pattern_learner
    )
    await global_health_monitor.update_component_status(
        "graphql_patterns",
        ComponentStatus.HEALTHY,
        details={
            "patterns_loaded": len(GRAPHQL_PATTERNS),
            "capabilities": list(GRAPHQL_CAPABILITIES)
        }
    )

async def update_graphql_pattern_metrics(pattern_name: str, metrics: Dict[str, Any]) -> None:
    """Update metrics for a specific GraphQL pattern."""
    if pattern_name in GRAPHQL_PATTERN_METRICS:
        pattern_metrics = GRAPHQL_PATTERN_METRICS[pattern_name]
        pattern_metrics.execution_time = metrics.get("execution_time", pattern_metrics.execution_time)
        pattern_metrics.pattern_stats["matches"] += metrics.get("matches", 0)
        
        # Update success rate
        if pattern_metrics.pattern_stats["matches"] > 0:
            total = pattern_metrics.pattern_stats["matches"] + pattern_metrics.pattern_stats["failures"]
            pattern_metrics.success_rate = pattern_metrics.pattern_stats["matches"] / total if total > 0 else 0.0

# Export public interfaces
__all__ = [
    'GRAPHQL_PATTERNS',
    'PATTERN_RELATIONSHIPS',
    'GRAPHQL_PATTERN_METRICS',
    'extract_graphql_patterns_for_learning',
    'extract_graphql_features',
    'graphql_pattern_learner',
    'update_graphql_pattern_metrics'
] 