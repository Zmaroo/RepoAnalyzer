"""Query patterns for TOML files."""

from parsers.pattern_processor import QueryPattern, PatternCategory
from typing import Dict, Any, Match

def extract_table(match: Match) -> Dict[str, Any]:
    """Extract table information."""
    return {
        "type": "table",
        "path": match.group(1),
        "line_number": match.string.count('\n', 0, match.start()) + 1
    }

def extract_key_value(match: Match) -> Dict[str, Any]:
    """Extract key-value information."""
    return {
        "type": "key_value",
        "key": match.group(1),
        "value": match.group(2),
        "line_number": match.string.count('\n', 0, match.start()) + 1
    }

TOML_PATTERNS = {
    PatternCategory.SYNTAX: {
        "table": QueryPattern(
            pattern=r'^\s*\[(.*?)\]\s*$',
            extract=extract_table,
            description="Matches TOML tables",
            examples=["[table]", "[database]"]
        ),
        "array_table": QueryPattern(
            pattern=r'^\s*\[\[(.*?)\]\]\s*$',
            extract=lambda m: {
                "type": "array_table",
                "path": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches TOML array tables",
            examples=["[[products]]"]
        ),
        "key_value": QueryPattern(
            pattern=r'^\s*([\w.-]+)\s*=\s*(.+)$',
            extract=extract_key_value,
            description="Matches key-value pairs",
            examples=["name = \"value\"", "port = 8080"]
        )
    },
    
    PatternCategory.STRUCTURE: {
        "section": QueryPattern(
            pattern=r'^\s*\[(.*?)\]\s*$',
            extract=lambda m: {
                "type": "section",
                "name": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches sections",
            examples=["[section]"]
        ),
        "subsection": QueryPattern(
            pattern=r'^\s*\[(.*?)\.(.*?)\]\s*$',
            extract=lambda m: {
                "type": "subsection",
                "parent": m.group(1),
                "name": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches subsections",
            examples=["[server.http]"]
        )
    },
    
    PatternCategory.DOCUMENTATION: {
        "doc_comment": QueryPattern(
            pattern=r'#\s*@(\w+)\s*(.+)$',
            extract=lambda m: {
                "type": "doc_comment",
                "tag": m.group(1),
                "content": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches documentation comments",
            examples=["# @param value"]
        ),
        "comment": QueryPattern(
            pattern=r'#\s*(.+)$',
            extract=lambda m: {
                "type": "comment",
                "content": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches comments",
            examples=["# Comment"]
        )
    },
    
    PatternCategory.SEMANTICS: {
        "type": QueryPattern(
            pattern=r'^\s*([\w.-]+)\s*=\s*(\w+)\s*$',
            extract=lambda m: {
                "type": "type",
                "name": m.group(1),
                "value_type": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches type definitions",
            examples=["format = string"]
        ),
        "reference": QueryPattern(
            pattern=r'^\s*([\w.-]+)\s*=\s*\$\{(.*?)\}\s*$',
            extract=lambda m: {
                "type": "reference",
                "name": m.group(1),
                "target": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches references",
            examples=["path = ${base_path}"]
        )
    }
}

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "document": {
        "can_contain": ["table", "array_table", "key_value", "comment"],
        "can_be_contained_by": []
    },
    "table": {
        "can_contain": ["key_value", "comment"],
        "can_be_contained_by": ["document"]
    },
    "array_table": {
        "can_contain": ["key_value", "comment"],
        "can_be_contained_by": ["document"]
    }
} 