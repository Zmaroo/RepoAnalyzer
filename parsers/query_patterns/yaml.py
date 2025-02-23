"""
Query patterns for YAML files aligned with standard PATTERN_CATEGORIES.
"""

from typing import Dict, Any, List, Match
from dataclasses import dataclass
from parsers.types import FileType, QueryPattern, PatternCategory

def extract_mapping(match: Match) -> Dict[str, Any]:
    """Extract mapping information."""
    return {
        "type": "mapping",
        "indent": len(match.group(1)),
        "key": match.group(2).strip(),
        "value": match.group(3).strip(),
        "line_number": match.string.count('\n', 0, match.start()) + 1
    }

def extract_sequence(match: Match) -> Dict[str, Any]:
    """Extract sequence information."""
    return {
        "type": "sequence",
        "indent": len(match.group(1)),
        "value": match.group(2).strip(),
        "line_number": match.string.count('\n', 0, match.start()) + 1
    }

def extract_anchor(match: Match) -> Dict[str, Any]:
    """Extract anchor information."""
    return {
        "type": "anchor",
        "name": match.group(1),
        "line_number": match.string.count('\n', 0, match.start()) + 1
    }

YAML_PATTERNS = {
    PatternCategory.SYNTAX: {
        "mapping": QueryPattern(
            pattern=r'^(\s*)([^:]+):\s*(.*)$',
            extract=extract_mapping,
            description="Matches YAML key-value mappings",
            examples=["key: value"]
        ),
        "sequence": QueryPattern(
            pattern=r'^(\s*)-\s+(.+)$',
            extract=extract_sequence,
            description="Matches YAML sequence items",
            examples=["- item"]
        ),
        "scalar": QueryPattern(
            pattern=r'^(\s*)([^:-].*)$',
            extract=lambda m: {
                "type": "scalar",
                "value": m.group(2).strip(),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches YAML scalar values"
        )
    },
    
    PatternCategory.STRUCTURE: {
        "anchor": QueryPattern(
            pattern=r'&(\w+)\s',
            extract=extract_anchor,
            description="Matches YAML anchors",
            examples=["&anchor_name"]
        ),
        "alias": QueryPattern(
            pattern=r'\*(\w+)',
            extract=lambda m: {
                "type": "alias",
                "name": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches YAML aliases",
            examples=["*anchor_reference"]
        ),
        "tag": QueryPattern(
            pattern=r'!(\w+)(?:\s|$)',
            extract=lambda m: {
                "type": "tag",
                "name": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches YAML tags",
            examples=["!tag_name"]
        )
    },
    
    PatternCategory.DOCUMENTATION: {
        "comment": QueryPattern(
            pattern=r'^\s*#\s*(.*)$',
            extract=lambda m: {
                "type": "comment",
                "content": m.group(1).strip(),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches YAML comments",
            examples=["# Comment"]
        ),
        "doc_comment": QueryPattern(
            pattern=r'^\s*#\s*@(\w+)\s+(.*)$',
            extract=lambda m: {
                "type": "doc_comment",
                "tag": m.group(1),
                "content": m.group(2).strip(),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches YAML documentation comments",
            examples=["# @param description"]
        )
    },
    
    PatternCategory.SEMANTICS: {
        "variable": QueryPattern(
            pattern=r'^\s*(\w+):\s*\$\{([^}]+)\}$',
            extract=lambda m: {
                "type": "variable",
                "name": m.group(1),
                "reference": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches YAML variable references",
            examples=["key: ${VARIABLE}"]
        ),
        "import": QueryPattern(
            pattern=r'^\s*(import|include|require):\s*(.+)$',
            extract=lambda m: {
                "type": "import",
                "kind": m.group(1),
                "path": m.group(2).strip(),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches YAML imports and includes",
            examples=[
                "import: other.yaml",
                "include: config/*.yaml"
            ]
        )
    }
}

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "document": {
        "can_contain": ["mapping", "sequence", "comment"],
        "can_be_contained_by": []
    },
    "mapping": {
        "can_contain": ["mapping", "sequence"],
        "can_be_contained_by": ["document", "mapping", "sequence"]
    },
    "sequence": {
        "can_contain": ["mapping", "sequence"],
        "can_be_contained_by": ["document", "mapping", "sequence"]
    }
} 