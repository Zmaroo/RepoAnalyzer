"""Query patterns for AsciiDoc files."""

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

# Add patterns for repository learning
ASCIIDOC_PATTERNS_FOR_LEARNING = {
    "documentation_structure": {
        "document_structure": QueryPattern(
            pattern=r'(?s)^=\s+(.+?)\n\n(.*?)(?:==|$)',
            extract=lambda m: {
                "type": "document_structure_pattern",
                "title": m.group(1),
                "intro": m.group(2),
                "is_standard_format": True
            },
            description="Matches typical AsciiDoc document structure with title and intro",
            examples=["= Title\n\nIntroduction text\n== First Section"]
        ),
        "api_documentation": QueryPattern(
            pattern=r'(?s)==+ API\s*\n(.+?)(?:==|\Z)',
            extract=lambda m: {
                "type": "api_doc_pattern",
                "content": m.group(1),
                "has_api_section": True
            },
            description="Matches API documentation sections",
            examples=["== API\nFunction details here\n== Other"]
        ),
        "code_example": QueryPattern(
            pattern=r'\[source,([^\]]+)\]\s*\n----\s*\n(.*?)----',
            extract=lambda m: {
                "type": "code_example_pattern",
                "language": m.group(1),
                "code": m.group(2),
                "has_example": True
            },
            description="Matches source code examples",
            examples=["[source,python]\n----\nprint('Hello')\n----"]
        )
    },
    "best_practices": {
        "admonition_usage": QueryPattern(
            pattern=r'(NOTE|TIP|IMPORTANT|WARNING|CAUTION):\s+(.+)',
            extract=lambda m: {
                "type": "admonition_pattern",
                "admonition_type": m.group(1),
                "content": m.group(2),
                "has_admonition": True
            },
            description="Matches admonition usage patterns",
            examples=["NOTE: Important information"]
        ),
        "includes_pattern": QueryPattern(
            pattern=r'include::([^[\]]+)(?:\[(.*?)\])?',
            extract=lambda m: {
                "type": "include_pattern",
                "path": m.group(1),
                "options": m.group(2) if m.group(2) else "",
                "has_includes": True
            },
            description="Matches include directives pattern",
            examples=["include::common.adoc[]"]
        )
    }
}

# Add the repository learning patterns to the main patterns
ASCIIDOC_PATTERNS['REPOSITORY_LEARNING'] = ASCIIDOC_PATTERNS_FOR_LEARNING

# Function to extract patterns for repository learning
def extract_asciidoc_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """Extract patterns from AsciiDoc content for repository learning."""
    patterns = []
    
    # Process documentation structure patterns
    for pattern_name, pattern in ASCIIDOC_PATTERNS_FOR_LEARNING["documentation_structure"].items():
        if hasattr(pattern.pattern, "__call__"):
            # Skip AST-based patterns
            continue
            
        for match in re.finditer(pattern.pattern, content, re.MULTILINE | re.DOTALL):
            pattern_data = pattern.extract(match)
            patterns.append({
                "name": pattern_name,
                "type": pattern_data.get("type", "documentation_structure"),
                "content": match.group(0),
                "metadata": pattern_data,
                "confidence": 0.8
            })
    
    # Process best practices patterns
    for pattern_name, pattern in ASCIIDOC_PATTERNS_FOR_LEARNING["best_practices"].items():
        if hasattr(pattern.pattern, "__call__"):
            # Skip AST-based patterns
            continue
            
        for match in re.finditer(pattern.pattern, content, re.MULTILINE | re.DOTALL):
            pattern_data = pattern.extract(match)
            patterns.append({
                "name": pattern_name,
                "type": pattern_data.get("type", "best_practice"),
                "content": match.group(0),
                "metadata": pattern_data,
                "confidence": 0.75
            })
            
    return patterns 