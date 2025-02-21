"""Query patterns for AsciiDoc files."""

from parsers.pattern_processor import QueryPattern, PatternCategory
from typing import Dict, Any, Match

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
            extract=lambda m: {
                "type": "attribute",
                "name": m.group(1),
                "value": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
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
        )
    }
} 