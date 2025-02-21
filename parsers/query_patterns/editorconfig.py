"""
Query patterns for EditorConfig files aligned with PATTERN_CATEGORIES.

These patterns target the custom AST produced by our custom editorconfig parser.
"""

from parsers.file_classification import FileType
from parsers.pattern_processor import QueryPattern, PatternCategory
from typing import Dict, Any, Match

def extract_section(match: Match) -> Dict[str, Any]:
    """Extract section information."""
    return {
        "type": "section",
        "glob": match.group(1).strip(),
        "line_number": match.string.count('\n', 0, match.start()) + 1
    }

def extract_property(match: Match) -> Dict[str, Any]:
    """Extract property information."""
    return {
        "type": "property",
        "key": match.group(1).strip(),
        "value": match.group(2).strip(),
        "line_number": match.string.count('\n', 0, match.start()) + 1
    }

EDITORCONFIG_PATTERNS = {
    PatternCategory.SYNTAX: {
        "section": QueryPattern(
            pattern=r'^\[(.*)\]$',
            extract=extract_section,
            description="Matches EditorConfig section headers",
            examples=["[*.py]", "[*.{js,py}]"]
        ),
        "property": QueryPattern(
            pattern=r'^([^=]+)=(.*)$',
            extract=extract_property,
            description="Matches EditorConfig property assignments",
            examples=["indent_size = 4", "end_of_line = lf"]
        )
    },
    
    PatternCategory.STRUCTURE: {
        "root": QueryPattern(
            pattern=r'^root\s*=\s*(true|false)$',
            extract=lambda m: {
                "type": "root",
                "value": m.group(1).lower() == "true",
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches EditorConfig root declaration",
            examples=["root = true"]
        )
    },
    
    PatternCategory.DOCUMENTATION: {
        "comment": QueryPattern(
            pattern=r'^[#;](.*)$',
            extract=lambda m: {
                "type": "comment",
                "content": m.group(1).strip(),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches EditorConfig comments",
            examples=["# This is a comment", "; Another comment"]
        )
    },
    
    PatternCategory.SEMANTICS: {
        "indent": QueryPattern(
            pattern=r'^indent_(style|size)\s*=\s*(.+)$',
            extract=lambda m: {
                "type": "indent",
                "property": m.group(1),
                "value": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches EditorConfig indentation settings",
            examples=["indent_style = space", "indent_size = 2"]
        ),
        "charset": QueryPattern(
            pattern=r'^charset\s*=\s*(.+)$',
            extract=lambda m: {
                "type": "charset",
                "value": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches EditorConfig charset settings",
            examples=["charset = utf-8"]
        )
    }
}

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "section": {
        "can_contain": ["property", "comment"],
        "can_be_contained_by": ["editorconfig"]
    },
    "property": {
        "can_be_contained_by": ["section"]
    },
    "comment": {
        "can_be_contained_by": ["section", "editorconfig"]
    }
} 