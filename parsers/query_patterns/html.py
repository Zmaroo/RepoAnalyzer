"""Query patterns for HTML files."""

from parsers.pattern_processor import QueryPattern, PatternCategory
from typing import Dict, Any, Match

def extract_element(match: Match) -> Dict[str, Any]:
    """Extract element information."""
    return {
        "type": "element",
        "tag": match.group(1),
        "attributes_raw": match.group(2),
        "content": match.group(3),
        "line_number": match.string.count('\n', 0, match.start()) + 1
    }

HTML_PATTERNS = {
    PatternCategory.SYNTAX: {
        "element": QueryPattern(
            pattern=r'<(\w+)([^>]*)>(.*?)</\1>',
            extract=extract_element,
            description="Matches HTML elements",
            examples=["<div class='container'>content</div>"]
        ),
        "script": QueryPattern(
            pattern=r'<script[^>]*>(.*?)</script>',
            extract=lambda m: {
                "type": "script",
                "content": m.group(1).strip(),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches script elements",
            examples=["<script>console.log('test');</script>"]
        ),
        "style": QueryPattern(
            pattern=r'<style[^>]*>(.*?)</style>',
            extract=lambda m: {
                "type": "style",
                "content": m.group(1).strip(),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches style elements",
            examples=["<style>.class { color: red; }</style>"]
        )
    },
    
    PatternCategory.STRUCTURE: {
        "head": QueryPattern(
            pattern=r'<head[^>]*>(.*?)</head>',
            extract=lambda m: {
                "type": "head",
                "content": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches head section",
            examples=["<head><title>Page</title></head>"]
        ),
        "body": QueryPattern(
            pattern=r'<body[^>]*>(.*?)</body>',
            extract=lambda m: {
                "type": "body",
                "content": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches body section",
            examples=["<body class='main'>content</body>"]
        ),
        "form": QueryPattern(
            pattern=r'<form([^>]*)>(.*?)</form>',
            extract=lambda m: {
                "type": "form",
                "attributes": m.group(1),
                "content": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches form elements",
            examples=["<form action='/submit'>fields</form>"]
        )
    },
    
    PatternCategory.DOCUMENTATION: {
        "comment": QueryPattern(
            pattern=r'<!--(.*?)-->',
            extract=lambda m: {
                "type": "comment",
                "content": m.group(1).strip(),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches HTML comments",
            examples=["<!-- Navigation menu -->"]
        ),
        "doctype": QueryPattern(
            pattern=r'<!DOCTYPE\s+([^>]+)>',
            extract=lambda m: {
                "type": "doctype",
                "content": m.group(1).strip(),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches DOCTYPE declarations",
            examples=["<!DOCTYPE html>"]
        )
    },
    
    PatternCategory.SEMANTICS: {
        "meta": QueryPattern(
            pattern=r'<meta\s+([^>]+)>',
            extract=lambda m: {
                "type": "meta",
                "attributes": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches meta tags",
            examples=["<meta charset='utf-8'>"]
        ),
        "link": QueryPattern(
            pattern=r'<link\s+([^>]+)>',
            extract=lambda m: {
                "type": "link",
                "attributes": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches link elements",
            examples=["<link rel='stylesheet' href='style.css'>"]
        ),
        "aria": QueryPattern(
            pattern=r'\b(aria-\w+)=[\'"]([^\'"]*)[\'"]',
            extract=lambda m: {
                "type": "aria",
                "attribute": m.group(1),
                "value": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches ARIA attributes",
            examples=["aria-label='Navigation'"]
        )
    }
}

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "element": {
        "can_contain": ["element", "comment"],
        "can_be_contained_by": ["element", "body", "head"]
    },
    "head": {
        "can_contain": ["meta", "link", "style", "script"],
        "can_be_contained_by": ["html"]
    },
    "body": {
        "can_contain": ["element", "script"],
        "can_be_contained_by": ["html"]
    },
    "form": {
        "can_contain": ["element"],
        "can_be_contained_by": ["element", "body"]
    }
}