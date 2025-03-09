"""Query patterns for XML files.

This module provides XML-specific patterns with enhanced type system and relationships.
Integrates with cache analytics, error handling, and logging systems.
"""

from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
from parsers.types import (
    FileType, PatternCategory, PatternPurpose, PatternType,
    PatternRelationType, PatternContext, PatternPerformanceMetrics
)
from parsers.query_patterns.enhanced_patterns import (
    ResilientPattern, AdaptivePattern, CrossProjectPatternLearner
)
from utils.error_handling import handle_async_errors, AsyncErrorBoundary
from utils.logger import log

# Language identifier
LANGUAGE = "xml"

@dataclass
class XMLPatternContext(PatternContext):
    """XML-specific pattern context."""
    tag_names: Set[str] = field(default_factory=set)
    attribute_names: Set[str] = field(default_factory=set)
    namespace_names: Set[str] = field(default_factory=set)
    script_types: Set[str] = field(default_factory=set)
    style_types: Set[str] = field(default_factory=set)
    has_namespaces: bool = False
    has_dtd: bool = False
    has_cdata: bool = False
    has_processing_instructions: bool = False
    has_comments: bool = False
    
    def get_context_key(self) -> str:
        """Generate unique context key."""
        return f"{super().get_context_key()}:{len(self.tag_names)}:{self.has_namespaces}"

# Initialize pattern metrics
PATTERN_METRICS = {
    "element": PatternPerformanceMetrics(),
    "attribute": PatternPerformanceMetrics(),
    "namespace": PatternPerformanceMetrics(),
    "script": PatternPerformanceMetrics(),
    "doctype": PatternPerformanceMetrics()
}

XML_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "element": ResilientPattern(
                pattern="""
                [
                    (element
                        start_tag: (start_tag
                            name: (_) @syntax.element.name
                            attributes: (attribute)* @syntax.element.attrs) @syntax.element.start
                        content: (_)* @syntax.element.content
                        end_tag: (end_tag) @syntax.element.end) @syntax.element.def,
                    (empty_element
                        name: (_) @syntax.empty.name
                        attributes: (attribute)* @syntax.empty.attrs) @syntax.empty.def
                ]
                """,
                extract=lambda node: {
                    "type": "element",
                    "name": (
                        node["captures"].get("syntax.element.name", {}).get("text", "") or
                        node["captures"].get("syntax.empty.name", {}).get("text", "")
                    ),
                    "line_number": (
                        node["captures"].get("syntax.element.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.empty.def", {}).get("start_point", [0])[0]
                    ),
                    "is_empty": "syntax.empty.def" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["element", "attribute", "text"],
                        PatternRelationType.DEPENDS_ON: ["namespace"]
                    }
                },
                name="element",
                description="Matches XML element declarations",
                examples=["<tag>content</tag>", "<empty-tag/>"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["element"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-zA-Z_][a-zA-Z0-9_:-]*$'
                    }
                }
            ),
            "attribute": ResilientPattern(
                pattern="""
                [
                    (attribute
                        name: (_) @syntax.attr.name
                        value: (_) @syntax.attr.value) @syntax.attr.def,
                    (namespace_attribute
                        name: (_) @syntax.ns.attr.name
                        value: (_) @syntax.ns.attr.value) @syntax.ns.attr.def
                ]
                """,
                extract=lambda node: {
                    "type": "attribute",
                    "name": (
                        node["captures"].get("syntax.attr.name", {}).get("text", "") or
                        node["captures"].get("syntax.ns.attr.name", {}).get("text", "")
                    ),
                    "line_number": (
                        node["captures"].get("syntax.attr.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.ns.attr.def", {}).get("start_point", [0])[0]
                    ),
                    "is_namespace": "syntax.ns.attr.def" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINED_BY: ["element"],
                        PatternRelationType.DEPENDS_ON: ["namespace"]
                    }
                },
                name="attribute",
                description="Matches XML attribute declarations",
                examples=['id="123"', 'xmlns:prefix="uri"'],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["attribute"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-zA-Z_][a-zA-Z0-9_:-]*$'
                    }
                }
            )
        }
    },

    PatternCategory.LEARNING: {
        PatternPurpose.STRUCTURE: {
            "doctype": AdaptivePattern(
                pattern="""
                [
                    (doctype
                        name: (_) @struct.doctype.name
                        external_id: (_)? @struct.doctype.external
                        dtd: (_)? @struct.doctype.dtd) @struct.doctype.def,
                    (processing_instruction
                        name: (_) @struct.pi.name
                        content: (_)? @struct.pi.content) @struct.pi.def
                ]
                """,
                extract=lambda node: {
                    "type": "doctype",
                    "name": (
                        node["captures"].get("struct.doctype.name", {}).get("text", "") or
                        node["captures"].get("struct.pi.name", {}).get("text", "")
                    ),
                    "line_number": (
                        node["captures"].get("struct.doctype.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("struct.pi.def", {}).get("start_point", [0])[0]
                    ),
                    "is_processing_instruction": "struct.pi.def" in node["captures"],
                    "has_dtd": "struct.doctype.dtd" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["entity", "notation"],
                        PatternRelationType.DEPENDS_ON: ["doctype"]
                    }
                },
                name="doctype",
                description="Matches XML DOCTYPE and processing instruction declarations",
                examples=["<!DOCTYPE html>", "<?xml version='1.0'?>"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.STRUCTURE,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["doctype"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-zA-Z_][a-zA-Z0-9_:-]*$'
                    }
                }
            )
        },
        PatternPurpose.NAMESPACES: {
            "namespace": AdaptivePattern(
                pattern="""
                [
                    (namespace_declaration
                        prefix: (_)? @ns.prefix
                        uri: (_) @ns.uri) @ns.def,
                    (namespace_reference
                        prefix: (_) @ns.ref.prefix
                        local: (_) @ns.ref.local) @ns.ref.def
                ]
                """,
                extract=lambda node: {
                    "type": "namespace",
                    "line_number": (
                        node["captures"].get("ns.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("ns.ref.def", {}).get("start_point", [0])[0]
                    ),
                    "prefix": (
                        node["captures"].get("ns.prefix", {}).get("text", "") or
                        node["captures"].get("ns.ref.prefix", {}).get("text", "")
                    ),
                    "is_reference": "ns.ref.def" in node["captures"],
                    "relationships": {
                        PatternRelationType.APPLIES_TO: ["element", "attribute"],
                        PatternRelationType.DEPENDS_ON: ["namespace"]
                    }
                },
                name="namespace",
                description="Matches XML namespace declarations and references",
                examples=['xmlns="uri"', 'xmlns:prefix="uri"'],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.NAMESPACES,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["namespace"],
                    "validation": {
                        "required_fields": [],
                        "name_format": r'^[a-zA-Z_][a-zA-Z0-9_:-]*$'
                    }
                }
            )
        }
    }
}

# Initialize pattern learner
pattern_learner = CrossProjectPatternLearner()

async def extract_xml_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """Extract patterns from XML content for repository learning."""
    patterns = []
    context = XMLPatternContext()
    
    try:
        # Process each pattern category
        for category in PatternCategory:
            if category in XML_PATTERNS:
                category_patterns = XML_PATTERNS[category]
                for purpose in category_patterns:
                    for pattern_name, pattern in category_patterns[purpose].items():
                        if isinstance(pattern, (ResilientPattern, AdaptivePattern)):
                            try:
                                matches = await pattern.matches(content, context)
                                for match in matches:
                                    patterns.append({
                                        "name": pattern_name,
                                        "category": category.value,
                                        "purpose": purpose.value,
                                        "content": match.get("text", ""),
                                        "metadata": match,
                                        "confidence": pattern.confidence,
                                        "relationships": match.get("relationships", {})
                                    })
                                    
                                    # Update context
                                    if match["type"] == "element":
                                        context.tag_names.add(match["name"])
                                    elif match["type"] == "attribute":
                                        context.attribute_names.add(match["name"])
                                        if match["is_namespace"]:
                                            context.has_namespaces = True
                                    elif match["type"] == "doctype":
                                        if match["has_dtd"]:
                                            context.has_dtd = True
                                        if match["is_processing_instruction"]:
                                            context.has_processing_instructions = True
                                    elif match["type"] == "namespace":
                                        context.has_namespaces = True
                                        if match["prefix"]:
                                            context.namespace_names.add(match["prefix"])
                                    
                            except Exception as e:
                                await log(f"Error processing pattern {pattern_name}: {e}", level="error")
                                continue
    
    except Exception as e:
        await log(f"Error extracting XML patterns: {e}", level="error")
    
    return patterns

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "element": {
        PatternRelationType.CONTAINS: ["element", "attribute", "text"],
        PatternRelationType.DEPENDS_ON: ["namespace"]
    },
    "attribute": {
        PatternRelationType.CONTAINED_BY: ["element"],
        PatternRelationType.DEPENDS_ON: ["namespace"]
    },
    "doctype": {
        PatternRelationType.CONTAINS: ["entity", "notation"],
        PatternRelationType.DEPENDS_ON: ["doctype"]
    },
    "namespace": {
        PatternRelationType.APPLIES_TO: ["element", "attribute"],
        PatternRelationType.DEPENDS_ON: ["namespace"]
    }
}

# Export public interfaces
__all__ = [
    'XML_PATTERNS',
    'PATTERN_RELATIONSHIPS',
    'extract_xml_patterns_for_learning',
    'XMLPatternContext',
    'pattern_learner'
] 