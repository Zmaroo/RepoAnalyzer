"""Query patterns for HTML files."""

from typing import Dict, Any, List, Match, Pattern
from dataclasses import dataclass
from parsers.types import FileType, QueryPattern, PatternCategory, PatternInfo
import re

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

# HTML patterns for documentation and syntax
HTML_PATTERNS = {
    PatternCategory.DOCUMENTATION: {
        'comment': PatternInfo(
            pattern=r'<!--(.*?)-->',
            extract=lambda match: {'content': match.group(1).strip()}
        ),
        'doctype': PatternInfo(
            pattern=r'<!DOCTYPE[^>]*>',
            extract=lambda match: {'content': match.group(0).strip()}
        ),
    },
    PatternCategory.SYNTAX: {
        'script': PatternInfo(
            pattern=r'<script[^>]*>(.*?)</script>',
            extract=lambda match: {
                'content': match.group(1).strip(),
                'attributes': re.findall(r'(\w+)=["\'](.*?)["\']', match.group(0))
            }
        ),
        'style': PatternInfo(
            pattern=r'<style[^>]*>(.*?)</style>',
            extract=lambda match: {
                'content': match.group(1).strip(),
                'attributes': re.findall(r'(\w+)=["\'](.*?)["\']', match.group(0))
            }
        ),
        'element': PatternInfo(
            pattern=r'<([a-zA-Z0-9_-]+)[^>]*>(.*?)</\1>',
            extract=lambda match: {
                'tag': match.group(1),
                'content': match.group(2),
                'attributes': re.findall(r'(\w+)=["\'](.*?)["\']', match.group(0))
            }
        ),
        'void_element': PatternInfo(
            pattern=r'<([a-zA-Z0-9_-]+)([^>]*)\s*/>',
            extract=lambda match: {
                'tag': match.group(1),
                'attributes': re.findall(r'(\w+)=["\'](.*?)["\']', match.group(2))
            }
        ),
        'attribute': PatternInfo(
            pattern=r'(\w+)=["\'](.*?)["\']',
            extract=lambda match: {
                'name': match.group(1),
                'value': match.group(2)
            }
        ),
    }
}

# HTML patterns specifically for repository learning
HTML_PATTERNS_FOR_LEARNING = {
    # Semantic HTML structure patterns
    'semantic_elements': PatternInfo(
        pattern=r'<(article|section|nav|aside|header|footer|main|figure|figcaption)[^>]*>.*?</\1>',
        extract=lambda match: {
            'tag': match.group(1),
            'content': match.group(0),
            'semantic_type': 'layout'
        }
    ),
    
    # Accessibility patterns
    'aria_attributes': PatternInfo(
        pattern=r'(aria-\w+)=["\'](.*?)["\']',
        extract=lambda match: {
            'attribute': match.group(1),
            'value': match.group(2),
            'category': 'accessibility'
        }
    ),
    
    # Component patterns
    'form_patterns': PatternInfo(
        pattern=r'<form[^>]*>(.*?)</form>',
        extract=lambda match: {
            'content': match.group(0),
            'fields': re.findall(r'<(input|select|textarea|button)[^>]*>', match.group(1)),
            'component_type': 'form'
        }
    ),
    
    'navigation_patterns': PatternInfo(
        pattern=r'<nav[^>]*>(.*?)</nav>',
        extract=lambda match: {
            'content': match.group(0),
            'items': re.findall(r'<li[^>]*>(.*?)</li>', match.group(1)),
            'component_type': 'navigation'
        }
    ),
    
    'table_patterns': PatternInfo(
        pattern=r'<table[^>]*>(.*?)</table>',
        extract=lambda match: {
            'content': match.group(0),
            'has_header': bool(re.search(r'<th[^>]*>', match.group(1))),
            'rows': len(re.findall(r'<tr[^>]*>', match.group(1))),
            'component_type': 'table'
        }
    ),
    
    # Naming convention patterns
    'id_conventions': PatternInfo(
        pattern=r'id=["\']([\w-]+)["\']',
        extract=lambda match: {
            'id': match.group(1),
            'convention': 'kebab-case' if '-' in match.group(1) else 
                         'camelCase' if match.group(1)[0].islower() and any(c.isupper() for c in match.group(1)) else
                         'snake_case' if '_' in match.group(1) else 'unknown'
        }
    ),
    
    'class_conventions': PatternInfo(
        pattern=r'class=["\']([\w\s-]+)["\']',
        extract=lambda match: {
            'classes': match.group(1).split(),
            'convention': 'utility' if len(match.group(1).split()) > 3 else 'semantic'
        }
    ),
    
    # Data attribute patterns
    'data_attributes': PatternInfo(
        pattern=r'(data-\w+)=["\'](.*?)["\']',
        extract=lambda match: {
            'attribute': match.group(1),
            'value': match.group(2),
            'category': 'data'
        }
    ),
}

# Update the HTML_PATTERNS dictionary with the learning patterns
HTML_PATTERNS[PatternCategory.LEARNING] = HTML_PATTERNS_FOR_LEARNING

def extract_html_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """
    Extract HTML patterns from content for repository learning.
    
    Args:
        content: The HTML content to analyze
        
    Returns:
        List of extracted patterns with metadata
    """
    patterns = []
    
    # Compile patterns
    compiled_patterns = {
        name: re.compile(pattern_info.pattern, re.DOTALL)
        for name, pattern_info in HTML_PATTERNS_FOR_LEARNING.items()
    }
    
    # Process structural patterns (semantic elements, components)
    structure_patterns = ['semantic_elements', 'form_patterns', 'navigation_patterns', 'table_patterns']
    for pattern_name in structure_patterns:
        pattern = compiled_patterns[pattern_name]
        pattern_info = HTML_PATTERNS_FOR_LEARNING[pattern_name]
        
        for match in pattern.finditer(content):
            extracted = pattern_info.extract(match)
            patterns.append({
                'name': f'html_{pattern_name}',
                'content': extracted.get('content', ''),
                'metadata': extracted,
                'confidence': 0.85
            })
    
    # Process naming conventions
    convention_patterns = ['id_conventions', 'class_conventions']
    convention_counts = {}  # Track frequency of conventions
    
    for pattern_name in convention_patterns:
        pattern = compiled_patterns[pattern_name]
        pattern_info = HTML_PATTERNS_FOR_LEARNING[pattern_name]
        
        for match in pattern.finditer(content):
            extracted = pattern_info.extract(match)
            convention = extracted.get('convention')
            
            if convention:
                convention_counts[convention] = convention_counts.get(convention, 0) + 1
    
    # Add naming convention patterns based on frequency
    for convention, count in convention_counts.items():
        if count >= 3:  # Only include conventions with significant frequency
            patterns.append({
                'name': f'html_naming_convention_{convention}',
                'content': f"HTML naming convention: {convention}",
                'metadata': {
                    'convention_type': convention,
                    'frequency': count
                },
                'confidence': min(0.7 + (count / 20), 0.95)  # Higher confidence with more instances
            })
    
    # Process accessibility patterns
    accessibility_attributes = {}
    for match in compiled_patterns['aria_attributes'].finditer(content):
        extracted = HTML_PATTERNS_FOR_LEARNING['aria_attributes'].extract(match)
        attribute = extracted.get('attribute')
        if attribute:
            accessibility_attributes[attribute] = accessibility_attributes.get(attribute, 0) + 1
    
    if accessibility_attributes:
        patterns.append({
            'name': 'html_accessibility_pattern',
            'content': ', '.join(sorted(accessibility_attributes.keys())),
            'metadata': {
                'attributes': accessibility_attributes,
                'pattern_type': 'accessibility'
            },
            'confidence': 0.9 if len(accessibility_attributes) > 3 else 0.8
        })
    
    # Process data attribute patterns
    data_attributes = {}
    for match in compiled_patterns['data_attributes'].finditer(content):
        extracted = HTML_PATTERNS_FOR_LEARNING['data_attributes'].extract(match)
        attribute = extracted.get('attribute')
        if attribute:
            data_attributes[attribute] = data_attributes.get(attribute, 0) + 1
    
    if data_attributes:
        patterns.append({
            'name': 'html_data_attributes_pattern',
            'content': ', '.join(sorted(data_attributes.keys())),
            'metadata': {
                'attributes': data_attributes,
                'pattern_type': 'data'
            },
            'confidence': 0.85 if len(data_attributes) > 3 else 0.75
        })
    
    return patterns