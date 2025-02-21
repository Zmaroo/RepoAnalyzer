"""Query patterns for reStructuredText files."""

from parsers.pattern_processor import QueryPattern, PatternCategory
from typing import Dict, Any, Match

def extract_section(match: Match) -> Dict[str, Any]:
    """Extract section information."""
    return {
        "type": "section",
        "marker": match.group(1),
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
        )
    },
    
    PatternCategory.DOCUMENTATION: {
        "field": QueryPattern(
            pattern=r':([^:]+):\s+(.+)$',
            extract=lambda m: {
                "type": "field",
                "name": m.group(1),
                "content": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches field lists",
            examples=[":author: Name"]
        ),
        "admonition": QueryPattern(
            pattern=r'\.\.\s+(note|warning|important|tip|caution)::\s*(.*)$',
            extract=lambda m: {
                "type": "admonition",
                "admonition_type": m.group(1),
                "content": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches admonitions",
            examples=[".. note::", ".. warning::"]
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
        )
    }
}

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "document": {
        "can_contain": ["section", "directive", "field", "admonition"],
        "can_be_contained_by": []
    },
    "section": {
        "can_contain": ["section", "directive", "field", "reference", "link"],
        "can_be_contained_by": ["document", "section"]
    },
    "directive": {
        "can_contain": ["field"],
        "can_be_contained_by": ["document", "section"]
    }
} 