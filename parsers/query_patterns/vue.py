"""Query patterns for Vue files.

This module provides Vue-specific patterns with enhanced type system and relationships.
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
LANGUAGE = "vue"

@dataclass
class VuePatternContext(PatternContext):
    """Vue-specific pattern context."""
    component_names: Set[str] = field(default_factory=set)
    directive_names: Set[str] = field(default_factory=set)
    prop_names: Set[str] = field(default_factory=set)
    event_names: Set[str] = field(default_factory=set)
    has_composition_api: bool = False
    has_options_api: bool = False
    has_typescript: bool = False
    has_setup: bool = False
    has_jsx: bool = False
    
    def get_context_key(self) -> str:
        """Generate unique context key."""
        return f"{super().get_context_key()}:{len(self.component_names)}:{self.has_composition_api}"

# Initialize pattern metrics
PATTERN_METRICS = {
    "component": PatternPerformanceMetrics(),
    "template": PatternPerformanceMetrics(),
    "script": PatternPerformanceMetrics(),
    "style": PatternPerformanceMetrics(),
    "directive": PatternPerformanceMetrics()
}

VUE_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "component": ResilientPattern(
                pattern="""
                [
                    (component
                        (template_element
                            (start_tag) @syntax.template.start
                            (_)* @syntax.template.content
                            (end_tag) @syntax.template.end) @syntax.template
                        (script_element
                            (start_tag) @syntax.script.start
                            (raw_text) @syntax.script.content
                            (end_tag) @syntax.script.end) @syntax.script
                        (style_element
                            (start_tag) @syntax.style.start
                            (_)? @syntax.style.content
                            (end_tag) @syntax.style.end)? @syntax.style) @syntax.component,
                    (element
                        (start_tag
                            name: (_) @syntax.element.name
                            attributes: (attribute
                                name: (attribute_name) @syntax.element.attr.name
                                value: (attribute_value) @syntax.element.attr.value)* @syntax.element.attrs) @syntax.element.start
                        (_)* @syntax.element.children
                        (end_tag) @syntax.element.end) @syntax.element
                ]
                """,
                extract=lambda node: {
                    "type": "component",
                    "line_number": node["captures"].get("syntax.component", {}).get("start_point", [0])[0],
                    "has_template": "syntax.template" in node["captures"],
                    "has_script": "syntax.script" in node["captures"],
                    "has_style": "syntax.style" in node["captures"],
                    "element_name": node["captures"].get("syntax.element.name", {}).get("text", ""),
                    "relationships": {
                        PatternRelationType.CONTAINS: ["template", "script", "style"],
                        PatternRelationType.DEPENDS_ON: ["component"]
                    }
                },
                name="component",
                description="Matches Vue component declarations",
                examples=["<template>...</template>", "<script>...</script>"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["component"],
                    "validation": {
                        "required_fields": [],
                        "name_format": None
                    }
                }
            ),
            "directive": ResilientPattern(
                pattern="""
                [
                    (directive_attribute
                        name: (directive_name) @syntax.directive.name {
                            match: "^v-if$"
                        }
                        value: (attribute_value) @syntax.directive.if.value) @syntax.directive.if,
                    (directive_attribute
                        name: (directive_name) @syntax.directive.name {
                            match: "^v-else-if$"
                        }
                        value: (attribute_value) @syntax.directive.else_if.value) @syntax.directive.else_if,
                    (directive_attribute
                        name: (directive_name) @syntax.directive.name {
                            match: "^v-else$"
                        }) @syntax.directive.else,
                    (directive_attribute
                        name: (directive_name) @syntax.directive.name {
                            match: "^v-for$"
                        }
                        value: (attribute_value) @syntax.directive.for.value) @syntax.directive.for
                ]
                """,
                extract=lambda node: {
                    "type": "directive",
                    "line_number": (
                        node["captures"].get("syntax.directive.if", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.directive.else_if", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.directive.else", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.directive.for", {}).get("start_point", [0])[0]
                    ),
                    "name": node["captures"].get("syntax.directive.name", {}).get("text", ""),
                    "value": (
                        node["captures"].get("syntax.directive.if.value", {}).get("text", "") or
                        node["captures"].get("syntax.directive.else_if.value", {}).get("text", "") or
                        node["captures"].get("syntax.directive.for.value", {}).get("text", "")
                    ),
                    "relationships": {
                        PatternRelationType.CONTAINED_BY: ["template"],
                        PatternRelationType.DEPENDS_ON: ["script"]
                    }
                },
                name="directive",
                description="Matches Vue directive attributes",
                examples=["v-if='condition'", "v-for='item in items'"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["directive"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^v-[a-z][a-z0-9-]*$'
                    }
                }
            )
        }
    },

    PatternCategory.LEARNING: {
        PatternPurpose.COMPOSITION: {
            "script_setup": AdaptivePattern(
                pattern="""
                [
                    (script_element
                        (start_tag
                            attributes: [(attribute
                                name: (attribute_name) @script.attr.name {
                                    match: "^lang$"
                                }
                                value: (attribute_value) @script.attr.lang)
                            (attribute
                                name: (attribute_name) @script.attr.name {
                                    match: "^setup$"
                                })]) @script.start
                        (raw_text) @script.content
                        (end_tag)) @script.setup,
                    (raw_text) @script.composition.api {
                        match: "\\b(ref|reactive|computed|watch|watchEffect|onMounted|onUpdated|onUnmounted|provide|inject)\\b"
                    }
                ]
                """,
                extract=lambda node: {
                    "type": "script_setup",
                    "line_number": node["captures"].get("script.setup", {}).get("start_point", [0])[0],
                    "lang": next((lang.get("text", "").strip('"\'') for lang in node["captures"].get("script.attr.lang", [])), "js"),
                    "has_composition_api": "script.composition.api" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["import", "function", "variable"],
                        PatternRelationType.DEPENDS_ON: ["component"]
                    }
                },
                name="script_setup",
                description="Matches Vue script setup blocks",
                examples=["<script setup>", "<script setup lang='ts'>"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.COMPOSITION,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["script"],
                    "validation": {
                        "required_fields": [],
                        "name_format": None
                    }
                }
            )
        },
        PatternPurpose.REACTIVITY: {
            "template_expressions": AdaptivePattern(
                pattern="""
                [
                    (interpolation
                        (raw_text) @expr.interpolation.text) @expr.interpolation,
                    (directive_attribute
                        name: (directive_name) @expr.directive.name
                        value: (attribute_value) @expr.directive.value) @expr.directive,
                    (directive_attribute
                        name: (directive_name) @expr.binding.name {
                            match: "^v-bind$|^:"
                        }
                        argument: (directive_argument) @expr.binding.arg
                        value: (attribute_value) @expr.binding.value) @expr.binding
                ]
                """,
                extract=lambda node: {
                    "type": "template_expressions",
                    "line_number": (
                        node["captures"].get("expr.interpolation", {}).get("start_point", [0])[0] or
                        node["captures"].get("expr.directive", {}).get("start_point", [0])[0] or
                        node["captures"].get("expr.binding", {}).get("start_point", [0])[0]
                    ),
                    "expression": (
                        node["captures"].get("expr.interpolation.text", {}).get("text", "") or
                        node["captures"].get("expr.directive.value", {}).get("text", "") or
                        node["captures"].get("expr.binding.value", {}).get("text", "")
                    ),
                    "is_binding": "expr.binding" in node["captures"],
                    "relationships": {
                        PatternRelationType.REFERENCES: ["script"],
                        PatternRelationType.DEPENDS_ON: ["component"]
                    }
                },
                name="template_expressions",
                description="Matches Vue template expressions",
                examples=["{{ value }}", "v-bind:prop='expr'", ":prop='expr'"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.REACTIVITY,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["template"],
                    "validation": {
                        "required_fields": ["expression"],
                        "name_format": None
                    }
                }
            )
        }
    }
}

# Initialize pattern learner
pattern_learner = CrossProjectPatternLearner()

async def extract_vue_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """Extract patterns from Vue content for repository learning."""
    patterns = []
    context = VuePatternContext()
    
    try:
        # Process each pattern category
        for category in PatternCategory:
            if category in VUE_PATTERNS:
                category_patterns = VUE_PATTERNS[category]
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
                                    if match["type"] == "component":
                                        if match["element_name"]:
                                            context.component_names.add(match["element_name"])
                                    elif match["type"] == "directive":
                                        context.directive_names.add(match["name"])
                                    elif match["type"] == "script_setup":
                                        context.has_setup = True
                                        if match["lang"] == "ts":
                                            context.has_typescript = True
                                        if match["has_composition_api"]:
                                            context.has_composition_api = True
                                    elif match["type"] == "template_expressions":
                                        if match["is_binding"]:
                                            context.prop_names.add(match["expression"])
                                    
                            except Exception as e:
                                await log(f"Error processing pattern {pattern_name}: {e}", level="error")
                                continue
    
    except Exception as e:
        await log(f"Error extracting Vue patterns: {e}", level="error")
    
    return patterns

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "component": {
        PatternRelationType.CONTAINS: ["template", "script", "style"],
        PatternRelationType.DEPENDS_ON: ["component"]
    },
    "directive": {
        PatternRelationType.CONTAINED_BY: ["template"],
        PatternRelationType.DEPENDS_ON: ["script"]
    },
    "script_setup": {
        PatternRelationType.CONTAINS: ["import", "function", "variable"],
        PatternRelationType.DEPENDS_ON: ["component"]
    },
    "template_expressions": {
        PatternRelationType.REFERENCES: ["script"],
        PatternRelationType.DEPENDS_ON: ["component"]
    }
}

# Export public interfaces
__all__ = [
    'VUE_PATTERNS',
    'PATTERN_RELATIONSHIPS',
    'extract_vue_patterns_for_learning',
    'VuePatternContext',
    'pattern_learner'
] 