"""Query patterns for Nim files."""

from parsers.pattern_processor import QueryPattern, PatternCategory
from typing import Dict, Any, Match

def extract_proc(match: Match) -> Dict[str, Any]:
    """Extract procedure information."""
    return {
        "type": "proc",
        "name": match.group(1),
        "parameters": match.group(2),
        "return_type": match.group(3),
        "line_number": match.string.count('\n', 0, match.start()) + 1
    }

def extract_type(match: Match) -> Dict[str, Any]:
    """Extract type information."""
    return {
        "type": "type",
        "name": match.group(1),
        "line_number": match.string.count('\n', 0, match.start()) + 1
    }

NIM_PATTERNS = {
    PatternCategory.SYNTAX: {
        "proc": QueryPattern(
            pattern=r'^proc\s+(\w+)\*?\s*\((.*?)\)(?:\s*:\s*(\w+))?\s*=',
            extract=extract_proc,
            description="Matches Nim procedure definitions",
            examples=["proc add*(x, y: int): int ="]
        ),
        "type": QueryPattern(
            pattern=r'^type\s+(\w+)\*?\s*=\s*(?:object|enum|tuple|ref\s+object)',
            extract=extract_type,
            description="Matches Nim type definitions",
            examples=["type Person* = object"]
        )
    },
    
    PatternCategory.STRUCTURE: {
        "import": QueryPattern(
            pattern=r'^import\s+(.*?)(?:\s+except\s+.*)?$',
            extract=lambda m: {
                "type": "import",
                "modules": [mod.strip() for mod in m.group(1).split(',')],
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches import statements",
            examples=["import strutils, sequtils"]
        ),
        "module": QueryPattern(
            pattern=r'^module\s+(\w+)',
            extract=lambda m: {
                "type": "module",
                "name": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches module declarations",
            examples=["module mymodule"]
        )
    },
    
    PatternCategory.DOCUMENTATION: {
        "docstring": QueryPattern(
            pattern=r'^##\s*(.*)$',
            extract=lambda m: {
                "type": "docstring",
                "content": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches documentation strings",
            examples=["## This is a docstring"]
        ),
        "comment": QueryPattern(
            pattern=r'^#\s*(.*)$',
            extract=lambda m: {
                "type": "comment",
                "content": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches comments",
            examples=["# This is a comment"]
        )
    },
    
    PatternCategory.SEMANTICS: {
        "variable": QueryPattern(
            pattern=r'^(var|let|const)\s+(\w+)\*?\s*(?::\s*(\w+))?\s*=\s*(.+)$',
            extract=lambda m: {
                "type": "variable",
                "kind": m.group(1),
                "name": m.group(2),
                "value_type": m.group(3),
                "value": m.group(4),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches variable declarations",
            examples=["var x: int = 42", "let name = \"John\""]
        ),
        "parameter": QueryPattern(
            pattern=r'(\w+)(?:\s*:\s*(\w+))?',
            extract=lambda m: {
                "type": "parameter",
                "name": m.group(1),
                "value_type": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches procedure parameters",
            examples=["x: int", "name: string"]
        )
    }
}

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "module": {
        "can_contain": ["proc", "type", "import", "variable"],
        "can_be_contained_by": []
    },
    "proc": {
        "can_contain": ["parameter", "docstring"],
        "can_be_contained_by": ["module"]
    },
    "type": {
        "can_contain": ["docstring"],
        "can_be_contained_by": ["module"]
    },
    "variable": {
        "can_contain": ["docstring"],
        "can_be_contained_by": ["module", "proc"]
    }
} 