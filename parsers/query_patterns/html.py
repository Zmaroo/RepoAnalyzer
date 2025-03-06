"""Query patterns for HTML files with enhanced pattern support."""

from typing import Dict, Any, List, Match
from dataclasses import dataclass
from parsers.types import FileType, QueryPattern, PatternCategory
import re

def extract_element(match: Match) -> Dict[str, Any]:
    """Extract element information."""
    return {
        "type": "element",
        "tag": match.group(1),
        "attributes": match.group(2) if match.group(2) else "",
        "content": match.group(3) if match.group(3) else "",
        "line_number": match.string.count('\n', 0, match.start()) + 1
    }

def extract_attribute(match: Match) -> Dict[str, Any]:
    """Extract attribute information."""
    return {
        "type": "attribute",
        "name": match.group(1),
        "value": match.group(2) if match.group(2) else "",
        "line_number": match.string.count('\n', 0, match.start()) + 1
    }

def extract_script(match: Match) -> Dict[str, Any]:
    """Extract script information."""
    return {
        "type": "script",
        "attributes": match.group(1) if match.group(1) else "",
        "content": match.group(2) if match.group(2) else "",
        "line_number": match.string.count('\n', 0, match.start()) + 1
    }

HTML_PATTERNS = {
    PatternCategory.SYNTAX: {
        "element": QueryPattern(
            pattern=r'<(\w+)([^>]*)(?:>(.*?)</\1>|/>)',
            extract=extract_element,
            description="Matches HTML elements",
            examples=["<div class=\"container\">content</div>", "<img src=\"image.jpg\" />"]
        ),
        "attribute": QueryPattern(
            pattern=r'\s(\w+)(?:=(["\'][^"\']*["\']))?',
            extract=extract_attribute,
            description="Matches HTML attributes",
            examples=["class=\"container\"", "disabled"]
        ),
        "doctype": QueryPattern(
            pattern=r'<!DOCTYPE[^>]*>',
            extract=lambda m: {
                "type": "doctype",
                "declaration": m.group(0),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches DOCTYPE declarations",
            examples=["<!DOCTYPE html>"]
        ),
        "text_content": QueryPattern(
            pattern=r'>([^<]+)<',
            extract=lambda m: {
                "type": "text",
                "content": m.group(1).strip(),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches text content",
            examples=[">Some text<"]
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
            examples=["<head><title>Page Title</title></head>"]
        ),
        "body": QueryPattern(
            pattern=r'<body[^>]*>(.*?)</body>',
            extract=lambda m: {
                "type": "body",
                "content": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches body section",
            examples=["<body><div>content</div></body>"]
        ),
        "container": QueryPattern(
            pattern=r'<(div|section|article|main|aside|nav|header|footer)[^>]*>(.*?)</\1>',
            extract=lambda m: {
                "type": "container",
                "tag": m.group(1),
                "content": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches structural containers",
            examples=["<div class=\"container\">content</div>"]
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
        "meta": QueryPattern(
            pattern=r'<meta\s+([^>]*)>',
            extract=lambda m: {
                "type": "meta",
                "attributes": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches meta tags",
            examples=["<meta name=\"description\" content=\"Page description\">"]
        ),
        "aria_label": QueryPattern(
            pattern=r'aria-label=(["\'][^"\']*["\'])',
            extract=lambda m: {
                "type": "aria_label",
                "label": m.group(1).strip('\'"'),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches ARIA labels",
            examples=["aria-label=\"Close button\""]
        )
    },
    
    PatternCategory.SEMANTICS: {
        "heading": QueryPattern(
            pattern=r'<(h[1-6])[^>]*>(.*?)</\1>',
            extract=lambda m: {
                "type": "heading",
                "level": int(m.group(1)[1]),
                "content": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches heading elements",
            examples=["<h1>Page Title</h1>"]
        ),
        "link": QueryPattern(
            pattern=r'<a\s+([^>]*)>(.*?)</a>',
            extract=lambda m: {
                "type": "link",
                "attributes": m.group(1),
                "content": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches link elements",
            examples=["<a href=\"page.html\">Link Text</a>"]
        ),
        "list": QueryPattern(
            pattern=r'<(ul|ol)[^>]*>(.*?)</\1>',
            extract=lambda m: {
                "type": "list",
                "list_type": m.group(1),
                "content": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches list elements",
            examples=["<ul><li>Item</li></ul>"]
        )
    },
    
    PatternCategory.CODE_PATTERNS: {
        "script": QueryPattern(
            pattern=r'<script([^>]*)>(.*?)</script>',
            extract=extract_script,
            description="Matches script elements",
            examples=["<script>console.log('Hello');</script>"]
        ),
        "style": QueryPattern(
            pattern=r'<style[^>]*>(.*?)</style>',
            extract=lambda m: {
                "type": "style",
                "content": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches style elements",
            examples=["<style>.class { color: red; }</style>"]
        ),
        "template": QueryPattern(
            pattern=r'<template[^>]*>(.*?)</template>',
            extract=lambda m: {
                "type": "template",
                "content": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches template elements",
            examples=["<template><div>template content</div></template>"]
        )
    },
    
    PatternCategory.DEPENDENCIES: {
        "stylesheet": QueryPattern(
            pattern=r'<link\s+[^>]*rel=["\'](stylesheet)["\'][^>]*>',
            extract=lambda m: {
                "type": "stylesheet",
                "attributes": m.group(0),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches stylesheet links",
            examples=["<link rel=\"stylesheet\" href=\"style.css\">"]
        ),
        "script_src": QueryPattern(
            pattern=r'<script\s+[^>]*src=["\'](.*?)["\'][^>]*>',
            extract=lambda m: {
                "type": "script_src",
                "src": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches external script references",
            examples=["<script src=\"app.js\"></script>"]
        ),
        "import_map": QueryPattern(
            pattern=r'<script\s+type=["\'](importmap)["\'][^>]*>(.*?)</script>',
            extract=lambda m: {
                "type": "import_map",
                "content": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches import maps",
            examples=["<script type=\"importmap\">{\"imports\":{}}</script>"]
        )
    },
    
    PatternCategory.BEST_PRACTICES: {
        "semantic_element": QueryPattern(
            pattern=r'<(article|aside|details|figcaption|figure|footer|header|main|mark|nav|section|time|summary)[^>]*>',
            extract=lambda m: {
                "type": "semantic_element",
                "tag": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Checks semantic HTML5 element usage",
            examples=["<article>", "<nav>"]
        ),
        "accessibility": QueryPattern(
            pattern=r'(?:aria-[a-z]+|role)=["\'](.*?)["\']',
            extract=lambda m: {
                "type": "accessibility",
                "attribute": m.group(0).split('=')[0],
                "value": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Checks accessibility attributes",
            examples=["role=\"button\"", "aria-hidden=\"true\""]
        )
    },
    
    PatternCategory.COMMON_ISSUES: {
        "missing_alt": QueryPattern(
            pattern=r'<img[^>]+(?!alt=)[^>]*>',
            extract=lambda m: {
                "type": "missing_alt",
                "element": m.group(0),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "needs_alt": True
            },
            description="Detects images missing alt attributes",
            examples=["<img src=\"image.jpg\">"]
        ),
        "inline_style": QueryPattern(
            pattern=r'style=["\'](.*?)["\']',
            extract=lambda m: {
                "type": "inline_style",
                "style": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "is_inline": True
            },
            description="Detects inline styles",
            examples=["style=\"color: red;\""]
        )
    },
    
    PatternCategory.USER_PATTERNS: {
        "custom_element": QueryPattern(
            pattern=r'<([a-z]+-[a-z-]+)([^>]*)(?:>(.*?)</\1>|/>)',
            extract=lambda m: {
                "type": "custom_element",
                "tag": m.group(1),
                "attributes": m.group(2) if m.group(2) else "",
                "content": m.group(3) if m.group(3) else "",
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches custom elements",
            examples=["<my-component>content</my-component>"]
        ),
        "custom_attribute": QueryPattern(
            pattern=r'\sdata-[a-z-]+=["\'](.*?)["\']',
            extract=lambda m: {
                "type": "custom_attribute",
                "attribute": m.group(0).split('=')[0].strip(),
                "value": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches custom data attributes",
            examples=["data-custom=\"value\""]
        )
    }
}

# Add the repository learning patterns
HTML_PATTERNS[PatternCategory.LEARNING] = {
    "structure_patterns": QueryPattern(
        pattern=r'<(div|section|article|main)[^>]*>.*?</\1>',
        extract=lambda m: {
            "type": "structure_pattern",
            "tag": m.group(1),
            "content": m.group(0),
            "line_number": m.string.count('\n', 0, m.start()) + 1,
            "nesting_level": len(re.findall(r'<div|<section|<article|<main', m.group(0)))
        },
        description="Learns structural patterns",
        examples=["<div class=\"container\"><div class=\"row\">content</div></div>"]
    ),
    "component_patterns": QueryPattern(
        pattern=r'<([a-z]+-[a-z-]+|div\s+class=["\'](component|widget|module)["\'])[^>]*>.*?</(?:\1|div)>',
        extract=lambda m: {
            "type": "component_pattern",
            "identifier": m.group(1),
            "content": m.group(0),
            "line_number": m.string.count('\n', 0, m.start()) + 1,
            "is_custom_element": bool(re.match(r'[a-z]+-[a-z-]+', m.group(1)))
        },
        description="Learns component patterns",
        examples=["<my-component>", "<div class=\"component\">"]
    )
}

# Function to extract patterns for repository learning
def extract_html_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """Extract patterns from HTML content for repository learning."""
    patterns = []
    
    # Process each pattern category
    for category in PatternCategory:
        if category in HTML_PATTERNS:
            category_patterns = HTML_PATTERNS[category]
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
        "can_contain": ["head", "body"],
        "can_be_contained_by": []
    },
    "head": {
        "can_contain": ["meta", "title", "link", "script", "style"],
        "can_be_contained_by": ["document"]
    },
    "body": {
        "can_contain": ["container", "heading", "list", "link", "custom_element"],
        "can_be_contained_by": ["document"]
    },
    "container": {
        "can_contain": ["container", "heading", "list", "link", "custom_element"],
        "can_be_contained_by": ["body", "container"]
    },
    "list": {
        "can_contain": ["list_item"],
        "can_be_contained_by": ["container", "body"]
    }
}

def extract_html_features(ast: dict) -> dict:
    """Extract features that align with pattern categories."""
    features = {
        "syntax": {
            "elements": [],
            "attributes": [],
            "doctypes": [],
            "text_nodes": []
        },
        "structure": {
            "heads": [],
            "bodies": [],
            "containers": []
        },
        "semantics": {
            "headings": [],
            "links": [],
            "lists": []
        },
        "documentation": {
            "comments": [],
            "metas": [],
            "aria_labels": []
        }
    }
    return features