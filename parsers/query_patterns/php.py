"""Query patterns for PHP files.

This module provides PHP-specific patterns with enhanced type system and relationships.
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
LANGUAGE = "php"

@dataclass
class PHPPatternContext(PatternContext):
    """PHP-specific pattern context."""
    class_names: Set[str] = field(default_factory=set)
    function_names: Set[str] = field(default_factory=set)
    namespace_names: Set[str] = field(default_factory=set)
    trait_names: Set[str] = field(default_factory=set)
    has_attributes: bool = False
    has_traits: bool = False
    has_enums: bool = False
    has_namespaces: bool = False
    
    def get_context_key(self) -> str:
        """Generate unique context key."""
        return f"{super().get_context_key()}:{len(self.class_names)}:{self.has_attributes}"

# Initialize pattern metrics
PATTERN_METRICS = {
    "class": PatternPerformanceMetrics(),
    "function": PatternPerformanceMetrics(),
    "namespace": PatternPerformanceMetrics(),
    "attribute": PatternPerformanceMetrics(),
    "trait": PatternPerformanceMetrics()
}

PHP_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "class": ResilientPattern(
                pattern="""
                [
                    (class_declaration
                        modifiers: [(abstract) (final)]* @syntax.class.modifier
                        name: (name) @syntax.class.name
                        base_clause: (base_clause)? @syntax.class.extends
                        interfaces: (class_interface_clause)? @syntax.class.implements
                        body: (declaration_list) @syntax.class.body) @syntax.class.def,
                    (interface_declaration
                        name: (name) @syntax.interface.name
                        interfaces: (interface_base_clause)? @syntax.interface.extends
                        body: (declaration_list) @syntax.interface.body) @syntax.interface.def,
                    (trait_declaration
                        name: (name) @syntax.trait.name
                        body: (declaration_list) @syntax.trait.body) @syntax.trait.def
                ]
                """,
                extract=lambda node: {
                    "type": "class",
                    "name": (
                        node["captures"].get("syntax.class.name", {}).get("text", "") or
                        node["captures"].get("syntax.interface.name", {}).get("text", "") or
                        node["captures"].get("syntax.trait.name", {}).get("text", "")
                    ),
                    "line_number": node["captures"].get("syntax.class.def", {}).get("start_point", [0])[0],
                    "is_interface": "syntax.interface.def" in node["captures"],
                    "is_trait": "syntax.trait.def" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["method", "property", "attribute"],
                        PatternRelationType.DEPENDS_ON: ["interface", "class"]
                    }
                },
                name="class",
                description="Matches PHP class declarations",
                examples=["class MyClass extends BaseClass", "interface MyInterface"],
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
                    (function_definition
                        name: (name) @syntax.func.name
                        parameters: (formal_parameters) @syntax.func.params
                        body: (compound_statement) @syntax.func.body) @syntax.func.def,
                    (method_declaration
                        modifiers: [(public) (private) (protected) (static) (final) (abstract)]* @syntax.method.modifier
                        name: (name) @syntax.method.name
                        parameters: (formal_parameters) @syntax.method.params
                        body: (compound_statement)? @syntax.method.body) @syntax.method.def,
                    (arrow_function 
                        parameters: (formal_parameters) @syntax.arrow.params
                        body: (_) @syntax.arrow.body) @syntax.arrow.def
                ]
                """,
                extract=lambda node: {
                    "type": "function",
                    "name": (
                        node["captures"].get("syntax.func.name", {}).get("text", "") or
                        node["captures"].get("syntax.method.name", {}).get("text", "")
                    ),
                    "line_number": node["captures"].get("syntax.func.def", {}).get("start_point", [0])[0],
                    "is_method": "syntax.method.def" in node["captures"],
                    "is_arrow": "syntax.arrow.def" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["parameter", "block"],
                        PatternRelationType.DEPENDS_ON: ["class"]
                    }
                },
                name="function",
                description="Matches PHP function declarations",
                examples=["function process($data)", "public function handle(): void"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["function"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-zA-Z_][a-zA-Z0-9_]*$'
                    }
                }
            )
        }
    },

    PatternCategory.LEARNING: {
        PatternPurpose.ATTRIBUTES: {
            "attribute": AdaptivePattern(
                pattern="""
                [
                    (attribute
                        name: (qualified_name) @attr.name
                        arguments: (arguments)? @attr.args) @attr.def,
                    (attribute_group
                        attributes: (attribute)* @attr.group.items) @attr.group
                ]
                """,
                extract=lambda node: {
                    "type": "attribute",
                    "line_number": node["captures"].get("attr.def", {}).get("start_point", [0])[0],
                    "name": node["captures"].get("attr.name", {}).get("text", ""),
                    "has_arguments": "attr.args" in node["captures"],
                    "is_group": "attr.group" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINED_BY: ["class", "method", "property"],
                        PatternRelationType.DEPENDS_ON: ["class"]
                    }
                },
                name="attribute",
                description="Matches PHP 8 attributes",
                examples=["#[Route('/api')]", "#[Attribute]"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.ATTRIBUTES,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["attribute"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[A-Z][a-zA-Z0-9_\\]*$'
                    }
                }
            )
        },
        PatternPurpose.NAMESPACES: {
            "namespace": AdaptivePattern(
                pattern="""
                [
                    (namespace_definition
                        name: (namespace_name)? @ns.name
                        body: (compound_statement) @ns.body) @ns.def,
                    (namespace_use_declaration
                        clauses: (namespace_use_clause
                            name: (qualified_name) @ns.use.name
                            alias: (namespace_aliasing_clause)? @ns.use.alias)*) @ns.use
                ]
                """,
                extract=lambda node: {
                    "type": "namespace",
                    "line_number": node["captures"].get("ns.def", {}).get("start_point", [0])[0],
                    "name": node["captures"].get("ns.name", {}).get("text", ""),
                    "is_use": "ns.use" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["class", "function", "trait"],
                        PatternRelationType.DEPENDS_ON: ["namespace"]
                    }
                },
                name="namespace",
                description="Matches PHP namespace declarations",
                examples=["namespace App\\Controllers;", "use App\\Models\\User;"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.NAMESPACES,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["namespace"],
                    "validation": {
                        "required_fields": [],
                        "name_format": r'^[A-Z][a-zA-Z0-9_\\]*$'
                    }
                }
            )
        }
    }
}

# Initialize pattern learner
pattern_learner = CrossProjectPatternLearner()

async def extract_php_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """Extract patterns from PHP content for repository learning."""
    patterns = []
    context = PHPPatternContext()
    
    try:
        # Process each pattern category
        for category in PatternCategory:
            if category in PHP_PATTERNS:
                category_patterns = PHP_PATTERNS[category]
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
                                        if match["is_trait"]:
                                            context.has_traits = True
                                            context.trait_names.add(match["name"])
                                    elif match["type"] == "function":
                                        context.function_names.add(match["name"])
                                    elif match["type"] == "attribute":
                                        context.has_attributes = True
                                    elif match["type"] == "namespace":
                                        context.has_namespaces = True
                                        if match["name"]:
                                            context.namespace_names.add(match["name"])
                                    
                            except Exception as e:
                                await log(f"Error processing pattern {pattern_name}: {e}", level="error")
                                continue
    
    except Exception as e:
        await log(f"Error extracting PHP patterns: {e}", level="error")
    
    return patterns

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "class": {
        PatternRelationType.CONTAINS: ["method", "property", "attribute"],
        PatternRelationType.DEPENDS_ON: ["interface", "class"]
    },
    "function": {
        PatternRelationType.CONTAINS: ["parameter", "block"],
        PatternRelationType.DEPENDS_ON: ["class"]
    },
    "attribute": {
        PatternRelationType.CONTAINED_BY: ["class", "method", "property"],
        PatternRelationType.DEPENDS_ON: ["class"]
    },
    "namespace": {
        PatternRelationType.CONTAINS: ["class", "function", "trait"],
        PatternRelationType.DEPENDS_ON: ["namespace"]
    }
}

# Export public interfaces
__all__ = [
    'PHP_PATTERNS',
    'PATTERN_RELATIONSHIPS',
    'extract_php_patterns_for_learning',
    'PHPPatternContext',
    'pattern_learner'
] 