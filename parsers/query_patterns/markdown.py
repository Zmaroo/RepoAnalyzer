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
        "level": len(match.group(1)),
        "content": match.group(2),
        "line_number": match.string.count('\n', 0, match.start()) + 1
    }

def extract_list_item(match: Match) -> Dict[str, Any]:
    """Extract list item information."""
    return {
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
                "language": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches code block delimiters",
            examples=["```python", "```"]
        )
    },
    
    PatternCategory.SEMANTICS: {
        "emphasis": QueryPattern(
            pattern=r'(\*\*|__)(.*?)\1|(\*|_)(.*?)\3',
            extract=lambda m: {
                "type": "strong" if m.group(1) else "emphasis",
                "content": m.group(2) or m.group(4),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches text emphasis",
            examples=["**bold**", "_italic_"]
        ),
        "inline_code": QueryPattern(
            pattern=r'`([^`]+)`',
            extract=lambda m: {
                "code": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches inline code",
            examples=["`code`"]
        )
    },
    
    PatternCategory.STRUCTURE: {
        "section": QueryPattern(
            pattern=r'^(#{1,6})\s+(.+?)\s*(?:{#([^}]+)})?\s*$',
            extract=lambda m: {
                "level": len(m.group(1)),
                "title": m.group(2),
                "id": m.group(3) if m.group(3) else None,
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches document sections",
            examples=["# Section {#section-id}"]
        ),
        "list": QueryPattern(
            pattern=r'^(\s*)(?:[*+-]|\d+\.)\s+(.+)$',
            extract=lambda m: {
                "indent": len(m.group(1)),
                "content": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches list structures",
            examples=["1. First", "  * Nested"]
        )
    },
    
    PatternCategory.DOCUMENTATION: {
        "metadata": QueryPattern(
            pattern=r'^\s*<!--\s*@(\w+):\s*(.+?)\s*-->$',
            extract=lambda m: {
                "key": m.group(1),
                "value": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches metadata comments",
            examples=["<!-- @author: John Doe -->"]
        ),
        "comment": QueryPattern(
            pattern=r'<!--(.*?)-->',
            extract=lambda m: {
                "content": m.group(1).strip(),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches HTML comments",
            examples=["<!-- Comment -->"]
        )
    },
    
    PatternCategory.CODE_PATTERNS: {
        "admonition": QueryPattern(
            pattern=r'^\s*(?:>|\|)\s*(?:\[!(\w+)\])?\s*(.+)$',
            extract=lambda m: {
                "type": m.group(1) if m.group(1) else "note",
                "content": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches admonition blocks",
            examples=["> [!NOTE] Important information"]
        ),
        "task_list": QueryPattern(
            pattern=r'^\s*[-*+]\s+\[([ xX])\]\s+(.+)$',
            extract=lambda m: {
                "completed": m.group(1).lower() == 'x',
                "task": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches task list items",
            examples=["- [x] Completed task"]
        )
    },
    
    PatternCategory.DEPENDENCIES: {
        "link_reference": QueryPattern(
            pattern=r'^\s*\[([^\]]+)\]:\s*(\S+)(?:\s+"([^"]+)")?$',
            extract=lambda m: {
                "label": m.group(1),
                "url": m.group(2),
                "title": m.group(3) if m.group(3) else None,
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches link references",
            examples=["[ref]: https://example.com \"Title\""]
        ),
        "image_reference": QueryPattern(
            pattern=r'!\[([^\]]*)\]\[([^\]]+)\]',
            extract=lambda m: {
                "alt": m.group(1),
                "ref": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches image references",
            examples=["![Alt text][image-ref]"]
        )
    },
    
    PatternCategory.BEST_PRACTICES: {
        "heading_hierarchy": QueryPattern(
            pattern=r'^(#{1,6})\s+(.+)$(?:\n(?!#).*)*(?:\n(#{1,6})\s+(.+)$)?',
            extract=lambda m: {
                "parent_level": len(m.group(1)),
                "parent_title": m.group(2),
                "child_level": len(m.group(3)) if m.group(3) else None,
                "child_title": m.group(4) if m.group(4) else None,
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "follows_hierarchy": m.group(3) and len(m.group(3)) <= len(m.group(1)) + 1
            },
            description="Checks heading hierarchy",
            examples=["# H1\n## H2"]
        ),
        "link_style": QueryPattern(
            pattern=r'\[([^\]]+)\]\(([^)]+)\)',
            extract=lambda m: {
                "text": m.group(1),
                "url": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "has_text": bool(m.group(1).strip()),
                "is_relative": not m.group(2).startswith(('http', 'https', 'ftp', 'mailto'))
            },
            description="Checks link formatting",
            examples=["[Link text](url)"]
        )
    },
    
    PatternCategory.COMMON_ISSUES: {
        "broken_reference": QueryPattern(
            pattern=r'\[([^\]]+)\]\[([^\]]+)\](?!.*\[\2\]:)',
            extract=lambda m: {
                "text": m.group(1),
                "ref": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "is_broken": True
            },
            description="Detects broken references",
            examples=["[Link][missing-ref]"]
        ),
        "inconsistent_list": QueryPattern(
            pattern=r'^(\s*)(?:[*+-]|\d+\.)\s+.*\n\1([*+-]|\d+\.)\s+',
            extract=lambda m: {
                "indent": len(m.group(1)),
                "markers": [m.group(1), m.group(2)],
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "is_consistent": m.group(1) == m.group(2)
            },
            description="Detects inconsistent list markers",
            examples=["* Item\n- Item"]
        )
    },
    
    PatternCategory.USER_PATTERNS: {
        "custom_container": QueryPattern(
            pattern=r'^\s*:::\s*(\w+)\s*$(.*?)^\s*:::$',
            extract=lambda m: {
                "type": m.group(1),
                "content": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches custom container blocks",
            examples=[":::note\nContent\n:::"]
        )
    }
}

# Add the repository learning patterns to the main patterns
MARKDOWN_PATTERNS[PatternCategory.LEARNING] = {
    "document_structure": QueryPattern(
        pattern=r'(?s)^#\s+([^\n]+)\n\n(.*?)(?=\n#\s|$)',
        extract=lambda m: {
            "title": m.group(1),
            "content": m.group(2),
            "type": "document_structure",
            "line_number": m.string.count('\n', 0, m.start()) + 1
        },
        description="Matches document structure patterns",
        examples=["# Title\n\nContent"]
    )
}

# Function to extract patterns for repository learning
def extract_markdown_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """Extract patterns from Markdown content for repository learning."""
    patterns = []
    
    # Process each pattern category
    for category in PatternCategory:
        if category in MARKDOWN_PATTERNS:
            category_patterns = MARKDOWN_PATTERNS[category]
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
        "can_contain": ["header", "list", "code_block", "blockquote"],
        "can_be_contained_by": []
    },
    "header": {
        "can_contain": ["link", "emphasis", "inline_code"],
        "can_be_contained_by": ["document"]
    },
    "list": {
        "can_contain": ["list_item", "task_list"],
        "can_be_contained_by": ["document", "list_item"]
    },
    "list_item": {
        "can_contain": ["emphasis", "link", "inline_code"],
        "can_be_contained_by": ["list"]
    },
    "code_block": {
        "can_be_contained_by": ["document"]
    },
    "custom_container": {
        "can_contain": ["header", "list", "code_block"],
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
