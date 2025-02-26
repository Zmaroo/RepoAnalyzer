"""
Query patterns for Markdown files with enhanced documentation support.
"""

from typing import Dict, Any, List, Match
from dataclasses import dataclass
from parsers.types import FileType, QueryPattern, PatternCategory
import re

def extract_header(match: Match) -> Dict[str, Any]:
    """Extract header information."""
    return {
        "type": "header",
        "level": len(match.group(1)),
        "content": match.group(2),
        "line_number": match.string.count('\n', 0, match.start()) + 1
    }

def extract_list_item(match: Match) -> Dict[str, Any]:
    """Extract list item information."""
    return {
        "type": "list_item",
        "indent": len(match.group(1)),
        "content": match.group(2),
        "line_number": match.string.count('\n', 0, match.start()) + 1
    }

MARKDOWN_PATTERNS = {
    PatternCategory.SYNTAX: {
        "header": QueryPattern(
            pattern=r'^(#{1,6})\s+(.+)$',
            extract=extract_header,
            description="Matches Markdown headers",
            examples=["# Title", "## Section"]
        ),
        "list_item": QueryPattern(
            pattern=r'^(\s*)[*+-]\s+(.+)$',
            extract=extract_list_item,
            description="Matches unordered list items",
            examples=["* Item", "- Point"]
        ),
        "code_block": QueryPattern(
            pattern=r'^```(\w*)$',
            extract=lambda m: {
                "type": "code_block",
                "language": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches code block delimiters",
            examples=["```python", "```"]
        )
    },
    
    PatternCategory.STRUCTURE: {
        "section": QueryPattern(
            pattern=lambda node: node["type"] == "header",
            extract=lambda node: {
                "type": "section",
                "level": node["level"],
                "title": node["content"],
                "children": node.get("children", [])
            },
            description="Matches document sections",
            examples=["# Section with content"]
        ),
        "list": QueryPattern(
            pattern=lambda node: node["type"] == "list_item",
            extract=lambda node: {
                "type": "list",
                "items": node.get("children", []),
                "indent": node["indent"]
            },
            description="Matches list structures",
            examples=["* Nested\n  * Items"]
        )
    },
    
    PatternCategory.DOCUMENTATION: {
        "metadata": QueryPattern(
            pattern=lambda node: node["type"] == "header" and node["level"] == 1,
            extract=lambda node: {
                "type": "metadata",
                "title": node["content"]
            },
            description="Matches document metadata",
            examples=["# Document Title"]
        ),
        "blockquote": QueryPattern(
            pattern=r'^\s*>\s*(.+)$',
            extract=lambda m: {
                "type": "blockquote",
                "content": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches blockquotes",
            examples=["> Quote text"]
        )
    },
    
    PatternCategory.SEMANTICS: {
        "link": QueryPattern(
            pattern=r'\[([^\]]+)\]\(([^)]+)\)',
            extract=lambda m: {
                "type": "link",
                "text": m.group(1),
                "url": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches Markdown links",
            examples=["[text](url)"]
        ),
        "image": QueryPattern(
            pattern=r'!\[([^\]]*)\]\(([^)]+)\)',
            extract=lambda m: {
                "type": "image",
                "alt": m.group(1),
                "src": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches image references",
            examples=["![alt](image.png)"]
        )
    }
}

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "document": {
        "can_contain": ["header", "list", "code_block", "blockquote"],
        "can_be_contained_by": []
    },
    "header": {
        "can_contain": ["link", "image"],
        "can_be_contained_by": ["document"]
    },
    "list": {
        "can_contain": ["list_item"],
        "can_be_contained_by": ["document", "list_item"]
    },
    "list_item": {
        "can_contain": ["list", "link", "image"],
        "can_be_contained_by": ["list"]
    },
    "code_block": {
        "can_be_contained_by": ["document"]
    }
}

def extract_markdown_features(ast: dict) -> dict:
    """Extract features that align with pattern categories."""
    features = {
        "syntax": {
            "headers": [],
            "code_blocks": [],
            "emphasis": []
        },
        "structure": {
            "sections": [],
            "lists": [],
            "tables": []
        },
        "semantics": {
            "links": [],
            "references": [],
            "definitions": []
        },
        "documentation": {
            "metadata": {},
            "comments": [],
            "blockquotes": []
        }
    }
    
    def process_node(node: dict):
        """Process a node and extract its features."""
        if not isinstance(node, dict):
            return
            
        node_type = node.get("type")
        
        # Syntax features
        if node_type == "header":
            features["syntax"]["headers"].append({
                "level": node.get("level"),
                "content": node.get("content"),
                "line": node.get("line")
            })
        elif node_type == "code_block":
            features["syntax"]["code_blocks"].append({
                "language": node.get("language"),
                "content": node.get("content"),
                "start_line": node.get("start_line"),
                "end_line": node.get("end_line")
            })
        elif node_type == "emphasis":
            features["syntax"]["emphasis"].append({
                "content": node.get("content"),
                "line": node.get("line")
            })
            
        # Structure features
        elif node_type == "list":
            features["structure"]["lists"].append({
                "items": node.get("items", []),
                "indent_level": node.get("indent_level"),
                "start_line": node.get("start_line"),
                "end_line": node.get("end_line")
            })
            
        # Semantic features
        elif node_type == "link":
            features["semantics"]["links"].append({
                "text": node.get("text"),
                "url": node.get("url"),
                "line": node.get("line")
            })
            
        # Documentation features
        elif node_type == "blockquote":
            features["documentation"]["blockquotes"].append({
                "content": node.get("content"),
                "line": node.get("line")
            })
        
        # Process children recursively
        for child in node.get("children", []):
            process_node(child)
    
    process_node(ast)
    return features

# Helper functions for specific feature extraction
def extract_markdown_headings(ast: dict) -> list:
    """Extract all headings with enhanced metadata."""
    features = extract_markdown_features(ast)
    return features["syntax"]["headers"]

def extract_markdown_code_blocks(ast: dict) -> list:
    """Extract all code blocks with enhanced metadata."""
    features = extract_markdown_features(ast)
    return features["syntax"]["code_blocks"]

def extract_markdown_links(ast: dict) -> list:
    """Extract all links with enhanced metadata."""
    features = extract_markdown_features(ast)
    return features["semantics"]["links"]

def extract_markdown_lists(ast: dict) -> list:
    """Extract all lists with enhanced metadata."""
    features = extract_markdown_features(ast)
    return features["structure"]["lists"]

def extract_markdown_blockquotes(ast: dict) -> list:
    """Extract all blockquotes with enhanced metadata."""
    features = extract_markdown_features(ast)
    return features["documentation"]["blockquotes"]

# Add new pattern category for repository learning patterns
MARKDOWN_PATTERNS_FOR_LEARNING = {
    "documentation_structure": {
        "typical_readme": QueryPattern(
            pattern=r'(?s)^# (.+?)\n\n(.*?)\n## (.+)',
            extract=lambda m: {
                "type": "readme_pattern",
                "title": m.group(1),
                "intro": m.group(2),
                "first_section": m.group(3),
                "is_standard_format": True
            },
            description="Matches typical README structure with title, intro, and sections",
            examples=["# Project\n\nDescription\n## Installation"]
        ),
        "api_documentation": QueryPattern(
            pattern=r'(?s)## API\s*\n(.+?)(?:\n##|\Z)',
            extract=lambda m: {
                "type": "api_doc_pattern",
                "content": m.group(1),
                "has_api_section": True
            },
            description="Matches API documentation sections",
            examples=["## API\nFunction details here\n## Other"]
        ),
        "code_example": QueryPattern(
            pattern=r'```(\w+)\n(.*?)```',
            extract=lambda m: {
                "type": "code_example_pattern",
                "language": m.group(1),
                "code": m.group(2),
                "has_example": True
            },
            description="Matches code examples with language specifications",
            examples=["```python\nprint('Hello')\n```"]
        ),
        "usage_example": QueryPattern(
            pattern=r'(?s)## (Usage|Examples?)\s*\n(.+?)(?:\n##|\Z)',
            extract=lambda m: {
                "type": "usage_example_pattern",
                "section_title": m.group(1),
                "content": m.group(2),
                "has_usage_section": True
            },
            description="Matches usage example sections",
            examples=["## Usage\nHow to use this library\n## API"]
        )
    },
    "best_practices": {
        "badges": QueryPattern(
            pattern=r'(!\[.+?\]\(.+?\))\s*',
            extract=lambda m: {
                "type": "badges_pattern",
                "badge": m.group(1),
                "has_badges": True
            },
            description="Matches status badges in documentation",
            examples=["![Build Status](https://travis-ci.org/user/repo.svg)"]
        ),
        "table_of_contents": QueryPattern(
            pattern=r'(?s)## Table of Contents\s*\n(.+?)(?:\n##|\Z)',
            extract=lambda m: {
                "type": "toc_pattern",
                "content": m.group(1),
                "has_toc": True
            },
            description="Matches table of contents sections",
            examples=["## Table of Contents\n* [Installation](#installation)"]
        ),
        "contribution_guidelines": QueryPattern(
            pattern=r'(?s)## Contribut(ing|ion)\s*\n(.+?)(?:\n##|\Z)',
            extract=lambda m: {
                "type": "contribution_pattern",
                "content": m.group(2),
                "has_contribution_guide": True
            },
            description="Matches contribution guideline sections",
            examples=["## Contributing\nHow to contribute\n## License"]
        )
    }
}

# Update the MARKDOWN_PATTERNS dictionary
MARKDOWN_PATTERNS = {
    # ... existing patterns ...
}

# Add the repository learning patterns to the main patterns
MARKDOWN_PATTERNS['REPOSITORY_LEARNING'] = MARKDOWN_PATTERNS_FOR_LEARNING

# Extend extract_markdown_features to include pattern extraction for learning
def extract_markdown_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """Extract patterns from markdown content for repository learning."""
    patterns = []
    
    # Process documentation structure patterns
    for pattern_name, pattern in MARKDOWN_PATTERNS_FOR_LEARNING["documentation_structure"].items():
        if hasattr(pattern.pattern, "__call__"):
            # Skip AST-based patterns, we need regex for now
            continue
            
        for match in re.finditer(pattern.pattern, content, re.MULTILINE | re.DOTALL):
            pattern_data = pattern.extract(match)
            patterns.append({
                "name": pattern_name,
                "type": pattern_data.get("type", "documentation_structure"),
                "content": match.group(0),
                "metadata": pattern_data,
                "confidence": 0.8
            })
    
    # Process best practices patterns
    for pattern_name, pattern in MARKDOWN_PATTERNS_FOR_LEARNING["best_practices"].items():
        if hasattr(pattern.pattern, "__call__"):
            # Skip AST-based patterns, we need regex for now
            continue
            
        for match in re.finditer(pattern.pattern, content, re.MULTILINE | re.DOTALL):
            pattern_data = pattern.extract(match)
            patterns.append({
                "name": pattern_name,
                "type": pattern_data.get("type", "best_practice"),
                "content": match.group(0),
                "metadata": pattern_data,
                "confidence": 0.75
            })
            
    return patterns
