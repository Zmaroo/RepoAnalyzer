"""Query patterns for HTML files with enhanced pattern support.

This module provides HTML-specific patterns with enhanced type system and relationships.
Integrates with cache analytics, error handling, and logging systems.
"""

from typing import Dict, Any, List, Match, Optional, Set
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
LANGUAGE = "html"

@dataclass
class HTMLPatternContext(PatternContext):
    """HTML-specific pattern context."""
    tag_names: Set[str] = field(default_factory=set)
    attribute_names: Set[str] = field(default_factory=set)
    script_types: Set[str] = field(default_factory=set)
    style_types: Set[str] = field(default_factory=set)
    has_head: bool = False
    has_body: bool = False
    has_scripts: bool = False
    has_styles: bool = False
    
    def get_context_key(self) -> str:
        """Generate unique context key."""
        return f"{super().get_context_key()}:{len(self.tag_names)}:{len(self.script_types)}"

# Initialize pattern metrics
PATTERN_METRICS = {
    "element": PatternPerformanceMetrics(),
    "attribute": PatternPerformanceMetrics(),
    "script": PatternPerformanceMetrics(),
    "style": PatternPerformanceMetrics(),
    "comment": PatternPerformanceMetrics(),
    "doctype": PatternPerformanceMetrics()
}

def extract_element(match: Match) -> Dict[str, Any]:
    """Extract element information."""
    return {
        "type": "element",
        "tag": match.group(1),
        "attributes": match.group(2) if match.group(2) else "",
        "content": match.group(3) if match.group(3) else "",
        "line_number": match.string.count('\n', 0, match.start()) + 1,
        "relationships": {
            PatternRelationType.CONTAINS: ["element", "text", "comment"],
            PatternRelationType.DEPENDS_ON: []
        }
    }

def extract_attribute(match: Match) -> Dict[str, Any]:
    """Extract attribute information."""
    return {
        "type": "attribute",
        "name": match.group(1),
        "value": match.group(2) if match.group(2) else "",
        "line_number": match.string.count('\n', 0, match.start()) + 1,
        "relationships": {
            PatternRelationType.CONTAINED_BY: ["element"],
            PatternRelationType.REFERENCES: []
        }
    }

def extract_script(match: Match) -> Dict[str, Any]:
    """Extract script information."""
    return {
        "type": "script",
        "attributes": match.group(1) if match.group(1) else "",
        "content": match.group(2) if match.group(2) else "",
        "line_number": match.string.count('\n', 0, match.start()) + 1,
        "relationships": {
            PatternRelationType.CONTAINED_BY: ["head", "body"],
            PatternRelationType.DEPENDS_ON: ["script"]
        }
    }

HTML_PATTERNS = {
    PatternCategory.SYNTAX: {
        "element": ResilientPattern(
            pattern=r'<(\w+)([^>]*)(?:>(.*?)</\1>|/>)',
            extract=extract_element,
            description="Matches HTML elements",
            examples=["<div class=\"container\">content</div>", "<img src=\"image.jpg\" />"],
            name="element",
            category=PatternCategory.SYNTAX,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            confidence=0.95,
            metadata={
                "metrics": PATTERN_METRICS["element"],
                "validation": {
                    "required_fields": ["tag"],
                    "tag_format": r'^[a-zA-Z][a-zA-Z0-9]*$'
                }
            }
        ),
        "attribute": ResilientPattern(
            pattern=r'\s(\w+)(?:=(["\'][^"\']*["\']))?',
            extract=extract_attribute,
            description="Matches HTML attributes",
            examples=["class=\"container\"", "disabled"],
            name="attribute",
            category=PatternCategory.SYNTAX,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            confidence=0.95,
            metadata={
                "metrics": PATTERN_METRICS["attribute"],
                "validation": {
                    "required_fields": ["name"],
                    "name_format": r'^[a-zA-Z][a-zA-Z0-9-]*$'
                }
            }
        ),
        "doctype": ResilientPattern(
            pattern=r'<!DOCTYPE[^>]*>',
            extract=lambda m: {
                "type": "doctype",
                "declaration": m.group(0),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "relationships": {
                    PatternRelationType.DEPENDS_ON: [],
                    PatternRelationType.REFERENCES: []
                }
            },
            description="Matches DOCTYPE declarations",
            examples=["<!DOCTYPE html>"],
            name="doctype",
            category=PatternCategory.SYNTAX,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            confidence=0.95,
            metadata={
                "metrics": PATTERN_METRICS["doctype"],
                "validation": {
                    "required_fields": ["declaration"]
                }
            }
        ),
        "text_content": ResilientPattern(
            pattern=r'>([^<]+)<',
            extract=lambda m: {
                "type": "text",
                "content": m.group(1).strip(),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "relationships": {
                    PatternRelationType.CONTAINED_BY: ["element"],
                    PatternRelationType.REFERENCES: []
                }
            },
            description="Matches text content",
            examples=[">Some text<"],
            name="text_content",
            category=PatternCategory.SYNTAX,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            confidence=0.95,
            metadata={
                "metrics": PATTERN_METRICS["text"],
                "validation": {
                    "required_fields": ["content"]
                }
            }
        )
    },
    
    PatternCategory.STRUCTURE: {
        "head": AdaptivePattern(
            pattern=r'<head[^>]*>(.*?)</head>',
            extract=lambda m: {
                "type": "head",
                "content": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "relationships": {
                    PatternRelationType.CONTAINS: ["meta", "title", "link", "script", "style"],
                    PatternRelationType.CONTAINED_BY: ["html"]
                }
            },
            description="Matches head section",
            examples=["<head><title>Page Title</title></head>"],
            name="head",
            category=PatternCategory.STRUCTURE,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            confidence=0.9,
            metadata={
                "metrics": PATTERN_METRICS["head"],
                "validation": {
                    "required_fields": ["content"]
                }
            }
        ),
        "body": AdaptivePattern(
            pattern=r'<body[^>]*>(.*?)</body>',
            extract=lambda m: {
                "type": "body",
                "content": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "relationships": {
                    PatternRelationType.CONTAINS: ["element", "script", "style"],
                    PatternRelationType.CONTAINED_BY: ["html"]
                }
            },
            description="Matches body section",
            examples=["<body><div>content</div></body>"],
            name="body",
            category=PatternCategory.STRUCTURE,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            confidence=0.9,
            metadata={
                "metrics": PATTERN_METRICS["body"],
                "validation": {
                    "required_fields": ["content"]
                }
            }
        ),
        "container": AdaptivePattern(
            pattern=r'<(div|section|article|main|aside|nav|header|footer)[^>]*>(.*?)</\1>',
            extract=lambda m: {
                "type": "container",
                "tag": m.group(1),
                "content": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "relationships": {
                    PatternRelationType.CONTAINS: ["element", "text", "comment"],
                    PatternRelationType.CONTAINED_BY: ["body", "container"]
                }
            },
            description="Matches structural containers",
            examples=["<div class=\"container\">content</div>"],
            name="container",
            category=PatternCategory.STRUCTURE,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            confidence=0.9,
            metadata={
                "metrics": PATTERN_METRICS["container"],
                "validation": {
                    "required_fields": ["tag", "content"],
                    "tag_format": r'^[a-z]+$'
                }
            }
        )
    },
    
    PatternCategory.DOCUMENTATION: {
        "comment": ResilientPattern(
            pattern=r'<!--(.*?)-->',
            extract=lambda m: {
                "type": "comment",
                "content": m.group(1).strip(),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "relationships": {
                    PatternRelationType.CONTAINED_BY: ["element", "head", "body"],
                    PatternRelationType.REFERENCES: []
                }
            },
            description="Matches HTML comments",
            examples=["<!-- Navigation menu -->"],
            name="comment",
            category=PatternCategory.DOCUMENTATION,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            confidence=0.95,
            metadata={
                "metrics": PATTERN_METRICS["comment"],
                "validation": {
                    "required_fields": ["content"]
                }
            }
        ),
        "meta": ResilientPattern(
            pattern=r'<meta\s+([^>]*)>',
            extract=lambda m: {
                "type": "meta",
                "attributes": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "relationships": {
                    PatternRelationType.CONTAINED_BY: ["head"],
                    PatternRelationType.REFERENCES: []
                }
            },
            description="Matches meta tags",
            examples=["<meta name=\"description\" content=\"Page description\">"],
            name="meta",
            category=PatternCategory.DOCUMENTATION,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            confidence=0.95,
            metadata={
                "metrics": PATTERN_METRICS["meta"],
                "validation": {
                    "required_fields": ["attributes"]
                }
            }
        ),
        "aria_label": ResilientPattern(
            pattern=r'aria-label=(["\'][^"\']*["\'])',
            extract=lambda m: {
                "type": "aria_label",
                "label": m.group(1).strip('\'"'),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "relationships": {
                    PatternRelationType.CONTAINED_BY: ["element"],
                    PatternRelationType.REFERENCES: []
                }
            },
            description="Matches ARIA labels",
            examples=["aria-label=\"Close button\""],
            name="aria_label",
            category=PatternCategory.DOCUMENTATION,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            confidence=0.95,
            metadata={
                "metrics": PATTERN_METRICS["aria_label"],
                "validation": {
                    "required_fields": ["label"]
                }
            }
        )
    },
    
    PatternCategory.CODE_PATTERNS: {
        "script": ResilientPattern(
            pattern=r'<script([^>]*)>(.*?)</script>',
            extract=extract_script,
            description="Matches script elements",
            examples=["<script>console.log('Hello');</script>"],
            name="script",
            category=PatternCategory.CODE_PATTERNS,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            confidence=0.95,
            metadata={
                "metrics": PATTERN_METRICS["script"],
                "validation": {
                    "required_fields": ["content"]
                }
            }
        ),
        "style": ResilientPattern(
            pattern=r'<style[^>]*>(.*?)</style>',
            extract=lambda m: {
                "type": "style",
                "content": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "relationships": {
                    PatternRelationType.CONTAINED_BY: ["head"],
                    PatternRelationType.REFERENCES: []
                }
            },
            description="Matches style elements",
            examples=["<style>.class { color: red; }</style>"],
            name="style",
            category=PatternCategory.CODE_PATTERNS,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            confidence=0.95,
            metadata={
                "metrics": PATTERN_METRICS["style"],
                "validation": {
                    "required_fields": ["content"]
                }
            }
        ),
        "template": ResilientPattern(
            pattern=r'<template[^>]*>(.*?)</template>',
            extract=lambda m: {
                "type": "template",
                "content": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "relationships": {
                    PatternRelationType.CONTAINED_BY: ["body"],
                    PatternRelationType.REFERENCES: []
                }
            },
            description="Matches template elements",
            examples=["<template><div>template content</div></template>"],
            name="template",
            category=PatternCategory.CODE_PATTERNS,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            confidence=0.95,
            metadata={
                "metrics": PATTERN_METRICS["template"],
                "validation": {
                    "required_fields": ["content"]
                }
            }
        )
    }
}

# Initialize pattern learner
pattern_learner = CrossProjectPatternLearner()

async def extract_html_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """Extract patterns from HTML content for repository learning."""
    patterns = []
    context = HTMLPatternContext()
    
    try:
        # Process each pattern category
        for category in PatternCategory:
            if category in HTML_PATTERNS:
                category_patterns = HTML_PATTERNS[category]
                for pattern_name, pattern in category_patterns.items():
                    if isinstance(pattern, (ResilientPattern, AdaptivePattern)):
                        try:
                            matches = await pattern.matches(content, context)
                            for match in matches:
                                patterns.append({
                                    "name": pattern_name,
                                    "category": category.value,
                                    "content": match.get("text", ""),
                                    "metadata": match,
                                    "confidence": pattern.confidence,
                                    "relationships": match.get("relationships", {})
                                })
                                
                                # Update context
                                if match["type"] == "element":
                                    context.tag_names.add(match["tag"])
                                elif match["type"] == "script":
                                    context.has_scripts = True
                                    if "type" in match["attributes"]:
                                        context.script_types.add(match["attributes"]["type"])
                                elif match["type"] == "style":
                                    context.has_styles = True
                                    if "type" in match["attributes"]:
                                        context.style_types.add(match["attributes"]["type"])
                                elif match["type"] == "head":
                                    context.has_head = True
                                elif match["type"] == "body":
                                    context.has_body = True
                                
                        except Exception as e:
                            await log(f"Error processing pattern {pattern_name}: {e}", level="error")
                            continue
    
    except Exception as e:
        await log(f"Error extracting HTML patterns: {e}", level="error")
    
    return patterns

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "element": {
        PatternRelationType.CONTAINS: ["element", "text", "comment"],
        PatternRelationType.CONTAINED_BY: ["element", "body"]
    },
    "head": {
        PatternRelationType.CONTAINS: ["meta", "title", "link", "script", "style"],
        PatternRelationType.CONTAINED_BY: ["html"]
    },
    "body": {
        PatternRelationType.CONTAINS: ["element", "script", "style"],
        PatternRelationType.CONTAINED_BY: ["html"]
    },
    "script": {
        PatternRelationType.CONTAINED_BY: ["head", "body"],
        PatternRelationType.DEPENDS_ON: ["script"]
    },
    "style": {
        PatternRelationType.CONTAINED_BY: ["head"],
        PatternRelationType.REFERENCES: []
    }
}

# Export public interfaces
__all__ = [
    'HTML_PATTERNS',
    'PATTERN_RELATIONSHIPS',
    'extract_html_patterns_for_learning',
    'HTMLPatternContext',
    'pattern_learner'
]