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
    }
}

# Define language for pattern extraction
LANGUAGE = "yaml"

# YAML patterns for repository learning
YAML_PATTERNS_FOR_LEARNING = {
    "document_structure": {
        "top_level_structure": QueryPattern(
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
    },
    "naming_conventions": {
        "snake_case_keys": QueryPattern(
            pattern=r'^\s*([a-z][a-z0-9_]*[a-z0-9]):\s',
            extract=lambda m: {
                "type": "naming_convention_pattern",
                "key": m.group(1),
                "convention": "snake_case" if '_' in m.group(1) else None
            },
            description="Matches snake_case naming convention in YAML keys",
            examples=["snake_case_key: value"]
        ),
        "camel_case_keys": QueryPattern(
            pattern=r'^\s*([a-z][a-zA-Z0-9]*[A-Z][a-zA-Z0-9]*):\s',
            extract=lambda m: {
                "type": "naming_convention_pattern",
                "key": m.group(1),
                "convention": "camelCase" if not '_' in m.group(1) and not '-' in m.group(1) else None
            },
            description="Matches camelCase naming convention in YAML keys",
            examples=["camelCaseKey: value"]
        ),
        "kebab_case_keys": QueryPattern(
            pattern=r'^\s*([a-z][a-z0-9-]*[a-z0-9]):\s',
            extract=lambda m: {
                "type": "naming_convention_pattern",
                "key": m.group(1),
                "convention": "kebab-case" if '-' in m.group(1) else None
            },
            description="Matches kebab-case naming convention in YAML keys",
            examples=["kebab-case-key: value"]
        )
    },
    "value_patterns": {
        "environment_variables": QueryPattern(
            pattern=r'(\${[^}]+}|\$\w+|\$\([^)]+\))',
            extract=lambda m: {
                "type": "environment_variable_pattern",
                "reference": m.group(1),
                "is_environment_var": True
            },
            description="Matches environment variable references in YAML",
            examples=["key: ${VAR}", "path: $HOME"]
        ),
        "url_values": QueryPattern(
            pattern=r'(https?://[^\s,]+)',
            extract=lambda m: {
                "type": "url_pattern",
                "url": m.group(1),
                "is_url": True
            },
            description="Matches URL values in YAML",
            examples=["url: https://example.com"]
        ),
        "version_strings": QueryPattern(
            pattern=r'version:\s*[\'"]?(\d+\.\d+(?:\.\d+)?(?:-\w+)?)[\'"]?',
            extract=lambda m: {
                "type": "version_pattern",
                "version": m.group(1),
                "is_version": True
            },
            description="Matches version strings in YAML",
            examples=["version: 1.0.0", "version: '2.1.3-beta'"]
        )
    }
}

# Add the repository learning patterns to the main patterns
YAML_PATTERNS['REPOSITORY_LEARNING'] = YAML_PATTERNS_FOR_LEARNING

# Function to extract patterns for repository learning
def extract_yaml_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """Extract patterns from YAML content for repository learning."""
    patterns = []
    
    # Process document structure patterns
    for pattern_name, pattern in YAML_PATTERNS_FOR_LEARNING["document_structure"].items():
        if hasattr(pattern.pattern, "__call__"):
            # Skip AST-based patterns
            continue
            
        for match in re.finditer(pattern.pattern, content, re.MULTILINE | re.DOTALL):
            pattern_data = pattern.extract(match)
            patterns.append({
                "name": pattern_name,
                "type": pattern_data.get("type", "document_structure"),
                "content": match.group(0),
                "metadata": pattern_data,
                "confidence": 0.85
            })
    
    # Process naming convention patterns
    snake_case_count = 0
    camel_case_count = 0
    kebab_case_count = 0
    
    for pattern_name, pattern in YAML_PATTERNS_FOR_LEARNING["naming_conventions"].items():
        if hasattr(pattern.pattern, "__call__"):
            # Skip AST-based patterns
            continue
            
        for match in re.finditer(pattern.pattern, content, re.MULTILINE):
            pattern_data = pattern.extract(match)
            convention = pattern_data.get("convention")
            if convention == "snake_case":
                snake_case_count += 1
            elif convention == "camelCase":
                camel_case_count += 1
            elif convention == "kebab-case":
                kebab_case_count += 1
    
    # Only add a naming convention pattern if we have enough data
    total_keys = snake_case_count + camel_case_count + kebab_case_count
    if total_keys > 3:
        if snake_case_count >= camel_case_count and snake_case_count >= kebab_case_count:
            dominant_convention = "snake_case"
            dom_count = snake_case_count
        elif camel_case_count >= snake_case_count and camel_case_count >= kebab_case_count:
            dominant_convention = "camelCase"
            dom_count = camel_case_count
        else:
            dominant_convention = "kebab-case"
            dom_count = kebab_case_count
            
        confidence = 0.5 + 0.3 * (dom_count / total_keys)
            
        patterns.append({
            "name": "key_naming_convention",
            "type": "naming_convention_pattern",
            "content": f"Key naming convention: {dominant_convention}",
            "metadata": {
                "convention": dominant_convention,
                "snake_case_count": snake_case_count,
                "camel_case_count": camel_case_count,
                "kebab_case_count": kebab_case_count
            },
            "confidence": confidence
        })
    
    # Process value patterns
    for pattern_name, pattern in YAML_PATTERNS_FOR_LEARNING["value_patterns"].items():
        if hasattr(pattern.pattern, "__call__"):
            # Skip AST-based patterns
            continue
            
        for match in re.finditer(pattern.pattern, content, re.MULTILINE):
            pattern_data = pattern.extract(match)
            patterns.append({
                "name": pattern_name,
                "type": pattern_data.get("type", "value_pattern"),
                "content": match.group(0),
                "metadata": pattern_data,
                "confidence": 0.75
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