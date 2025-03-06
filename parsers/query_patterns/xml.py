"""Query patterns for XML files with enhanced pattern support."""

from typing import Dict, Any, List, Match, Optional
from dataclasses import dataclass
from parsers.types import FileType, QueryPattern, PatternCategory, PatternPurpose
import re

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
    },
    
    PatternCategory.CODE_PATTERNS: {
        "script": QueryPattern(
            pattern=r'<script([^>]*)>(.*?)</script>',
            extract=lambda m: {
                "type": "script",
                "attributes": m.group(1),
                "content": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches script elements",
            examples=["<script>console.log('Hello');</script>"]
        ),
        "embedded_code": QueryPattern(
            pattern=r'<(\w+:)?code([^>]*)>(.*?)</\1code>',
            extract=lambda m: {
                "type": "embedded_code",
                "namespace": m.group(1),
                "attributes": m.group(2),
                "content": m.group(3),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches embedded code elements",
            examples=["<code>print('hello')</code>"]
        )
    },
    
    PatternCategory.DEPENDENCIES: {
        "import": QueryPattern(
            pattern=r'<import\s+([^>]*)/?>',
            extract=lambda m: {
                "type": "import",
                "attributes": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches import declarations",
            examples=["<import namespace=\"http://example.com\"/>"]
        ),
        "include": QueryPattern(
            pattern=r'<include\s+([^>]*)/?>',
            extract=lambda m: {
                "type": "include",
                "attributes": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches include declarations",
            examples=["<include href=\"common.xml\"/>"]
        )
    },
    
    PatternCategory.BEST_PRACTICES: {
        "schema_validation": QueryPattern(
            pattern=r'<\w+[^>]*xsi:schemaLocation=["\'](.*?)["\'][^>]*>',
            extract=lambda m: {
                "type": "schema_validation",
                "location": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches schema validation attributes",
            examples=["<root xsi:schemaLocation=\"http://example.com schema.xsd\">"]
        ),
        "namespace_declaration": QueryPattern(
            pattern=r'<[^>]+xmlns:([a-zA-Z0-9]+)=["\'](.*?)["\'][^>]*>',
            extract=lambda m: {
                "type": "namespace_declaration",
                "prefix": m.group(1),
                "uri": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches namespace declarations",
            examples=["<root xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\">"]
        )
    },
    
    PatternCategory.COMMON_ISSUES: {
        "unclosed_tag": QueryPattern(
            pattern=r'<([a-zA-Z0-9:]+)[^>]*>[^<]*$',
            extract=lambda m: {
                "type": "unclosed_tag",
                "tag": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Detects potentially unclosed tags",
            examples=["<div>unclosed content"]
        ),
        "mismatched_tag": QueryPattern(
            pattern=r'<(\w+)[^>]*>.*?</(?!\1)[^>]+>',
            extract=lambda m: {
                "type": "mismatched_tag",
                "opening_tag": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Detects mismatched tags",
            examples=["<div>content</span>"]
        )
    },
    
    PatternCategory.USER_PATTERNS: {
        "custom_element": QueryPattern(
            pattern=r'<([a-z]+-[a-z-]+)([^>]*)(?:>(.*?)</\1>|/>)',
            extract=lambda m: {
                "type": "custom_element",
                "tag": m.group(1),
                "attributes": m.group(2),
                "content": m.group(3) if m.group(3) else None,
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches custom elements",
            examples=["<my-component>content</my-component>"]
        ),
        "custom_attribute": QueryPattern(
            pattern=r'\sdata-[a-z-]+=["\'](.*?)["\']',
            extract=lambda m: {
                "type": "custom_attribute",
                "value": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches custom data attributes",
            examples=["data-custom=\"value\""]
        )
    }
}

# Add repository learning patterns
XML_PATTERNS[PatternCategory.LEARNING] = {
    "document_structure": QueryPattern(
        pattern=r'<([a-zA-Z][a-zA-Z0-9:-]*)(?:\s+[^>]*)?(?:>.*?</\1>|/>)',
        extract=lambda m: {
            "type": "root_element_pattern",
            "tag": m.group(1),
            "is_root": True,
            "line_number": m.string.count('\n', 0, m.start()) + 1
        },
        description="Matches root elements in XML documents",
        examples=["<root>...</root>"]
    ),
    "nested_elements": QueryPattern(
        pattern=r'<([a-zA-Z][a-zA-Z0-9:-]*)(?:\s+[^>]*)?>(.*?)<\/\1>',
        extract=lambda m: {
            "type": "nested_elements_pattern",
            "parent_tag": m.group(1),
            "content": m.group(2),
            "has_nested_content": '<' in m.group(2) and '>' in m.group(2),
            "line_number": m.string.count('\n', 0, m.start()) + 1
        },
        description="Matches nested element structures in XML",
        examples=["<parent><child>content</child></parent>"]
    ),
    "processing_instruction_use": QueryPattern(
        pattern=r'<\?([a-zA-Z][a-zA-Z0-9:-]*)\s+([^?]*)\?>',
        extract=lambda m: {
            "type": "processing_instruction_pattern",
            "target": m.group(1),
            "content": m.group(2),
            "is_standard": m.group(1).lower() in ['xml', 'xml-stylesheet'],
            "line_number": m.string.count('\n', 0, m.start()) + 1
        },
        description="Matches processing instruction usage in XML",
        examples=["<?xml version=\"1.0\" encoding=\"UTF-8\"?>"]
    )
}

# Function to extract patterns for repository learning
def extract_xml_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """Extract patterns from XML content for repository learning."""
    patterns = []
    
    # Process each pattern category
    for category in PatternCategory:
        if category in XML_PATTERNS:
            category_patterns = XML_PATTERNS[category]
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