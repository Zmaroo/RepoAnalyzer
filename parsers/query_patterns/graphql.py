"""Query patterns for GraphQL files with enhanced pattern support."""

from typing import Dict, Any, List, Match
from dataclasses import dataclass
from parsers.types import FileType, QueryPattern, PatternCategory
import re

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
    PatternCategory.SYNTAX: {
        "type_definition": QueryPattern(
            pattern=r'type\s+(\w+)\s*\{([^}]+)\}',
            extract=extract_type,
            description="Matches GraphQL type definitions",
            examples=["type User { id: ID! name: String }"]
        ),
        "interface": QueryPattern(
            pattern=r'interface\s+(\w+)\s*\{([^}]+)\}',
            extract=lambda m: {
                "type": "interface",
                "name": m.group(1),
                "fields": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches GraphQL interfaces",
            examples=["interface Node { id: ID! }"]
        ),
        "enum": QueryPattern(
            pattern=r'enum\s+(\w+)\s*\{([^}]+)\}',
            extract=lambda m: {
                "type": "enum",
                "name": m.group(1),
                "values": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches GraphQL enums",
            examples=["enum Role { USER ADMIN }"]
        ),
        "input": QueryPattern(
            pattern=r'input\s+(\w+)\s*\{([^}]+)\}',
            extract=lambda m: {
                "type": "input",
                "name": m.group(1),
                "fields": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches GraphQL input types",
            examples=["input UserInput { name: String! }"]
        )
    },
    
    PatternCategory.STRUCTURE: {
        "field": QueryPattern(
            pattern=r'(\w+)(?:\(([^)]+)\))?\s*:\s*([\w\[\]!]+)',
            extract=extract_field,
            description="Matches GraphQL fields",
            examples=["name: String", "age: Int!"]
        ),
        "argument": QueryPattern(
            pattern=r'(\w+):\s*([\w\[\]!]+)(?:\s*=\s*([^,\s]+))?',
            extract=extract_argument,
            description="Matches GraphQL arguments",
            examples=["id: ID!", "limit: Int = 10"]
        ),
        "directive": QueryPattern(
            pattern=r'@(\w+)(?:\(([^)]+)\))?',
            extract=lambda m: {
                "type": "directive",
                "name": m.group(1),
                "arguments": m.group(2) if m.group(2) else None,
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches GraphQL directives",
            examples=["@deprecated", "@include(if: $flag)"]
        )
    },
    
    PatternCategory.DOCUMENTATION: {
        "description": QueryPattern(
            pattern=r'"""([^"]+)"""',
            extract=lambda m: {
                "type": "description",
                "content": m.group(1).strip(),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches GraphQL descriptions",
            examples=["\"\"\"User type description\"\"\""]
        ),
        "comment": QueryPattern(
            pattern=r'#\s*(.+)$',
            extract=lambda m: {
                "type": "comment",
                "content": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches GraphQL comments",
            examples=["# This is a comment"]
        ),
        "deprecated": QueryPattern(
            pattern=r'@deprecated\(reason:\s*"([^"]+)"\)',
            extract=lambda m: {
                "type": "deprecated",
                "reason": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches deprecation notices",
            examples=["@deprecated(reason: \"Use newField instead\")"]
        )
    },
    
    PatternCategory.SEMANTICS: {
        "scalar": QueryPattern(
            pattern=r'scalar\s+(\w+)',
            extract=lambda m: {
                "type": "scalar",
                "name": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches scalar type definitions",
            examples=["scalar DateTime"]
        ),
        "union": QueryPattern(
            pattern=r'union\s+(\w+)\s*=\s*([^{\n]+)',
            extract=lambda m: {
                "type": "union",
                "name": m.group(1),
                "types": [t.strip() for t in m.group(2).split('|')],
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches union type definitions",
            examples=["union SearchResult = User | Post"]
        ),
        "implements": QueryPattern(
            pattern=r'type\s+(\w+)\s+implements\s+([^\{]+)',
            extract=lambda m: {
                "type": "implements",
                "type_name": m.group(1),
                "interfaces": [i.strip() for i in m.group(2).split('&')],
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches interface implementations",
            examples=["type User implements Node & Entity"]
        )
    },
    
    PatternCategory.CODE_PATTERNS: {
        "query": QueryPattern(
            pattern=r'(?:query|mutation|subscription)\s+(\w+)(?:\(([^)]+)\))?\s*\{([^}]+)\}',
            extract=lambda m: {
                "type": "operation",
                "name": m.group(1),
                "arguments": m.group(2) if m.group(2) else None,
                "body": m.group(3),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches GraphQL operations",
            examples=["query GetUser($id: ID!) { user(id: $id) { name } }"]
        ),
        "fragment": QueryPattern(
            pattern=r'fragment\s+(\w+)\s+on\s+(\w+)\s*\{([^}]+)\}',
            extract=lambda m: {
                "type": "fragment",
                "name": m.group(1),
                "on_type": m.group(2),
                "body": m.group(3),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches GraphQL fragments",
            examples=["fragment UserFields on User { name email }"]
        )
    },
    
    PatternCategory.DEPENDENCIES: {
        "type_reference": QueryPattern(
            pattern=r':\s*([\w\[\]!]+)',
            extract=lambda m: {
                "type": "type_reference",
                "referenced_type": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "is_required": m.group(1).endswith('!')
            },
            description="Matches type references",
            examples=["name: String!", "posts: [Post]"]
        ),
        "fragment_spread": QueryPattern(
            pattern=r'\.\.\.\s*(\w+)',
            extract=lambda m: {
                "type": "fragment_spread",
                "fragment_name": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches fragment spreads",
            examples=["...UserFields"]
        )
    },
    
    PatternCategory.BEST_PRACTICES: {
        "naming_convention": QueryPattern(
            pattern=r'type\s+([A-Z][a-zA-Z]*)',
            extract=lambda m: {
                "type": "naming_convention",
                "name": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "follows_convention": bool(re.match(r'^[A-Z][a-zA-Z]*$', m.group(1)))
            },
            description="Checks type naming conventions",
            examples=["type User", "type badName"]
        ),
        "field_nullability": QueryPattern(
            pattern=r'(\w+):\s*([\w\[\]!]+)',
            extract=lambda m: {
                "type": "field_nullability",
                "field": m.group(1),
                "field_type": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "is_nullable": not m.group(2).endswith('!')
            },
            description="Checks field nullability",
            examples=["id: ID!", "name: String"]
        )
    },
    
    PatternCategory.COMMON_ISSUES: {
        "duplicate_field": QueryPattern(
            pattern=r'\{[^}]*(\w+)[^}]*\1[^}]*\}',
            extract=lambda m: {
                "type": "duplicate_field",
                "field": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "is_duplicate": True
            },
            description="Detects duplicate fields",
            examples=["{ name age name }"]
        ),
        "circular_fragment": QueryPattern(
            pattern=r'fragment\s+(\w+)[^{]*\{[^}]*\.\.\.\1[^}]*\}',
            extract=lambda m: {
                "type": "circular_fragment",
                "fragment_name": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "has_circular_reference": True
            },
            description="Detects circular fragment references",
            examples=["fragment User on User { ...User }"]
        )
    },
    
    PatternCategory.USER_PATTERNS: {
        "custom_directive": QueryPattern(
            pattern=r'directive\s+@(\w+)\s*(?:\(([^)]+)\))?\s+on\s+([^\n]+)',
            extract=lambda m: {
                "type": "custom_directive",
                "name": m.group(1),
                "arguments": m.group(2) if m.group(2) else None,
                "locations": [l.strip() for l in m.group(3).split('|')],
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches custom directive definitions",
            examples=["directive @auth(requires: Role!) on FIELD_DEFINITION"]
        ),
        "custom_scalar": QueryPattern(
            pattern=r'scalar\s+(\w+)(?:\s+@[^\n]+)?',
            extract=lambda m: {
                "type": "custom_scalar",
                "name": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches custom scalar definitions",
            examples=["scalar DateTime @specifiedBy(url: \"url\")"]
        )
    }
}

# Add the repository learning patterns
GRAPHQL_PATTERNS[PatternCategory.LEARNING] = {
    "type_patterns": QueryPattern(
        pattern=r'type\s+(\w+)(?:\s+implements[^{]+)?\s*\{([^}]+)\}',
        extract=lambda m: {
            "type": "type_pattern",
            "name": m.group(1),
            "body": m.group(2),
            "line_number": m.string.count('\n', 0, m.start()) + 1,
            "has_interfaces": "implements" in m.group(0)
        },
        description="Learns type definition patterns",
        examples=["type User { id: ID! }", "type Post implements Node { id: ID! }"]
    ),
    "operation_patterns": QueryPattern(
        pattern=r'(?:query|mutation|subscription)\s+(\w+)(?:\([^)]+\))?\s*\{([^}]+)\}',
        extract=lambda m: {
            "type": "operation_pattern",
            "name": m.group(1),
            "body": m.group(2),
            "line_number": m.string.count('\n', 0, m.start()) + 1,
            "operation_type": re.match(r'(query|mutation|subscription)', m.group(0)).group(1)
        },
        description="Learns operation patterns",
        examples=["query GetUser { user { name } }", "mutation UpdateUser { updateUser { id } }"]
    )
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