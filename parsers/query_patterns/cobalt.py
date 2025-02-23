"""Query patterns for the Cobalt programming language."""

from typing import Dict, Any, Match
from parsers.types import QueryPattern, PatternCategory

def extract_function(match: Match) -> Dict[str, Any]:
    """Extract function information."""
    return {
        "type": "function",
        "name": match.group(1),
        "parameters": [p.strip() for p in match.group(2).split(',') if p.strip()],
        "return_type": match.group(3),
        "line_number": match.string.count('\n', 0, match.start()) + 1
    }

def extract_class(match: Match) -> Dict[str, Any]:
    """Extract class information."""
    return {
        "type": "class",
        "name": match.group(1),
        "parent": match.group(2),
        "line_number": match.string.count('\n', 0, match.start()) + 1
    }

COBALT_PATTERNS = {
    PatternCategory.SYNTAX: {
        "function": QueryPattern(
            pattern=r'^fn\s+(\w+)\s*\((.*?)\)(?:\s*->\s*(\w+))?\s*{',
            extract=extract_function,
            description="Matches Cobalt function declarations",
            examples=[
                "fn main() {",
                "fn calculate(x: int, y: int) -> int {"
            ]
        ),
        "class": QueryPattern(
            pattern=r'^class\s+(\w+)(?:\s*:\s*(\w+))?\s*{',
            extract=extract_class,
            description="Matches Cobalt class declarations",
            examples=[
                "class MyClass {",
                "class Derived: Base {"
            ]
        )
    },
    
    PatternCategory.STRUCTURE: {
        "import": QueryPattern(
            pattern=r'^import\s+([\w.]+)(?:\s+as\s+(\w+))?$',
            extract=lambda m: {
                "type": "import",
                "path": m.group(1),
                "alias": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches Cobalt import statements",
            examples=[
                "import std.io",
                "import math.vector as vec"
            ]
        ),
        "namespace": QueryPattern(
            pattern=r'^namespace\s+([\w.]+)\s*{',
            extract=lambda m: {
                "type": "namespace",
                "name": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches Cobalt namespace declarations",
            examples=["namespace core.utils {"]
        )
    },
    
    PatternCategory.DOCUMENTATION: {
        "docstring": QueryPattern(
            pattern=r'^///\s*(.*)$',
            extract=lambda m: {
                "type": "docstring",
                "content": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches Cobalt docstrings",
            examples=["/// Function documentation"]
        ),
        "comment": QueryPattern(
            pattern=r'^//\s*(.*)$',
            extract=lambda m: {
                "type": "comment",
                "content": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches Cobalt comments",
            examples=["// Regular comment"]
        )
    },
    
    PatternCategory.SEMANTICS: {
        "variable": QueryPattern(
            pattern=r'^(let|var)\s+(\w+)(?:\s*:\s*(\w+))?(?:\s*=\s*(.+))?$',
            extract=lambda m: {
                "type": "variable",
                "name": m.group(2),
                "value_type": m.group(3),
                "value": m.group(4),
                "is_mutable": m.group(1) == "var",
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches Cobalt variable declarations",
            examples=[
                "let x: int = 42",
                "var name = \"value\""
            ]
        )
    }
}

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "function": {
        "can_contain": ["variable", "comment", "docstring"],
        "can_be_contained_by": ["class", "namespace"]
    },
    "class": {
        "can_contain": ["function", "variable", "comment", "docstring"],
        "can_be_contained_by": ["namespace"]
    },
    "namespace": {
        "can_contain": ["class", "function", "variable", "comment"],
        "can_be_contained_by": ["namespace"]
    }
} 