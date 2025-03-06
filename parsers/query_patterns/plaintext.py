"""
Query patterns for plaintext files with enhanced pattern support.
"""

from typing import Dict, Any, List, Match, Optional
from dataclasses import dataclass
from parsers.types import FileType, QueryPattern, PatternCategory, PatternPurpose
import re

# Language identifier
LANGUAGE = "plaintext"

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
        "level": len(match.group(1)) if match.group(1) else (1 if match.group(4) and match.group(4)[0] == '=' else 2),
        "content": match.group(2) if match.group(2) else match.group(3),
        "line_number": match.string.count('\n', 0, match.start()) + 1
    }

# Plaintext patterns for all categories
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
            pattern=r'^(={2,}|-{2,}|\*{2,}|#{1,6})\s*(.+?)(?:\s*\1)?$|^(.+)\n(=+|-+)$',
            extract=extract_header,
            description="Matches headers",
            examples=["# Title", "=== Title ===", "Title\n===="]
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
        ),
        "section": QueryPattern(
            pattern=r'^(.*?)\n[=\-]{3,}\n',
            extract=lambda m: {
                "type": "section",
                "title": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches sections",
            examples=["Section Title\n============"]
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
        ),
        "comment": QueryPattern(
            pattern=r'^(?://|#)\s*(.+)$',
            extract=lambda m: {
                "type": "comment",
                "content": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches comments",
            examples=["# Comment", "// Comment"]
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
        ),
        "path": QueryPattern(
            pattern=r'(?:^|[\s"])(?:/[\w.-]+)+(?:[\s"]|$)',
            extract=lambda m: {
                "type": "path",
                "path": m.group(0).strip(),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches file paths",
            examples=["/usr/local/bin"]
        )
    },
    
    PatternCategory.CODE_PATTERNS: {
        "fenced_code": QueryPattern(
            pattern=r'```(\w*)\n(.*?)```',
            extract=lambda m: {
                "type": "fenced_code",
                "language": m.group(1),
                "content": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches fenced code blocks",
            examples=["```python\nprint('hello')\n```"]
        ),
        "inline_code": QueryPattern(
            pattern=r'`([^`]+)`',
            extract=lambda m: {
                "type": "inline_code",
                "content": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches inline code",
            examples=["`code`"]
        )
    },
    
    PatternCategory.DEPENDENCIES: {
        "reference": QueryPattern(
            pattern=r'\[([^\]]+)\]\(([^\)]+)\)',
            extract=lambda m: {
                "type": "reference",
                "text": m.group(1),
                "target": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches references",
            examples=["[link](target)"]
        ),
        "include": QueryPattern(
            pattern=r'(?:include|require|import)\s+["\'<]([^\'">\n]+)[\'">]',
            extract=lambda m: {
                "type": "include",
                "path": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches include statements",
            examples=["include 'file.txt'"]
        )
    },
    
    PatternCategory.BEST_PRACTICES: {
        "todo": QueryPattern(
            pattern=r'(?:TODO|FIXME|XXX|HACK):\s*(.+)$',
            extract=lambda m: {
                "type": "todo",
                "content": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches TODO comments",
            examples=["TODO: Fix this"]
        ),
        "citation": QueryPattern(
            pattern=r'^\s*>\s*(.+)$',
            extract=lambda m: {
                "type": "citation",
                "content": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches citations",
            examples=["> Quoted text"]
        )
    },
    
    PatternCategory.COMMON_ISSUES: {
        "broken_link": QueryPattern(
            pattern=r'\[([^\]]*)\]\(\s*\)',
            extract=lambda m: {
                "type": "broken_link",
                "text": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Detects broken links",
            examples=["[link]()"]
        ),
        "trailing_space": QueryPattern(
            pattern=r'[ \t]+$',
            extract=lambda m: {
                "type": "trailing_space",
                "content": m.group(0),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Detects trailing whitespace",
            examples=["Line with spaces   "]
        )
    },
    
    PatternCategory.USER_PATTERNS: {
        "custom_list": QueryPattern(
            pattern=r'^\s*(?:[→➢➤▶►▸▹▻❯❱]|\(\d+\)|\[\d+\])\s+(.+)$',
            extract=lambda m: {
                "type": "custom_list",
                "content": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches custom list markers",
            examples=["→ Item", "(1) Item"]
        ),
        "custom_section": QueryPattern(
            pattern=r'^[^\w\s][-=]{3,}[^\w\s]*$',
            extract=lambda m: {
                "type": "custom_section",
                "marker": m.group(0),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches custom section markers",
            examples=["---===---"]
        )
    }
}

# Add repository learning patterns
PLAINTEXT_PATTERNS[PatternCategory.LEARNING] = {
    "document_structure": QueryPattern(
        pattern=r'(?:^|\n)([^\n]+)\n[=\-]{3,}\n(.*?)(?=\n[^\n]+\n[=\-]{3,}\n|\Z)',
        extract=lambda m: {
            "type": "document_structure",
            "title": m.group(1),
            "content": m.group(2),
            "line_number": m.string.count('\n', 0, m.start()) + 1
        },
        description="Matches document structure patterns",
        examples=["Title\n=====\nContent"]
    ),
    "list_structure": QueryPattern(
        pattern=r'(?:^|\n)(?:\s*[-*+•]\s+[^\n]+\n)+',
        extract=lambda m: {
            "type": "list_structure",
            "content": m.group(0),
            "items_count": len(re.findall(r'^\s*[-*+•]', m.group(0), re.MULTILINE)),
            "line_number": m.string.count('\n', 0, m.start()) + 1
        },
        description="Matches list structure patterns",
        examples=["* Item 1\n* Item 2"]
    ),
    "formatting_patterns": QueryPattern(
        pattern=r'(?:\*\*[^*]+\*\*|__[^_]+__|_[^_]+_|\*[^*]+\*|`[^`]+`|\[[^\]]+\]\([^\)]+\))',
        extract=lambda m: {
            "type": "formatting_pattern",
            "content": m.group(0),
            "format_type": "bold" if m.group(0).startswith(("**", "__")) else
                          "italic" if m.group(0).startswith(("*", "_")) else
                          "code" if m.group(0).startswith("`") else
                          "link",
            "line_number": m.string.count('\n', 0, m.start()) + 1
        },
        description="Matches text formatting patterns",
        examples=["**bold**", "_italic_", "`code`"]
    )
}

# Function to extract patterns for repository learning
def extract_plaintext_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """Extract patterns from plaintext content for repository learning."""
    patterns = []
    
    # Process each pattern category
    for category in PatternCategory:
        if category in PLAINTEXT_PATTERNS:
            category_patterns = PLAINTEXT_PATTERNS[category]
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
        "can_contain": ["header", "paragraph", "list_item", "numbered_item", "code_block", "section"],
        "can_be_contained_by": []
    },
    "section": {
        "can_contain": ["paragraph", "list_item", "code_block"],
        "can_be_contained_by": ["document"]
    },
    "paragraph": {
        "can_contain": ["url", "email", "path", "inline_code"],
        "can_be_contained_by": ["document", "section"]
    },
    "list_item": {
        "can_contain": ["url", "email", "path", "inline_code"],
        "can_be_contained_by": ["document", "section"]
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