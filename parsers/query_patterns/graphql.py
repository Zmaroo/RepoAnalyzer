"""Query patterns for GraphQL schema files."""

from parsers.pattern_processor import QueryPattern, PatternCategory
from typing import Dict, Any, Match

def extract_type(match: Match) -> Dict[str, Any]:
    """Extract type information."""
    return {
        "type": "type",
        "name": match.group(1),
        "implements": match.group(2),
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
            pattern=r'^type\s+(\w+)(?:\s+implements\s+(\w+))?\s*{',
            extract=extract_type,
            description="Matches GraphQL type definitions",
            examples=["type User {", "type Post implements Node {"]
        ),
        "field": QueryPattern(
            pattern=r'^\s*(\w+)(?:\(([^)]*)\))?\s*:\s*(\w+)(!?\[?!?\]?)',
            extract=extract_field,
            description="Matches GraphQL field definitions",
            examples=["name: String!", "posts(first: Int): [Post]"]
        )
    },
    
    PatternCategory.STRUCTURE: {
        "interface": QueryPattern(
            pattern=r'^interface\s+(\w+)\s*{',
            extract=lambda m: {
                "type": "interface",
                "name": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches GraphQL interface definitions",
            examples=["interface Node {"]
        ),
        "fragment": QueryPattern(
            pattern=r'^fragment\s+(\w+)\s+on\s+(\w+)',
            extract=lambda m: {
                "type": "fragment",
                "name": m.group(1),
                "target": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches GraphQL fragment definitions",
            examples=["fragment UserFields on User"]
        )
    },
    
    PatternCategory.DOCUMENTATION: {
        "description": QueryPattern(
            pattern=r'^"""(.*?)"""',
            extract=lambda m: {
                "type": "description",
                "content": m.group(1).strip(),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches GraphQL descriptions",
            examples=['"""User type description"""']
        ),
        "comment": QueryPattern(
            pattern=r'^#\s*(.*)$',
            extract=lambda m: {
                "type": "comment",
                "content": m.group(1).strip(),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches GraphQL comments",
            examples=["# User type"]
        )
    },
    
    PatternCategory.SEMANTICS: {
        "directive": QueryPattern(
            pattern=r'@(\w+)(?:\(([^)]*)\))?',
            extract=lambda m: {
                "type": "directive",
                "name": m.group(1),
                "arguments": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches GraphQL directives",
            examples=["@deprecated", "@include(if: $foo)"]
        ),
        "argument": QueryPattern(
            pattern=r'(\w+)\s*:\s*(\w+)(!?\[?!?\]?)',
            extract=lambda m: {
                "type": "argument",
                "name": m.group(1),
                "value_type": m.group(2),
                "modifiers": m.group(3),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches GraphQL arguments",
            examples=["id: ID!", "status: Status"]
        )
    }
}

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