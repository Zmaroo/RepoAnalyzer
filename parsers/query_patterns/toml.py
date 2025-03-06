"""Query patterns for TOML files with enhanced pattern support."""

from typing import Dict, Any, List, Match
from dataclasses import dataclass
from parsers.types import FileType, QueryPattern, PatternCategory
import re

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
        ),
        "array": QueryPattern(
            pattern=r'^\s*([\w.-]+)\s*=\s*\[(.*)\]$',
            extract=lambda m: {
                "type": "array",
                "key": m.group(1),
                "values": [v.strip() for v in m.group(2).split(',') if v.strip()],
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches arrays",
            examples=["tags = [\"web\", \"api\"]"]
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
        ),
        "inline_table": QueryPattern(
            pattern=r'^\s*([\w.-]+)\s*=\s*\{([^}]+)\}$',
            extract=lambda m: {
                "type": "inline_table",
                "key": m.group(1),
                "content": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches inline tables",
            examples=["point = { x = 1, y = 2 }"]
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
        ),
        "section_comment": QueryPattern(
            pattern=r'#\s*(.+)\n\s*\[(.*?)\]',
            extract=lambda m: {
                "type": "section_comment",
                "comment": m.group(1),
                "section": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches section comments",
            examples=["# Server configuration\n[server]"]
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
        ),
        "datetime": QueryPattern(
            pattern=r'^\s*([\w.-]+)\s*=\s*(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)\s*$',
            extract=lambda m: {
                "type": "datetime",
                "key": m.group(1),
                "value": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches datetime values",
            examples=["date = 2024-03-14T15:09:26Z"]
        )
    },
    
    PatternCategory.CODE_PATTERNS: {
        "multiline_string": QueryPattern(
            pattern=r'^\s*([\w.-]+)\s*=\s*"""\n(.*?)\n\s*"""$',
            extract=lambda m: {
                "type": "multiline_string",
                "key": m.group(1),
                "content": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches multiline strings",
            examples=["content = \"\"\"\nMultiline\ncontent\n\"\"\""]
        ),
        "literal_string": QueryPattern(
            pattern=r"^\s*([\w.-]+)\s*=\s*'([^'\\]*(\\.[^'\\]*)*)'$",
            extract=lambda m: {
                "type": "literal_string",
                "key": m.group(1),
                "content": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches literal strings",
            examples=["path = 'C:\\Program Files\\App'"]
        )
    },
    
    PatternCategory.DEPENDENCIES: {
        "import": QueryPattern(
            pattern=r'^\s*@import\s+"([^"]+)"\s*$',
            extract=lambda m: {
                "type": "import",
                "path": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches import statements",
            examples=["@import \"config.toml\""]
        ),
        "env_var": QueryPattern(
            pattern=r'^\s*([\w.-]+)\s*=\s*\$\{([^:}]+)(?::([^}]+))?\}$',
            extract=lambda m: {
                "type": "env_var",
                "key": m.group(1),
                "var_name": m.group(2),
                "default": m.group(3) if m.group(3) else None,
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches environment variable references",
            examples=["api_key = ${API_KEY:default_key}"]
        )
    },
    
    PatternCategory.BEST_PRACTICES: {
        "key_naming": QueryPattern(
            pattern=r'^\s*([\w.-]+)\s*=',
            extract=lambda m: {
                "type": "key_naming",
                "key": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "follows_convention": bool(re.match(r'^[a-z][a-z0-9_.-]*$', m.group(1)))
            },
            description="Checks key naming conventions",
            examples=["good_key = value", "BadKey = value"]
        ),
        "table_hierarchy": QueryPattern(
            pattern=r'^\s*\[(.*?)\]\s*$\n(?:[^[]*\n)*\s*\[(.*?)\]\s*$',
            extract=lambda m: {
                "type": "table_hierarchy",
                "parent": m.group(1),
                "child": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "follows_hierarchy": m.group(2).startswith(m.group(1) + ".")
            },
            description="Checks table hierarchy",
            examples=["[parent]\n[parent.child]"]
        )
    },
    
    PatternCategory.COMMON_ISSUES: {
        "duplicate_key": QueryPattern(
            pattern=r'^\s*([\w.-]+)\s*=.*\n(?:.*\n)*?\s*\1\s*=',
            extract=lambda m: {
                "type": "duplicate_key",
                "key": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "is_duplicate": True
            },
            description="Detects duplicate keys",
            examples=["key = 1\nkey = 2"]
        ),
        "invalid_value": QueryPattern(
            pattern=r'^\s*([\w.-]+)\s*=\s*([^"\[\{][^\s,\]]*)',
            extract=lambda m: {
                "type": "invalid_value",
                "key": m.group(1),
                "value": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "needs_quotes": not re.match(r'^-?\d+(?:\.\d+)?$', m.group(2))
            },
            description="Detects potentially invalid values",
            examples=["key = invalid value"]
        )
    },
    
    PatternCategory.USER_PATTERNS: {
        "custom_table": QueryPattern(
            pattern=r'^\s*\[x\.(.*?)\]\s*$',
            extract=lambda m: {
                "type": "custom_table",
                "name": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches custom table definitions",
            examples=["[x.custom]"]
        ),
        "custom_format": QueryPattern(
            pattern=r'^\s*format\s*=\s*"([^"]+)".*?pattern\s*=\s*"([^"]+)"',
            extract=lambda m: {
                "type": "custom_format",
                "format": m.group(1),
                "pattern": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches custom format definitions",
            examples=["format = \"custom\"\npattern = \".*\""]
        )
    }
}

# Add the repository learning patterns
TOML_PATTERNS[PatternCategory.LEARNING] = {
    "document_structure": QueryPattern(
        pattern=r'(?s)^\s*\[(.*?)\]\s*\n(.*?)(?=\n\s*\[|$)',
        extract=lambda m: {
            "type": "document_structure",
            "section": m.group(1),
            "content": m.group(2),
            "line_number": m.string.count('\n', 0, m.start()) + 1
        },
        description="Matches document structure patterns",
        examples=["[section]\nkey = value"]
    ),
    "value_patterns": QueryPattern(
        pattern=r'^\s*([\w.-]+)\s*=\s*(.+)$',
        extract=lambda m: {
            "type": "value_pattern",
            "key": m.group(1),
            "value": m.group(2),
            "line_number": m.string.count('\n', 0, m.start()) + 1,
            "value_type": "string" if m.group(2).startswith('"') else "number" if m.group(2).replace(".", "").isdigit() else "other"
        },
        description="Learns value patterns",
        examples=["key = \"value\"", "number = 42"]
    )
}

# Function to extract patterns for repository learning
def extract_toml_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """Extract patterns from TOML content for repository learning."""
    patterns = []
    
    # Process each pattern category
    for category in PatternCategory:
        if category in TOML_PATTERNS:
            category_patterns = TOML_PATTERNS[category]
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
    "document": {
        "can_contain": ["table", "key_value", "comment"],
        "can_be_contained_by": []
    },
    "table": {
        "can_contain": ["key_value", "array", "inline_table"],
        "can_be_contained_by": ["document", "table"]
    },
    "array_table": {
        "can_contain": ["key_value", "array", "inline_table"],
        "can_be_contained_by": ["document"]
    },
    "inline_table": {
        "can_contain": ["key_value"],
        "can_be_contained_by": ["table", "array_table", "key_value"]
    }
}

def extract_toml_features(ast: dict) -> dict:
    """Extract features that align with pattern categories."""
    features = {
        "syntax": {
            "tables": [],
            "array_tables": [],
            "key_values": [],
            "arrays": []
        },
        "structure": {
            "sections": [],
            "subsections": [],
            "inline_tables": []
        },
        "semantics": {
            "types": [],
            "references": [],
            "datetimes": []
        },
        "documentation": {
            "doc_comments": [],
            "comments": [],
            "section_comments": []
        }
    }
    return features 