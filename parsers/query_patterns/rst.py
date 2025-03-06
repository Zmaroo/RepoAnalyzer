"""Query patterns for reStructuredText files with enhanced pattern support."""

from typing import Dict, Any, List, Match
from dataclasses import dataclass
from parsers.types import FileType, QueryPattern, PatternCategory
import re

def extract_section(match: Match) -> Dict[str, Any]:
    """Extract section information."""
    return {
        "type": "section",
        "underline": match.group(1),
        "line_number": match.string.count('\n', 0, match.start()) + 1
    }

def extract_directive(match: Match) -> Dict[str, Any]:
    """Extract directive information."""
    return {
        "type": "directive",
        "name": match.group(1),
        "content": match.group(2),
        "line_number": match.string.count('\n', 0, match.start()) + 1
    }

def extract_field(match: Match) -> Dict[str, Any]:
    """Extract field information."""
    return {
        "type": "field",
        "name": match.group(1),
        "content": match.group(2),
        "line_number": match.string.count('\n', 0, match.start()) + 1
    }

RST_PATTERNS = {
    PatternCategory.SYNTAX: {
        "section": QueryPattern(
            pattern=r'^([=`~:\'"^_*+#-])\1{3,}\s*$',
            extract=extract_section,
            description="Matches section underlines",
            examples=["====", "----"]
        ),
        "directive": QueryPattern(
            pattern=r'\.\.\s+(\w+)::\s*(.*)$',
            extract=extract_directive,
            description="Matches directives",
            examples=[".. note::", ".. code-block:: python"]
        ),
        "role": QueryPattern(
            pattern=r':([^:]+):`([^`]+)`',
            extract=lambda m: {
                "type": "role",
                "role_type": m.group(1),
                "content": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches inline roles",
            examples=[":ref:`link`", ":class:`name`"]
        ),
        "literal_block": QueryPattern(
            pattern=r'::\s*\n\n((?:\s+.+\n)+)',
            extract=lambda m: {
                "type": "literal_block",
                "content": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches literal blocks",
            examples=["Text::\n\n    Literal block"]
        )
    },
    
    PatternCategory.STRUCTURE: {
        "reference": QueryPattern(
            pattern=r'`([^`]+)`_',
            extract=lambda m: {
                "type": "reference",
                "target": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches references",
            examples=["`link`_"]
        ),
        "include": QueryPattern(
            pattern=r'\.\.\s+include::\s*(.+)$',
            extract=lambda m: {
                "type": "include",
                "path": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches include directives",
            examples=[".. include:: file.rst"]
        ),
        "list": QueryPattern(
            pattern=r'^(\s*)(?:\*|\+|\-|\d+\.|\#\.|\[.*?\])\s+(.+)$',
            extract=lambda m: {
                "type": "list",
                "indent": len(m.group(1)),
                "content": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches lists",
            examples=["* Item", "1. Item", "#. Auto-numbered"]
        ),
        "definition_list": QueryPattern(
            pattern=r'^(\s*)([^\s].*)\n\1\s+(.+)$',
            extract=lambda m: {
                "type": "definition_list",
                "term": m.group(2),
                "definition": m.group(3),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches definition lists",
            examples=["term\n    Definition"]
        )
    },
    
    PatternCategory.DOCUMENTATION: {
        "field": QueryPattern(
            pattern=r':([^:]+):\s+(.+)$',
            extract=extract_field,
            description="Matches field lists",
            examples=[":author: Name"]
        ),
        "comment": QueryPattern(
            pattern=r'\.\.\s+(.*)$',
            extract=lambda m: {
                "type": "comment",
                "content": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches comments",
            examples=[".. This is a comment"]
        ),
        "doctest_block": QueryPattern(
            pattern=r'>>>.*?(?:\n\s+.*)*',
            extract=lambda m: {
                "type": "doctest_block",
                "content": m.group(0),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches doctest blocks",
            examples=[">>> print('test')\ntest"]
        )
    },
    
    PatternCategory.SEMANTICS: {
        "link": QueryPattern(
            pattern=r'`([^`]+)\s*<([^>]+)>`_',
            extract=lambda m: {
                "type": "link",
                "text": m.group(1),
                "url": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches external links",
            examples=["`Python <https://python.org>`_"]
        ),
        "substitution": QueryPattern(
            pattern=r'\|([^|]+)\|',
            extract=lambda m: {
                "type": "substitution",
                "name": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches substitutions",
            examples=["|name|"]
        ),
        "footnote": QueryPattern(
            pattern=r'\[(\d+|#|\*|\w+)\]_',
            extract=lambda m: {
                "type": "footnote",
                "label": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches footnotes",
            examples=["[1]_", "[#]_", "[*]_"]
        )
    },
    
    PatternCategory.CODE_PATTERNS: {
        "code_block": QueryPattern(
            pattern=r'\.\.\s+code-block::\s*(\w+)\s*\n\n((?:\s+.+\n)+)',
            extract=lambda m: {
                "type": "code_block",
                "language": m.group(1),
                "code": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches code blocks",
            examples=[".. code-block:: python\n\n    print('Hello')"]
        ),
        "code_role": QueryPattern(
            pattern=r':code:`([^`]+)`',
            extract=lambda m: {
                "type": "code_role",
                "code": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches inline code",
            examples=[":code:`print('Hello')`"]
        )
    },
    
    PatternCategory.DEPENDENCIES: {
        "internal_reference": QueryPattern(
            pattern=r':ref:`([^`]+)`',
            extract=lambda m: {
                "type": "internal_reference",
                "target": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches internal references",
            examples=[":ref:`section-label`"]
        ),
        "external_reference": QueryPattern(
            pattern=r'`([^`]+)`__',
            extract=lambda m: {
                "type": "external_reference",
                "target": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches anonymous external references",
            examples=["`link`__"]
        )
    },
    
    PatternCategory.BEST_PRACTICES: {
        "section_hierarchy": QueryPattern(
            pattern=r'([^\n]+)\n([=`~:\'"^_*+#-])\2{3,}\s*$(?:\n(?![=`~:\'"^_*+#-]).*)?\n([^\n]+)\n([=`~:\'"^_*+#-])\4{3,}\s*$',
            extract=lambda m: {
                "type": "section_hierarchy",
                "parent_title": m.group(1),
                "parent_char": m.group(2),
                "child_title": m.group(3),
                "child_char": m.group(4),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "follows_hierarchy": "=`~:'^_*+#-".index(m.group(2)) < "=`~:'^_*+#-".index(m.group(4))
            },
            description="Checks section hierarchy",
            examples=["Title\n=====\n\nSection\n-------"]
        ),
        "directive_style": QueryPattern(
            pattern=r'\.\.\s+(\w+)::\s*(.*)$',
            extract=lambda m: {
                "type": "directive_style",
                "name": m.group(1),
                "args": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "follows_convention": bool(re.match(r'^[a-z][a-z0-9-]*$', m.group(1)))
            },
            description="Checks directive naming conventions",
            examples=[".. good-name::", ".. BadName::"]
        )
    },
    
    PatternCategory.COMMON_ISSUES: {
        "broken_reference": QueryPattern(
            pattern=r'(?:`[^`]+`_(?!_)|:ref:`[^`]+`)(?!\s*_)',
            extract=lambda m: {
                "type": "broken_reference",
                "reference": m.group(0),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "needs_verification": True
            },
            description="Detects potentially broken references",
            examples=["`missing`_", ":ref:`nonexistent`"]
        ),
        "inconsistent_indentation": QueryPattern(
            pattern=r'^( +).*\n(?!\1|\s*$)( +)',
            extract=lambda m: {
                "type": "inconsistent_indentation",
                "first_indent": len(m.group(1)),
                "second_indent": len(m.group(2)),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "is_inconsistent": len(m.group(1)) != len(m.group(2))
            },
            description="Detects inconsistent indentation",
            examples=["    First line\n  Second line"]
        )
    },
    
    PatternCategory.USER_PATTERNS: {
        "custom_role": QueryPattern(
            pattern=r'\.\.\s+role::\s*(\w+)\n\s+:([^:]+):\s*(.+)$',
            extract=lambda m: {
                "type": "custom_role",
                "name": m.group(1),
                "property": m.group(2),
                "value": m.group(3),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches custom role definitions",
            examples=[".. role:: custom\n    :class: special"]
        ),
        "custom_directive": QueryPattern(
            pattern=r'\.\.\s+directive::\s*(\w+)\n(?:\s+:[\w-]+:\s*.+\n)*',
            extract=lambda m: {
                "type": "custom_directive",
                "name": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches custom directive definitions",
            examples=[".. directive:: custom\n    :option: value"]
        )
    }
}

# Add the repository learning patterns
RST_PATTERNS[PatternCategory.LEARNING] = {
    "document_structure": QueryPattern(
        pattern=r'(?s)([^\n]+)\n([=`~:\'"^_*+#-])\2{3,}\s*\n\n(.*?)(?=\n[^\n]+\n[=`~:\'"^_*+#-]{4,}|$)',
        extract=lambda m: {
            "type": "document_structure",
            "title": m.group(1),
            "level_char": m.group(2),
            "content": m.group(3),
            "line_number": m.string.count('\n', 0, m.start()) + 1
        },
        description="Matches document structure patterns",
        examples=["Title\n=====\n\nContent"]
    ),
    "section_patterns": QueryPattern(
        pattern=r'(?s)([^\n]+)\n([=`~:\'"^_*+#-])\2{3,}\s*\n\n(.*?)(?=\n[^\n]+\n[=`~:\'"^_*+#-]{4,}|$)',
        extract=lambda m: {
            "type": "section_pattern",
            "title": m.group(1),
            "level_char": m.group(2),
            "content": m.group(3),
            "line_number": m.string.count('\n', 0, m.start()) + 1
        },
        description="Learns section organization patterns",
        examples=["Section\n-------\n\nContent"]
    )
}

# Function to extract patterns for repository learning
def extract_rst_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """Extract patterns from RST content for repository learning."""
    patterns = []
    
    # Process each pattern category
    for category in PatternCategory:
        if category in RST_PATTERNS:
            category_patterns = RST_PATTERNS[category]
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
        "can_contain": ["section", "directive", "field_list", "comment"],
        "can_be_contained_by": []
    },
    "section": {
        "can_contain": ["section", "directive", "paragraph", "list"],
        "can_be_contained_by": ["document", "section"]
    },
    "directive": {
        "can_contain": ["directive_option", "directive_content"],
        "can_be_contained_by": ["document", "section"]
    },
    "list": {
        "can_contain": ["list_item"],
        "can_be_contained_by": ["document", "section", "list_item"]
    },
    "field_list": {
        "can_contain": ["field"],
        "can_be_contained_by": ["document", "section", "directive"]
    }
}

def extract_rst_features(ast: dict) -> dict:
    """Extract features that align with pattern categories."""
    features = {
        "syntax": {
            "sections": [],
            "directives": [],
            "roles": []
        },
        "structure": {
            "references": [],
            "includes": [],
            "lists": []
        },
        "semantics": {
            "links": [],
            "substitutions": [],
            "footnotes": []
        },
        "documentation": {
            "fields": [],
            "comments": [],
            "doctests": []
        }
    }
    return features 