"""Query patterns for TOML files."""

from typing import Dict, Any, List, Match, Optional
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

# Define language for pattern extraction
LANGUAGE = "toml"

# TOML patterns for repository learning
TOML_PATTERNS_FOR_LEARNING = {
    "config_structure": {
        "project_metadata": QueryPattern(
            pattern=r'(?s)^\s*\[(name|package|project|tool)\]\s*\n(.*?)(?=\n\[|\Z)',
            extract=lambda m: {
                "type": "project_metadata_pattern",
                "section": m.group(1),
                "content": m.group(2),
                "is_standard_format": True
            },
            description="Matches project metadata structure in TOML",
            examples=["[package]\nname = \"example\"\nversion = \"0.1.0\""]
        ),
        "dependency_section": QueryPattern(
            pattern=r'(?s)^\s*\[(dependencies|dev-dependencies|build-dependencies)\]\s*\n(.*?)(?=\n\[|\Z)',
            extract=lambda m: {
                "type": "dependency_pattern",
                "section_type": m.group(1),
                "content": m.group(2),
                "has_dependencies": True
            },
            description="Matches dependency sections in TOML",
            examples=["[dependencies]\nregex = \"1.0\""]
        ),
        "nested_tables": QueryPattern(
            pattern=r'(?s)^\s*\[(.*?)\.(.*?)\]\s*\n(.*?)(?=\n\[|\Z)',
            extract=lambda m: {
                "type": "nested_table_pattern",
                "parent": m.group(1),
                "child": m.group(2),
                "content": m.group(3),
                "has_nested_structure": True
            },
            description="Matches nested table structures in TOML",
            examples=["[server.http]\nport = 8080"]
        )
    },
    "value_patterns": {
        "string_value": QueryPattern(
            pattern=r'([\w.-]+)\s*=\s*"([^"]*)"',
            extract=lambda m: {
                "type": "string_value_pattern",
                "key": m.group(1),
                "value": m.group(2),
                "value_type": "string"
            },
            description="Matches string values in TOML",
            examples=["name = \"value\""]
        ),
        "integer_value": QueryPattern(
            pattern=r'([\w.-]+)\s*=\s*(\d+)(?!\.|")',
            extract=lambda m: {
                "type": "integer_value_pattern",
                "key": m.group(1),
                "value": int(m.group(2)),
                "value_type": "integer"
            },
            description="Matches integer values in TOML",
            examples=["port = 8080"]
        ),
        "array_value": QueryPattern(
            pattern=r'([\w.-]+)\s*=\s*\[(.*?)\]',
            extract=lambda m: {
                "type": "array_value_pattern",
                "key": m.group(1),
                "value": m.group(2),
                "value_type": "array"
            },
            description="Matches array values in TOML",
            examples=["tags = [\"web\", \"app\"]"]
        )
    },
    "naming_conventions": {
        "snake_case_keys": QueryPattern(
            pattern=r'([a-z][a-z0-9_]*[a-z0-9])\s*=',
            extract=lambda m: {
                "type": "naming_convention_pattern",
                "key": m.group(1),
                "convention": "snake_case" if "_" in m.group(1) else None
            },
            description="Matches snake_case naming convention in TOML",
            examples=["snake_case_key = \"value\""]
        ),
        "camel_case_keys": QueryPattern(
            pattern=r'([a-z][a-zA-Z0-9]*[a-zA-Z0-9])\s*=',
            extract=lambda m: {
                "type": "naming_convention_pattern",
                "key": m.group(1),
                "convention": "camelCase" if any(c.isupper() for c in m.group(1)) and not "_" in m.group(1) else None
            },
            description="Matches camelCase naming convention in TOML",
            examples=["camelCaseKey = \"value\""]
        )
    }
}

# Add the repository learning patterns to the main patterns
TOML_PATTERNS['REPOSITORY_LEARNING'] = TOML_PATTERNS_FOR_LEARNING

# Function to extract patterns for repository learning
def extract_toml_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """Extract patterns from TOML content for repository learning."""
    patterns = []
    
    # Process config structure patterns
    for pattern_name, pattern in TOML_PATTERNS_FOR_LEARNING["config_structure"].items():
        if hasattr(pattern.pattern, "__call__"):
            # Skip AST-based patterns
            continue
            
        for match in re.finditer(pattern.pattern, content, re.MULTILINE | re.DOTALL):
            pattern_data = pattern.extract(match)
            patterns.append({
                "name": pattern_name,
                "type": pattern_data.get("type", "config_structure"),
                "content": match.group(0),
                "metadata": pattern_data,
                "confidence": 0.85
            })
    
    # Process value patterns
    for pattern_name, pattern in TOML_PATTERNS_FOR_LEARNING["value_patterns"].items():
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
                "confidence": 0.8
            })
    
    # Process naming convention patterns
    snake_case_count = 0
    camel_case_count = 0
    
    for pattern_name, pattern in TOML_PATTERNS_FOR_LEARNING["naming_conventions"].items():
        if hasattr(pattern.pattern, "__call__"):
            # Skip AST-based patterns
            continue
            
        for match in re.finditer(pattern.pattern, content, re.MULTILINE):
            pattern_data = pattern.extract(match)
            if pattern_data.get("convention") == "snake_case":
                snake_case_count += 1
            elif pattern_data.get("convention") == "camelCase":
                camel_case_count += 1
    
    # Only add a naming convention pattern if we have enough data
    if snake_case_count > 0 or camel_case_count > 0:
        dominant_style = "snake_case" if snake_case_count >= camel_case_count else "camelCase"
        confidence = 0.5 + 0.3 * (max(snake_case_count, camel_case_count) / max(1, snake_case_count + camel_case_count))
        
        patterns.append({
            "name": "naming_convention",
            "type": "naming_convention_pattern",
            "content": f"Naming convention: {dominant_style}",
            "metadata": {
                "convention": dominant_style,
                "snake_case_count": snake_case_count,
                "camel_case_count": camel_case_count
            },
            "confidence": confidence
        })
    
    return patterns

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