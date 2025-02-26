"""Query patterns for XML files."""

from typing import Dict, Any, List, Match, Optional
from dataclasses import dataclass
from parsers.types import FileType, QueryPattern, PatternCategory
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
    }
}

# Define language for pattern extraction
LANGUAGE = "xml"

# XML patterns for repository learning
XML_PATTERNS_FOR_LEARNING = {
    "document_structure": {
        "root_element": QueryPattern(
            pattern=r'<([a-zA-Z][a-zA-Z0-9:-]*)(?:\s+[^>]*)?(?:>.*?</\1>|/>)',
            extract=lambda m: {
                "type": "root_element_pattern",
                "tag": m.group(1),
                "is_root": True
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
                "has_nested_content": '<' in m.group(2) and '>' in m.group(2)
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
                "is_standard": m.group(1).lower() in ['xml', 'xml-stylesheet']
            },
            description="Matches processing instruction usage in XML",
            examples=["<?xml version=\"1.0\" encoding=\"UTF-8\"?>"]
        )
    },
    "naming_conventions": {
        "kebab_case_elements": QueryPattern(
            pattern=r'<([a-z][a-z0-9]*(?:-[a-z0-9]+)+)',
            extract=lambda m: {
                "type": "naming_convention_pattern",
                "tag": m.group(1),
                "convention": "kebab-case",
                "has_hyphen": True
            },
            description="Matches kebab-case element names in XML",
            examples=["<my-element>", "<data-container>"]
        ),
        "camel_case_elements": QueryPattern(
            pattern=r'<([a-z][a-zA-Z0-9]*[A-Z][a-zA-Z0-9]*)',
            extract=lambda m: {
                "type": "naming_convention_pattern",
                "tag": m.group(1),
                "convention": "camelCase",
                "starts_lowercase": True
            },
            description="Matches camelCase element names in XML",
            examples=["<myElement>", "<dataContainer>"]
        ),
        "pascal_case_elements": QueryPattern(
            pattern=r'<([A-Z][a-zA-Z0-9]*)',
            extract=lambda m: {
                "type": "naming_convention_pattern",
                "tag": m.group(1),
                "convention": "PascalCase",
                "starts_uppercase": True
            },
            description="Matches PascalCase element names in XML",
            examples=["<MyElement>", "<DataContainer>"]
        )
    },
    "attribute_patterns": {
        "boolean_attributes": QueryPattern(
            pattern=r'(\w+)=["\'](?:true|false|yes|no|1|0)["\']',
            extract=lambda m: {
                "type": "boolean_attribute_pattern",
                "name": m.group(1),
                "is_boolean": True
            },
            description="Matches boolean attributes in XML",
            examples=["enabled=\"true\"", "visible=\"false\""]
        ),
        "id_attributes": QueryPattern(
            pattern=r'(?:id|Id|ID)=["\']([^"\']+)["\']',
            extract=lambda m: {
                "type": "id_attribute_pattern",
                "value": m.group(1),
                "is_id": True
            },
            description="Matches ID attributes in XML",
            examples=["id=\"unique123\"", "ID=\"section-main\""]
        ),
        "reference_attributes": QueryPattern(
            pattern=r'(?:ref|Ref|REF|href|src)=["\']([^"\']+)["\']',
            extract=lambda m: {
                "type": "reference_attribute_pattern",
                "attribute": m.group(0).split('=')[0],
                "target": m.group(1),
                "is_reference": True
            },
            description="Matches reference attributes in XML",
            examples=["ref=\"other\"", "href=\"http://example.com\""]
        )
    }
}

# Add the repository learning patterns to the main patterns
XML_PATTERNS['REPOSITORY_LEARNING'] = XML_PATTERNS_FOR_LEARNING

# Function to extract patterns for repository learning
def extract_xml_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """Extract patterns from XML content for repository learning."""
    patterns = []
    
    # Process document structure patterns
    for pattern_name, pattern in XML_PATTERNS_FOR_LEARNING["document_structure"].items():
        if hasattr(pattern.pattern, "__call__"):
            # Skip AST-based patterns
            continue
            
        for match in re.finditer(pattern.pattern, content, re.MULTILINE | re.DOTALL):
            pattern_data = pattern.extract(match)
            patterns.append({
                "name": pattern_name,
                "type": pattern_data.get("type", "document_structure"),
                "content": match.group(0),
                "metadata": pattern_data,
                "confidence": 0.85
            })
    
    # Process naming convention patterns
    camel_case_count = 0
    pascal_case_count = 0
    kebab_case_count = 0
    
    for pattern_name, pattern in XML_PATTERNS_FOR_LEARNING["naming_conventions"].items():
        if hasattr(pattern.pattern, "__call__"):
            # Skip AST-based patterns
            continue
            
        for match in re.finditer(pattern.pattern, content, re.MULTILINE):
            pattern_data = pattern.extract(match)
            convention = pattern_data.get("convention")
            if convention == "camelCase":
                camel_case_count += 1
            elif convention == "PascalCase":
                pascal_case_count += 1
            elif convention == "kebab-case":
                kebab_case_count += 1
    
    # Only add a naming convention pattern if we have enough data
    if camel_case_count + pascal_case_count + kebab_case_count > 3:
        if camel_case_count > pascal_case_count and camel_case_count > kebab_case_count:
            dominant_convention = "camelCase"
            dom_count = camel_case_count
        elif pascal_case_count > camel_case_count and pascal_case_count > kebab_case_count:
            dominant_convention = "PascalCase"
            dom_count = pascal_case_count
        else:
            dominant_convention = "kebab-case"
            dom_count = kebab_case_count
            
        total = camel_case_count + pascal_case_count + kebab_case_count
        confidence = 0.5 + 0.3 * (dom_count / total)
            
        patterns.append({
            "name": "element_naming_convention",
            "type": "naming_convention_pattern",
            "content": f"Element naming convention: {dominant_convention}",
            "metadata": {
                "convention": dominant_convention,
                "camel_case_count": camel_case_count,
                "pascal_case_count": pascal_case_count,
                "kebab_case_count": kebab_case_count
            },
            "confidence": confidence
        })
    
    # Process attribute patterns
    for pattern_name, pattern in XML_PATTERNS_FOR_LEARNING["attribute_patterns"].items():
        if hasattr(pattern.pattern, "__call__"):
            # Skip AST-based patterns
            continue
            
        for match in re.finditer(pattern.pattern, content, re.MULTILINE):
            pattern_data = pattern.extract(match)
            patterns.append({
                "name": pattern_name,
                "type": pattern_data.get("type", "attribute_pattern"),
                "content": match.group(0),
                "metadata": pattern_data,
                "confidence": 0.75
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