"""
Query patterns for Markdown files with enhanced documentation support.
"""

from parsers.file_classification import FileType
from parsers.query_patterns import PATTERN_CATEGORIES
from parsers.pattern_processor import QueryPattern, PatternCategory
from typing import Dict, Any, Match

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
