"""Query patterns for Kotlin files.

This module provides Kotlin-specific patterns with enhanced type system and relationships.
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
LANGUAGE = "kotlin"

@dataclass
class KotlinPatternContext(PatternContext):
    """Kotlin-specific pattern context."""
    class_names: Set[str] = field(default_factory=set)
    function_names: Set[str] = field(default_factory=set)
    property_names: Set[str] = field(default_factory=set)
    interface_names: Set[str] = field(default_factory=set)
    has_coroutines: bool = False
    has_data_classes: bool = False
    has_sealed_classes: bool = False
    has_extension_functions: bool = False
    
    def get_context_key(self) -> str:
        """Generate unique context key."""
        return f"{super().get_context_key()}:{len(self.class_names)}:{self.has_coroutines}"

# Initialize pattern metrics
PATTERN_METRICS = {
    "class": PatternPerformanceMetrics(),
    "function": PatternPerformanceMetrics(),
    "property": PatternPerformanceMetrics(),
    "interface": PatternPerformanceMetrics(),
    "coroutine": PatternPerformanceMetrics()
}

KOTLIN_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "class": ResilientPattern(
                pattern="""
                [
                    (class_declaration
                        name: (type_identifier) @syntax.class.name
                        body: (class_body) @syntax.class.body) @syntax.class.def,
                    (data_class_declaration
                        name: (type_identifier) @syntax.data.name
                        body: (class_body) @syntax.data.body) @syntax.data.def,
                    (sealed_class_declaration
                        name: (type_identifier) @syntax.sealed.name
                        body: (class_body) @syntax.sealed.body) @syntax.sealed.def
                ]
                """,
                extract=lambda node: {
                    "type": "class",
                    "name": (
                        node["captures"].get("syntax.class.name", {}).get("text", "") or
                        node["captures"].get("syntax.data.name", {}).get("text", "") or
                        node["captures"].get("syntax.sealed.name", {}).get("text", "")
                    ),
                    "line_number": node["captures"].get("syntax.class.def", {}).get("start_point", [0])[0],
                    "is_data_class": "syntax.data.def" in node["captures"],
                    "is_sealed_class": "syntax.sealed.def" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["property", "function"],
                        PatternRelationType.DEPENDS_ON: ["interface", "class"]
                    }
                },
                name="class",
                description="Matches class declarations",
                examples=["class MyClass", "data class User(val name: String)", "sealed class Result"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["class"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[A-Z][a-zA-Z0-9_]*$'
                    }
                }
            ),
            "function": ResilientPattern(
                pattern="""
                [
                    (function_declaration
                        name: (simple_identifier) @syntax.func.name
                        parameters: (parameter_list) @syntax.func.params
                        body: (function_body) @syntax.func.body) @syntax.func.def,
                    (extension_function_declaration
                        name: (simple_identifier) @syntax.ext.name
                        parameters: (parameter_list) @syntax.ext.params
                        body: (function_body) @syntax.ext.body) @syntax.ext.def
                ]
                """,
                extract=lambda node: {
                    "type": "function",
                    "name": (
                        node["captures"].get("syntax.func.name", {}).get("text", "") or
                        node["captures"].get("syntax.ext.name", {}).get("text", "")
                    ),
                    "line_number": node["captures"].get("syntax.func.def", {}).get("start_point", [0])[0],
                    "is_extension": "syntax.ext.def" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["parameter", "block"],
                        PatternRelationType.DEPENDS_ON: ["class", "interface"]
                    }
                },
                name="function",
                description="Matches function declarations",
                examples=["fun hello()", "fun String.addPrefix()"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["function"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-z][a-zA-Z0-9_]*$'
                    }
                }
            )
        }
    },

    PatternCategory.LEARNING: {
        PatternPurpose.COROUTINES: {
            "coroutine": AdaptivePattern(
                pattern="""
                [
                    (function_declaration
                        modifiers: (modifiers
                            (suspend_modifier) @coroutine.suspend) @coroutine.mods
                        name: (simple_identifier) @coroutine.func.name
                        parameters: (parameter_list) @coroutine.func.params
                        body: (function_body) @coroutine.func.body) @coroutine.func,
                        
                    (call_expression
                        function: [
                            (simple_identifier) @coroutine.launch.name,
                            (navigation_expression
                                receiver: (simple_identifier) @coroutine.scope.name
                                name: (simple_identifier) @coroutine.launch.name)
                        ]
                        arguments: (call_suffix
                            (lambda_literal) @coroutine.launch.body)) @coroutine.launch
                ]
                """,
                extract=lambda node: {
                    "type": "coroutine",
                    "line_number": node["captures"].get("coroutine.func", {}).get("start_point", [0])[0],
                    "is_suspend_function": "coroutine.suspend" in node["captures"],
                    "is_coroutine_builder": (
                        node["captures"].get("coroutine.launch.name", {}).get("text", "") in
                        {"launch", "async", "runBlocking", "withContext"}
                    ),
                    "coroutine_scope": node["captures"].get("coroutine.scope.name", {}).get("text", ""),
                    "function_name": node["captures"].get("coroutine.func.name", {}).get("text", ""),
                    "relationships": {
                        PatternRelationType.CONTAINS: ["block"],
                        PatternRelationType.DEPENDS_ON: ["function"]
                    }
                },
                name="coroutine",
                description="Matches coroutine-related code",
                examples=["suspend fun fetch()", "launch { delay(1000) }"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.COROUTINES,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["coroutine"],
                    "validation": {
                        "required_fields": [],
                        "name_format": r'^[a-z][a-zA-Z0-9_]*$'
                    }
                }
            )
        },
        PatternPurpose.PROPERTIES: {
            "property": AdaptivePattern(
                pattern="""
                [
                    (property_declaration
                        modifiers: (modifiers)? @prop.mods
                        name: (simple_identifier) @prop.name
                        type: (type_reference)? @prop.type
                        (property_delegate)? @prop.delegate
                        (getter)? @prop.getter
                        (setter)? @prop.setter) @prop.decl,
                        
                    (class_parameter
                        modifiers: (modifiers)? @param.mods
                        name: (simple_identifier) @param.name
                        type: (type_reference) @param.type) @param.decl
                ]
                """,
                extract=lambda node: {
                    "type": "property",
                    "name": (
                        node["captures"].get("prop.name", {}).get("text", "") or
                        node["captures"].get("param.name", {}).get("text", "")
                    ),
                    "line_number": node["captures"].get("prop.decl", {}).get("start_point", [0])[0],
                    "has_custom_accessors": (
                        "prop.getter" in node["captures"] or
                        "prop.setter" in node["captures"]
                    ),
                    "is_delegated": "prop.delegate" in node["captures"],
                    "is_constructor_param": "param.decl" in node["captures"],
                    "relationships": {
                        PatternRelationType.DEPENDS_ON: ["class"],
                        PatternRelationType.REFERENCES: ["property"]
                    }
                },
                name="property",
                description="Matches property declarations",
                examples=["val name: String", "var count by Delegates.observable(0)"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.PROPERTIES,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["property"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-z][a-zA-Z0-9_]*$'
                    }
                }
            )
        }
    }
}

# Initialize pattern learner
pattern_learner = CrossProjectPatternLearner()

async def extract_kotlin_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """Extract patterns from Kotlin content for repository learning."""
    patterns = []
    context = KotlinPatternContext()
    
    try:
        # Process each pattern category
        for category in PatternCategory:
            if category in KOTLIN_PATTERNS:
                category_patterns = KOTLIN_PATTERNS[category]
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
                                    if match["type"] == "class":
                                        context.class_names.add(match["name"])
                                        if match["is_data_class"]:
                                            context.has_data_classes = True
                                        if match["is_sealed_class"]:
                                            context.has_sealed_classes = True
                                    elif match["type"] == "function":
                                        context.function_names.add(match["name"])
                                        if match["is_extension"]:
                                            context.has_extension_functions = True
                                    elif match["type"] == "coroutine":
                                        context.has_coroutines = True
                                    elif match["type"] == "property":
                                        context.property_names.add(match["name"])
                                    
                            except Exception as e:
                                await log(f"Error processing pattern {pattern_name}: {e}", level="error")
                                continue
    
    except Exception as e:
        await log(f"Error extracting Kotlin patterns: {e}", level="error")
    
    return patterns

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "class": {
        PatternRelationType.CONTAINS: ["property", "function"],
        PatternRelationType.DEPENDS_ON: ["interface", "class"]
    },
    "function": {
        PatternRelationType.CONTAINS: ["parameter", "block"],
        PatternRelationType.DEPENDS_ON: ["class", "interface"]
    },
    "property": {
        PatternRelationType.DEPENDS_ON: ["class"],
        PatternRelationType.REFERENCES: ["property"]
    },
    "interface": {
        PatternRelationType.CONTAINS: ["function"],
        PatternRelationType.REFERENCED_BY: ["class"]
    },
    "coroutine": {
        PatternRelationType.CONTAINS: ["block"],
        PatternRelationType.DEPENDS_ON: ["function"]
    }
}

# Export public interfaces
__all__ = [
    'KOTLIN_PATTERNS',
    'PATTERN_RELATIONSHIPS',
    'extract_kotlin_patterns_for_learning',
    'KotlinPatternContext',
    'pattern_learner'
] 