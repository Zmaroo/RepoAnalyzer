"""Query patterns for XML files."""

from parsers.pattern_processor import QueryPattern, PatternCategory
from typing import Dict, Any, Match

def extract_element(match: Match) -> Dict[str, Any]:
    """Extract element information."""
    return {
        "type": "element",
        "tag": match.group(1) or match.group(4),
        "attributes": match.group(2) or match.group(5),
        "content": match.group(3) if match.group(3) else None,
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

XML_PATTERNS = {
    PatternCategory.SYNTAX: {
        "element": QueryPattern(
            pattern=r'<(\w+)([^>]*)>(.*?)</\1>|<(\w+)([^>]*?)/?>',
            extract=extract_element,
            description="Matches XML elements",
            examples=["<tag>content</tag>", "<tag/>"]
        ),
        "attribute": QueryPattern(
            pattern=r'(\w+)=["\'](.*?)["\']',
            extract=extract_attribute,
            description="Matches XML attributes",
            examples=["id=\"123\"", "name='value'"]
        ),
        "namespace": QueryPattern(
            pattern=r'xmlns(?::(\w+))?=["\'](.*?)["\']',
            extract=lambda m: {
                "type": "namespace",
                "prefix": m.group(1),
                "uri": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches XML namespaces",
            examples=["xmlns=\"uri\"", "xmlns:prefix=\"uri\""]
        )
    },
    
    PatternCategory.STRUCTURE: {
        "processing_instruction": QueryPattern(
            pattern=r'<\?(.*?)\?>',
            extract=lambda m: {
                "type": "processing_instruction",
                "content": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches XML processing instructions",
            examples=["<?xml version=\"1.0\"?>"]
        ),
        "doctype": QueryPattern(
            pattern=r'<!DOCTYPE\s+([^>]+)>',
            extract=lambda m: {
                "type": "doctype",
                "content": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches DOCTYPE declarations",
            examples=["<!DOCTYPE html>"]
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
            description="Matches XML comments",
            examples=["<!-- comment -->"]
        ),
        "cdata": QueryPattern(
            pattern=r'<!\[CDATA\[(.*?)\]\]>',
            extract=lambda m: {
                "type": "cdata",
                "content": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches CDATA sections",
            examples=["<![CDATA[content]]>"]
        )
    },
    
    PatternCategory.SEMANTICS: {
        "entity": QueryPattern(
            pattern=r'<!ENTITY\s+(\w+)\s+"([^"]+)"',
            extract=lambda m: {
                "type": "entity",
                "name": m.group(1),
                "value": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches entity declarations",
            examples=["<!ENTITY name \"value\">"]
        ),
        "schema": QueryPattern(
            pattern=r'schemaLocation=["\'](.*?)["\']',
            extract=lambda m: {
                "type": "schema",
                "location": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches schema locations",
            examples=["schemaLocation=\"http://example.com/schema.xsd\""]
        )
    }
}

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "document": {
        "can_contain": ["element", "processing_instruction", "comment", "doctype"],
        "can_be_contained_by": []
    },
    "element": {
        "can_contain": ["element", "comment", "cdata"],
        "can_be_contained_by": ["document", "element"]
    },
    "attribute": {
        "can_contain": [],
        "can_be_contained_by": ["element"]
    }
} 