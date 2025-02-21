"""Query patterns for plaintext files."""

from parsers.pattern_processor import QueryPattern, PatternCategory
from typing import Dict, Any, Match

def extract_list_item(match: Match) -> Dict[str, Any]:
    """Extract list item information."""
    return {
        "type": "list_item",
        "content": match.group(1),
        "line_number": match.string.count('\n', 0, match.start()) + 1
    }

def extract_header(match: Match) -> Dict[str, Any]:
    """Extract header information."""
    return {
        "type": "header",
        "level": len(match.group(1)),
        "content": match.group(2),
        "line_number": match.string.count('\n', 0, match.start()) + 1
    }

PLAINTEXT_PATTERNS = {
    PatternCategory.SYNTAX: {
        "list_item": QueryPattern(
            pattern=r'^\s*[-*+•]\s+(.+)$',
            extract=extract_list_item,
            description="Matches unordered list items",
            examples=["* Item", "- Point"]
        ),
        "numbered_item": QueryPattern(
            pattern=r'^\s*\d+[.)]\s+(.+)$',
            extract=lambda m: {
                "type": "numbered_item",
                "content": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches numbered list items",
            examples=["1. First", "2. Second"]
        ),
        "code_block": QueryPattern(
            pattern=r'^(?:\s{4,}|\t+)(.+)$',
            extract=lambda m: {
                "type": "code_block",
                "content": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches indented code blocks",
            examples=["    code here", "\tcode here"]
        )
    },
    
    PatternCategory.STRUCTURE: {
        "header": QueryPattern(
            pattern=r'^(={2,}|-{2,}|\*{2,}|#{1,6})\s*(.+?)(?:\s*\1)?$',
            extract=extract_header,
            description="Matches headers",
            examples=["# Title", "=== Title ==="]
        ),
        "paragraph": QueryPattern(
            pattern=r'^(?!\s*[-*+•]|\d+[.)]|\s{4}|\t|\|)(.+)$',
            extract=lambda m: {
                "type": "paragraph",
                "content": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches paragraphs",
            examples=["This is a paragraph"]
        )
    },
    
    PatternCategory.DOCUMENTATION: {
        "metadata": QueryPattern(
            pattern=r'^@(\w+):\s*(.+)$',
            extract=lambda m: {
                "type": "metadata",
                "key": m.group(1),
                "value": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches metadata tags",
            examples=["@author: John Doe"]
        )
    },
    
    PatternCategory.SEMANTICS: {
        "url": QueryPattern(
            pattern=r'https?://\S+',
            extract=lambda m: {
                "type": "url",
                "url": m.group(0),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches URLs",
            examples=["https://example.com"]
        ),
        "email": QueryPattern(
            pattern=r'\b[\w\.-]+@[\w\.-]+\.\w+\b',
            extract=lambda m: {
                "type": "email",
                "address": m.group(0),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches email addresses",
            examples=["user@example.com"]
        )
    }
}

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "document": {
        "can_contain": ["header", "paragraph", "list_item", "numbered_item", "code_block"],
        "can_be_contained_by": []
    },
    "paragraph": {
        "can_contain": ["url", "email"],
        "can_be_contained_by": ["document"]
    },
    "list_item": {
        "can_contain": ["url", "email"],
        "can_be_contained_by": ["document"]
    }
}

def extract_plaintext_features(node: dict) -> dict:
    """Extract features from plaintext AST nodes."""
    features = {
        "structure": {
            "sections": [],
            "paragraphs": []
        },
        "syntax": {
            "lists": [],
            "code_blocks": [],
            "tables": []
        },
        "semantics": {
            "references": []
        },
        "documentation": {
            "headers": [],
            "metadata": {}
        }
    }
    
    def process_node(node: dict):
        if not isinstance(node, dict):
            return
            
        node_type = node.get("type")
        if node_type == "section":
            features["structure"]["sections"].append(node)
        elif node_type == "paragraph":
            features["structure"]["paragraphs"].append(node)
        elif node_type in ("bullet_list", "numbered_list"):
            features["syntax"]["lists"].append(node)
        elif node_type == "code_block":
            features["syntax"]["code_blocks"].append(node)
        elif node_type == "table":
            features["syntax"]["tables"].append(node)
        elif node_type in ("url", "email", "path"):
            features["semantics"]["references"].append(node)
        elif node_type == "header":
            features["documentation"]["headers"].append(node)
        elif node_type == "metadata":
            features["documentation"]["metadata"][node["key"]] = node["value"]
        
        # Process children
        for child in node.get("children", []):
            process_node(child)
    
    process_node(node)
    return features 