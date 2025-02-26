"""Query patterns for GraphQL files."""

from typing import Dict, Any, List, Match
from dataclasses import dataclass
from parsers.types import FileType, QueryPattern, PatternCategory
import re

def extract_type(match: Match) -> Dict[str, Any]:
    """Extract type information."""
    return {
        "name": match.group(1),
        "implements": match.group(2).strip() if match.group(2) else None,
        "line_number": match.string.count('\n', 0, match.start()) + 1
    }

def extract_field(match: Match) -> Dict[str, Any]:
    """Extract field information."""
    return {
        "type": "field",
        "name": match.group(1),
        "arguments": match.group(2),
        "return_type": match.group(3),
        "modifiers": match.group(4),
        "line_number": match.string.count('\n', 0, match.start()) + 1
    }

GRAPHQL_PATTERNS = {
    PatternCategory.SYNTAX: {
        "type": QueryPattern(
            pattern=r'type\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:implements\s+([a-zA-Z_][a-zA-Z0-9_,\s&|]*))?\s*{',
            extract=extract_type,
            description="Matches GraphQL type definitions",
            examples=["type User {", "type Product implements Node {"]
        ),
        "field": QueryPattern(
            pattern=r'([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:\(([^)]*)\))?\s*:\s*([!a-zA-Z_][!a-zA-Z0-9_\[\]]*)',
            extract=lambda m: {
                "name": m.group(1),
                "arguments": m.group(2) if m.group(2) else "",
                "field_type": m.group(3),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches GraphQL field definitions",
            examples=["name: String!", "products(first: Int): [Product!]"]
        )
    },
    
    PatternCategory.STRUCTURE: {
        "interface": QueryPattern(
            pattern=r'interface\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*{',
            extract=lambda m: {
                "name": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches GraphQL interface definitions",
            examples=["interface Node {"]
        ),
        "fragment": QueryPattern(
            pattern=r'fragment\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+on\s+([a-zA-Z_][a-zA-Z0-9_]*)',
            extract=lambda m: {
                "name": m.group(1),
                "on_type": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches GraphQL fragment definitions",
            examples=["fragment UserFields on User"]
        )
    },
    
    PatternCategory.DOCUMENTATION: {
        "description": QueryPattern(
            pattern=r'"""(.*?)"""',
            extract=lambda m: {
                "content": m.group(1).strip(),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches GraphQL descriptions",
            examples=['"""User type representing a registered user."""']
        ),
        "comment": QueryPattern(
            pattern=r'#\s*(.*)',
            extract=lambda m: {
                "content": m.group(1).strip(),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches GraphQL comments",
            examples=["# This is a comment"]
        )
    },
    
    PatternCategory.SEMANTICS: {
        "argument": QueryPattern(
            pattern=r'([a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*([a-zA-Z_][a-zA-Z0-9_\[\]!]*)',
            extract=lambda m: {
                "name": m.group(1),
                "type": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches GraphQL field argument definitions",
            examples=["id: ID!", "name: String"]
        ),
        "directive": QueryPattern(
            pattern=r'@([a-zA-Z_][a-zA-Z0-9_]*)(?:\(([^)]*)\))?',
            extract=lambda m: {
                "name": m.group(1),
                "arguments": m.group(2) if m.group(2) else "",
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches GraphQL directives",
            examples=["@deprecated", "@auth(requires: ADMIN)"]
        )
    }
}

# Add patterns for repository learning
GRAPHQL_PATTERNS_FOR_LEARNING = {
    "schema_patterns": {
        "query_type": QueryPattern(
            pattern=r'(?s)type\s+Query\s*{.*?}',
            extract=lambda m: {
                "type": "query_schema_pattern",
                "content": m.group(0),
                "has_query_type": True
            },
            description="Matches GraphQL Query type definitions",
            examples=["type Query { user(id: ID!): User }"]
        ),
        "mutation_type": QueryPattern(
            pattern=r'(?s)type\s+Mutation\s*{.*?}',
            extract=lambda m: {
                "type": "mutation_schema_pattern",
                "content": m.group(0),
                "has_mutation_type": True
            },
            description="Matches GraphQL Mutation type definitions",
            examples=["type Mutation { createUser(input: UserInput!): User }"]
        ),
        "subscription_type": QueryPattern(
            pattern=r'(?s)type\s+Subscription\s*{.*?}',
            extract=lambda m: {
                "type": "subscription_schema_pattern",
                "content": m.group(0),
                "has_subscription_type": True
            },
            description="Matches GraphQL Subscription type definitions",
            examples=["type Subscription { userUpdated: User }"]
        )
    },
    "type_patterns": {
        "connection_pattern": QueryPattern(
            pattern=r'(?s)type\s+(\w+Connection)\s*{.*?edges.*?nodes.*?}',
            extract=lambda m: {
                "type": "connection_pattern",
                "name": m.group(1),
                "follows_relay_spec": True
            },
            description="Matches Relay-style connection pattern",
            examples=["type UserConnection { edges: [UserEdge], nodes: [User], pageInfo: PageInfo }"]
        ),
        "input_pattern": QueryPattern(
            pattern=r'(?s)input\s+(\w+Input)\s*{.*?}',
            extract=lambda m: {
                "type": "input_pattern",
                "name": m.group(1),
                "is_input_type": True
            },
            description="Matches GraphQL input type pattern",
            examples=["input CreateUserInput { name: String!, email: String! }"]
        )
    },
    "naming_conventions": {
        "pascal_case_types": QueryPattern(
            pattern=r'type\s+([A-Z][a-zA-Z0-9]*)\s',
            extract=lambda m: {
                "type": "naming_convention",
                "convention": "pascal_case",
                "element_type": "type",
                "name": m.group(1),
                "follows_convention": True
            },
            description="Matches PascalCase type naming convention",
            examples=["type User {", "type ProductCategory {"]
        ),
        "camel_case_fields": QueryPattern(
            pattern=r'(?<={|\s)([a-z][a-zA-Z0-9]*)\s*(?:\(.*?\))?\s*:',
            extract=lambda m: {
                "type": "naming_convention",
                "convention": "camel_case",
                "element_type": "field",
                "name": m.group(1),
                "follows_convention": True
            },
            description="Matches camelCase field naming convention",
            examples=["firstName: String", "userProducts: [Product]"]
        )
    }
}

# Add the repository learning patterns to the main patterns
GRAPHQL_PATTERNS['REPOSITORY_LEARNING'] = GRAPHQL_PATTERNS_FOR_LEARNING

# Function to extract patterns for repository learning
def extract_graphql_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """Extract patterns from GraphQL content for repository learning."""
    patterns = []
    
    # Process schema patterns
    for pattern_name, pattern in GRAPHQL_PATTERNS_FOR_LEARNING["schema_patterns"].items():
        for match in re.finditer(pattern.pattern, content, re.MULTILINE | re.DOTALL):
            pattern_data = pattern.extract(match)
            patterns.append({
                "name": pattern_name,
                "type": pattern_data.get("type", "schema_pattern"),
                "content": match.group(0),
                "metadata": pattern_data,
                "confidence": 0.9
            })
    
    # Process type patterns
    for pattern_name, pattern in GRAPHQL_PATTERNS_FOR_LEARNING["type_patterns"].items():
        for match in re.finditer(pattern.pattern, content, re.MULTILINE | re.DOTALL):
            pattern_data = pattern.extract(match)
            patterns.append({
                "name": pattern_name,
                "type": pattern_data.get("type", "type_pattern"),
                "content": match.group(0),
                "metadata": pattern_data,
                "confidence": 0.85
            })
    
    # Process naming convention patterns
    for pattern_name, pattern in GRAPHQL_PATTERNS_FOR_LEARNING["naming_conventions"].items():
        for match in re.finditer(pattern.pattern, content, re.MULTILINE | re.DOTALL):
            pattern_data = pattern.extract(match)
            patterns.append({
                "name": pattern_name,
                "type": pattern_data.get("type", "naming_convention"),
                "content": match.group(0),
                "metadata": pattern_data,
                "confidence": 0.8
            })
            
    return patterns

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "type": {
        "can_contain": ["field", "description", "comment"],
        "can_be_contained_by": ["document"]
    },
    "interface": {
        "can_contain": ["field", "description", "comment"],
        "can_be_contained_by": ["document"]
    },
    "field": {
        "can_contain": ["argument", "directive"],
        "can_be_contained_by": ["type", "interface"]
    },
    "fragment": {
        "can_contain": ["field"],
        "can_be_contained_by": ["document"]
    }
} 