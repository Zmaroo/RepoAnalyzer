"""
Query patterns for YAML files aligned with standard PATTERN_CATEGORIES.
"""

from typing import Dict, Any, List, Match, Optional
from dataclasses import dataclass
from parsers.types import FileType, QueryPattern, PatternCategory
import re

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
    },
    
    PatternCategory.CODE_PATTERNS: {
        "function": QueryPattern(
            pattern=r'^\s*(\w+):\s*!(\w+)\s+(.*)$',
            extract=lambda m: {
                "type": "function",
                "name": m.group(1),
                "tag": m.group(2),
                "args": m.group(3).strip(),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches YAML function tags",
            examples=["calculate: !function add(x, y)"]
        ),
        "code_block": QueryPattern(
            pattern=r'^\s*(\w+):\s*\|\s*\n((?:\s+.*\n)+)',
            extract=lambda m: {
                "type": "code_block",
                "name": m.group(1),
                "content": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches YAML code blocks",
            examples=["script: |\n  def main():\n    print('hello')"]
        )
    },
    
    PatternCategory.DEPENDENCIES: {
        "dependency": QueryPattern(
            pattern=r'^\s*dependencies:\s*\n((?:\s+-\s+.*\n)+)',
            extract=lambda m: {
                "type": "dependencies",
                "content": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches dependency declarations",
            examples=["dependencies:\n  - package: ^1.0.0"]
        ),
        "version": QueryPattern(
            pattern=r'^\s*version:\s*[\'"]?(\d+\.\d+(?:\.\d+)?(?:-\w+)?)[\'"]?',
            extract=lambda m: {
                "type": "version",
                "value": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches version declarations",
            examples=["version: 1.0.0", "version: '2.1.3-beta'"]
        )
    },
    
    PatternCategory.BEST_PRACTICES: {
        "environment_var": QueryPattern(
            pattern=r'^\s*(\w+):\s*\$\{([^:}]+)(?::([^}]+))?\}$',
            extract=lambda m: {
                "type": "environment_var",
                "name": m.group(1),
                "var": m.group(2),
                "default": m.group(3) if m.group(3) else None,
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches environment variable usage with defaults",
            examples=["api_key: ${API_KEY:default_key}"]
        ),
        "secret": QueryPattern(
            pattern=r'^\s*(password|secret|key|token):\s*(.+)$',
            extract=lambda m: {
                "type": "secret",
                "key": m.group(1),
                "value": m.group(2).strip(),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "is_sensitive": True
            },
            description="Identifies sensitive information",
            examples=["password: secret123"]
        )
    },
    
    PatternCategory.COMMON_ISSUES: {
        "duplicate_key": QueryPattern(
            pattern=r'^\s*([^:]+):\s*(.*)$',
            extract=lambda m: {
                "type": "duplicate_key",
                "key": m.group(1).strip(),
                "value": m.group(2).strip(),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Detects potential duplicate keys",
            examples=["key: value1", "key: value2"]
        ),
        "invalid_indent": QueryPattern(
            pattern=r'^( +)[^ -]',
            extract=lambda m: {
                "type": "invalid_indent",
                "spaces": len(m.group(1)),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Detects invalid indentation",
            examples=["   key: value"]
        )
    },
    
    PatternCategory.USER_PATTERNS: {
        "custom_tag": QueryPattern(
            pattern=r'^\s*(\w+):\s*!(\w+)(?:\s+(.*))?$',
            extract=lambda m: {
                "type": "custom_tag",
                "key": m.group(1),
                "tag": m.group(2),
                "value": m.group(3).strip() if m.group(3) else None,
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches custom YAML tags",
            examples=["data: !custom value"]
        ),
        "custom_format": QueryPattern(
            pattern=r'^\s*(\w+):\s*([^{\n]*\{[^}\n]+\}[^\n]*)$',
            extract=lambda m: {
                "type": "custom_format",
                "key": m.group(1),
                "format": m.group(2).strip(),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches custom format strings",
            examples=["message: Hello {name}!"]
        )
    }
}

# Add the repository learning patterns
YAML_PATTERNS[PatternCategory.LEARNING] = {
    "document_structure": QueryPattern(
        pattern=r'(?s)^(.*?)(?=^\s*#|\Z)',
        extract=lambda m: {
            "type": "document_structure_pattern",
            "content": m.group(1).strip(),
            "is_top_level": True
        },
        description="Matches top-level document structure in YAML",
        examples=["key1: value1\nkey2: value2"]
    ),
    "nested_mapping": QueryPattern(
        pattern=r'(?s)^(\s*)([^:\n]+):\s*\n(\1\s+[^-\s].*?(?=\n\1[^:\s]|\n\1$|\Z))',
        extract=lambda m: {
            "type": "nested_mapping_pattern",
            "key": m.group(2).strip(),
            "content": m.group(3),
            "indentation": len(m.group(1)),
            "has_nested_content": True
        },
        description="Matches nested mapping structures in YAML",
        examples=["parent:\n  child1: value1\n  child2: value2"]
    ),
    "list_structure": QueryPattern(
        pattern=r'(?s)^(\s*)([^:\n]+):\s*\n(\1\s+-.*?(?=\n\1[^-\s]|\n\1$|\Z))',
        extract=lambda m: {
            "type": "list_structure_pattern",
            "key": m.group(2).strip(),
            "items": m.group(3).count('-'),
            "content": m.group(3),
            "indentation": len(m.group(1))
        },
        description="Matches list structures in YAML",
        examples=["items:\n  - item1\n  - item2"]
    )
}

# Function to extract patterns for repository learning
def extract_yaml_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """Extract patterns from YAML content for repository learning."""
    patterns = []
    
    # Process each pattern category
    for category in PatternCategory:
        if category in YAML_PATTERNS:
            category_patterns = YAML_PATTERNS[category]
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