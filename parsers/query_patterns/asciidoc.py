"""Query patterns for AsciiDoc files with enhanced pattern support."""

from typing import Dict, Any, List, Match
from dataclasses import dataclass
from parsers.types import FileType, QueryPattern, PatternCategory
import re

def extract_header(match: Match) -> Dict[str, Any]:
    """Extract header information."""
    return {
        "type": "header",
        "title": match.group(1),
        "line_number": match.string.count('\n', 0, match.start()) + 1
    }

def extract_section(match: Match) -> Dict[str, Any]:
    """Extract section information."""
    return {
        "type": "section",
        "level": len(match.group(1)),
        "title": match.group(2),
        "line_number": match.string.count('\n', 0, match.start()) + 1
    }

def extract_attribute(match: Match) -> Dict[str, Any]:
    """Extract attribute information."""
    return {
        "type": "attribute",
        "name": match.group(1),
        "value": match.group(2),
        "line_number": match.string.count('\n', 0, match.start()) + 1
    }

ASCIIDOC_PATTERNS = {
    PatternCategory.SYNTAX: {
        "header": QueryPattern(
            pattern=r'^=\s+(.+)$',
            extract=extract_header,
            description="Matches AsciiDoc document headers",
            examples=["= Document Title"]
        ),
        "section": QueryPattern(
            pattern=r'^(=+)\s+(.+)$',
            extract=extract_section,
            description="Matches AsciiDoc section headers",
            examples=["== Section Title", "=== Subsection Title"]
        ),
        "attribute": QueryPattern(
            pattern=r'^:([^:]+):\s*(.*)$',
            extract=extract_attribute,
            description="Matches AsciiDoc attributes",
            examples=[":attribute-name: value"]
        ),
        "block": QueryPattern(
            pattern=r'^(----|\[.*?\])\s*$',
            extract=lambda m: {
                "type": "block",
                "delimiter": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches AsciiDoc blocks",
            examples=["----", "[source,python]"]
        )
    },
    
    PatternCategory.STRUCTURE: {
        "include": QueryPattern(
            pattern=r'^include::([^[\]]+)(?:\[(.*?)\])?$',
            extract=lambda m: {
                "type": "include",
                "path": m.group(1),
                "options": m.group(2) if m.group(2) else {},
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches AsciiDoc include directives",
            examples=["include::file.adoc[]"]
        ),
        "anchor": QueryPattern(
            pattern=r'^\[\[([^\]]+)\]\]$',
            extract=lambda m: {
                "type": "anchor",
                "id": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches AsciiDoc anchors",
            examples=["[[anchor-id]]"]
        ),
        "list": QueryPattern(
            pattern=r'^(\s*)(?:\*|\d+\.|[a-zA-Z]\.|\[.*?\])\s+(.+)$',
            extract=lambda m: {
                "type": "list",
                "indent": len(m.group(1)),
                "content": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches AsciiDoc lists",
            examples=["* Item", "1. Item", "[square] Item"]
        )
    },
    
    PatternCategory.DOCUMENTATION: {
        "admonition": QueryPattern(
            pattern=r'^(NOTE|TIP|IMPORTANT|WARNING|CAUTION):\s+(.+)$',
            extract=lambda m: {
                "type": "admonition",
                "admonition_type": m.group(1),
                "content": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches AsciiDoc admonitions",
            examples=["NOTE: Important information"]
        ),
        "comment": QueryPattern(
            pattern=r'^//\s*(.*)$',
            extract=lambda m: {
                "type": "comment",
                "content": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches AsciiDoc comments",
            examples=["// This is a comment"]
        ),
        "metadata": QueryPattern(
            pattern=r'^:([^:]+)!?:\s*(.*)$',
            extract=lambda m: {
                "type": "metadata",
                "key": m.group(1),
                "value": m.group(2),
                "is_locked": m.group(1).endswith('!'),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches AsciiDoc metadata",
            examples=[":author: John Doe", ":version!: 1.0"]
        )
    },
    
    PatternCategory.SEMANTICS: {
        "callout": QueryPattern(
            pattern=r'<(\d+)>',
            extract=lambda m: {
                "type": "callout",
                "number": int(m.group(1)),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches AsciiDoc callouts",
            examples=["<1>"]
        ),
        "macro": QueryPattern(
            pattern=r'([a-z]+)::([^[\]]+)(?:\[(.*?)\])?',
            extract=lambda m: {
                "type": "macro",
                "name": m.group(1),
                "target": m.group(2),
                "attributes": m.group(3) if m.group(3) else None,
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches AsciiDoc macros",
            examples=["image::file.png[]", "link::https://example.com[]"]
        ),
        "inline_markup": QueryPattern(
            pattern=r'(?:\*\*(.+?)\*\*|__(.+?)__|`(.+?)`|\+\+(.+?)\+\+)',
            extract=lambda m: {
                "type": "inline_markup",
                "style": "bold" if m.group(1) else "italic" if m.group(2) else "monospace" if m.group(3) else "passthrough",
                "content": m.group(1) or m.group(2) or m.group(3) or m.group(4),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches AsciiDoc inline markup",
            examples=["**bold**", "__italic__", "`monospace`", "++passthrough++"]
        )
    },
    
    PatternCategory.CODE_PATTERNS: {
        "source_block": QueryPattern(
            pattern=r'^\[source,\s*([^\]]+)\]\s*\n----\s*\n(.*?)\n----',
            extract=lambda m: {
                "type": "source_block",
                "language": m.group(1),
                "code": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches source code blocks",
            examples=["[source,python]\n----\nprint('Hello')\n----"]
        ),
        "listing_block": QueryPattern(
            pattern=r'^\[listing\]\s*\n----\s*\n(.*?)\n----',
            extract=lambda m: {
                "type": "listing_block",
                "content": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches listing blocks",
            examples=["[listing]\n----\nContent\n----"]
        )
    },
    
    PatternCategory.DEPENDENCIES: {
        "xref": QueryPattern(
            pattern=r'<<([^,>]+)(?:,\s*([^>]+))?>',
            extract=lambda m: {
                "type": "xref",
                "target": m.group(1),
                "text": m.group(2) if m.group(2) else None,
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches cross-references",
            examples=["<<section>>", "<<section,See section>>"]
        ),
        "include_dependency": QueryPattern(
            pattern=r'^include::([^[\]]+)\[(.*?)\]$',
            extract=lambda m: {
                "type": "include_dependency",
                "path": m.group(1),
                "attributes": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches include dependencies",
            examples=["include::common.adoc[tag=snippet]"]
        )
    },
    
    PatternCategory.BEST_PRACTICES: {
        "heading_hierarchy": QueryPattern(
            pattern=r'^(=+)\s+(.+)$(?:\n(?!=).*)*(?:\n(=+)\s+(.+)$)?',
            extract=lambda m: {
                "type": "heading_hierarchy",
                "parent_level": len(m.group(1)),
                "parent_title": m.group(2),
                "child_level": len(m.group(3)) if m.group(3) else None,
                "child_title": m.group(4) if m.group(4) else None,
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "follows_hierarchy": m.group(3) and len(m.group(3)) <= len(m.group(1)) + 1
            },
            description="Checks heading hierarchy",
            examples=["= Title\n== Section"]
        ),
        "attribute_naming": QueryPattern(
            pattern=r'^:([a-z][a-z0-9-]*?)!?:\s*(.*)$',
            extract=lambda m: {
                "type": "attribute_naming",
                "name": m.group(1),
                "value": m.group(2),
                "follows_convention": bool(re.match(r'^[a-z][a-z0-9-]*$', m.group(1))),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Checks attribute naming conventions",
            examples=[":good-name: value", ":BadName: value"]
        )
    },
    
    PatternCategory.COMMON_ISSUES: {
        "broken_xref": QueryPattern(
            pattern=r'<<([^,>]+)(?:,\s*([^>]+))?>',
            extract=lambda m: {
                "type": "broken_xref",
                "target": m.group(1),
                "text": m.group(2) if m.group(2) else None,
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "needs_verification": True
            },
            description="Detects potentially broken cross-references",
            examples=["<<missing-section>>"]
        ),
        "inconsistent_attributes": QueryPattern(
            pattern=r'^:([^:]+)!?:\s*(.*)$\n(?:.*\n)*?^:\1!?:\s*(.*)$',
            extract=lambda m: {
                "type": "inconsistent_attributes",
                "name": m.group(1),
                "first_value": m.group(2),
                "second_value": m.group(3),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "is_inconsistent": m.group(2) != m.group(3)
            },
            description="Detects inconsistent attribute definitions",
            examples=[":attr: value1\n:attr: value2"]
        )
    },
    
    PatternCategory.USER_PATTERNS: {
        "custom_block": QueryPattern(
            pattern=r'^\[([^\]]+)\]\s*\n====\s*\n(.*?)\n====',
            extract=lambda m: {
                "type": "custom_block",
                "role": m.group(1),
                "content": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches custom block types",
            examples=["[custom]\n====\nContent\n===="]
        ),
        "custom_macro": QueryPattern(
            pattern=r'(\w+):([^[\]]+)\[(.*?)\]',
            extract=lambda m: {
                "type": "custom_macro",
                "name": m.group(1),
                "target": m.group(2),
                "attributes": m.group(3),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches custom macro definitions",
            examples=["custom:target[attrs]"]
        )
    }
}

# Add the repository learning patterns
ASCIIDOC_PATTERNS[PatternCategory.LEARNING] = {
    "document_structure": QueryPattern(
        pattern=r'(?s)^=\s+([^\n]+)\n\n(.*?)(?=\n=\s|$)',
        extract=lambda m: {
            "type": "document_structure",
            "title": m.group(1),
            "content": m.group(2),
            "line_number": m.string.count('\n', 0, m.start()) + 1
        },
        description="Matches document structure patterns",
        examples=["= Title\n\nContent"]
    ),
    "section_patterns": QueryPattern(
        pattern=r'(?s)(=+)\s+([^\n]+)\n\n(.*?)(?=\n=|$)',
        extract=lambda m: {
            "type": "section_pattern",
            "level": len(m.group(1)),
            "title": m.group(2),
            "content": m.group(3),
            "line_number": m.string.count('\n', 0, m.start()) + 1
        },
        description="Learns section organization patterns",
        examples=["== Section\n\nContent"]
    )
}

# Function to extract patterns for repository learning
def extract_asciidoc_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """Extract patterns from AsciiDoc content for repository learning."""
    patterns = []
    
    # Process each pattern category
    for category in PatternCategory:
        if category in ASCIIDOC_PATTERNS:
            category_patterns = ASCIIDOC_PATTERNS[category]
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
        "can_contain": ["header", "section", "block", "list"],
        "can_be_contained_by": []
    },
    "section": {
        "can_contain": ["section", "block", "list", "paragraph"],
        "can_be_contained_by": ["document", "section"]
    },
    "block": {
        "can_contain": ["source", "listing", "quote", "example"],
        "can_be_contained_by": ["document", "section"]
    },
    "list": {
        "can_contain": ["list_item"],
        "can_be_contained_by": ["document", "section", "list_item"]
    },
    "custom_block": {
        "can_contain": ["block", "list", "paragraph"],
        "can_be_contained_by": ["document", "section"]
    }
}

def extract_asciidoc_features(ast: dict) -> dict:
    """Extract features that align with pattern categories."""
    features = {
        "syntax": {
            "headers": [],
            "sections": [],
            "blocks": []
        },
        "structure": {
            "includes": [],
            "anchors": [],
            "lists": []
        },
        "semantics": {
            "callouts": [],
            "macros": [],
            "inline_markup": []
        },
        "documentation": {
            "admonitions": [],
            "comments": [],
            "metadata": {}
        }
    }
    return features 