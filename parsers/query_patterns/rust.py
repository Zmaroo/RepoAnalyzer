"""Query patterns for Rust files.

This module provides Rust-specific patterns with enhanced type system and relationships.
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
LANGUAGE = "rust"

@dataclass
class RustPatternContext(PatternContext):
    """Rust-specific pattern context."""
    struct_names: Set[str] = field(default_factory=set)
    enum_names: Set[str] = field(default_factory=set)
    trait_names: Set[str] = field(default_factory=set)
    function_names: Set[str] = field(default_factory=set)
    module_names: Set[str] = field(default_factory=set)
    has_generics: bool = False
    has_lifetimes: bool = False
    has_unsafe: bool = False
    has_async: bool = False
    has_macros: bool = False
    
    def get_context_key(self) -> str:
        """Generate unique context key."""
        return f"{super().get_context_key()}:{len(self.struct_names)}:{self.has_generics}"

# Initialize pattern metrics
PATTERN_METRICS = {
    "struct": PatternPerformanceMetrics(),
    "enum": PatternPerformanceMetrics(),
    "trait": PatternPerformanceMetrics(),
    "function": PatternPerformanceMetrics(),
    "module": PatternPerformanceMetrics()
}

RUST_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "struct": ResilientPattern(
                pattern="""
                [
                    (struct_item
                        name: (type_identifier) @syntax.struct.name
                        type_parameters: (type_parameters)? @syntax.struct.generics
                        fields: (field_declaration_list)? @syntax.struct.fields) @syntax.struct.def,
                    (struct_item
                        name: (type_identifier) @syntax.tuple.struct.name
                        type_parameters: (type_parameters)? @syntax.tuple.struct.generics
                        fields: (tuple_field_declaration_list)? @syntax.tuple.struct.fields) @syntax.tuple.struct.def
                ]
                """,
                extract=lambda node: {
                    "type": "struct",
                    "name": (
                        node["captures"].get("syntax.struct.name", {}).get("text", "") or
                        node["captures"].get("syntax.tuple.struct.name", {}).get("text", "")
                    ),
                    "line_number": (
                        node["captures"].get("syntax.struct.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.tuple.struct.def", {}).get("start_point", [0])[0]
                    ),
                    "has_generics": (
                        "syntax.struct.generics" in node["captures"] or
                        "syntax.tuple.struct.generics" in node["captures"]
                    ),
                    "is_tuple": "syntax.tuple.struct.def" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["field", "impl", "trait"],
                        PatternRelationType.DEPENDS_ON: ["type", "module"]
                    }
                },
                name="struct",
                description="Matches Rust struct declarations",
                examples=["struct Point<T> { x: T, y: T }", "struct Tuple(i32, String);"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["struct"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[A-Z][a-zA-Z0-9_]*$'
                    }
                }
            ),
            "enum": ResilientPattern(
                pattern="""
                [
                    (enum_item
                        name: (type_identifier) @syntax.enum.name
                        type_parameters: (type_parameters)? @syntax.enum.generics
                        variants: (enum_variant_list)? @syntax.enum.variants) @syntax.enum.def
                ]
                """,
                extract=lambda node: {
                    "type": "enum",
                    "name": node["captures"].get("syntax.enum.name", {}).get("text", ""),
                    "line_number": node["captures"].get("syntax.enum.def", {}).get("start_point", [0])[0],
                    "has_generics": "syntax.enum.generics" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["variant", "impl", "trait"],
                        PatternRelationType.DEPENDS_ON: ["type", "module"]
                    }
                },
                name="enum",
                description="Matches Rust enum declarations",
                examples=["enum Option<T> { Some(T), None }", "enum Color { Red, Green, Blue }"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["enum"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[A-Z][a-zA-Z0-9_]*$'
                    }
                }
            ),
            "trait": ResilientPattern(
                pattern="""
                [
                    (trait_item
                        name: (type_identifier) @syntax.trait.name
                        type_parameters: (type_parameters)? @syntax.trait.generics
                        bounds: (trait_bounds)? @syntax.trait.bounds
                        body: (declaration_list)? @syntax.trait.body) @syntax.trait.def,
                    (impl_item
                        trait: (type_identifier) @syntax.impl.trait.name
                        type: (type_identifier) @syntax.impl.type
                        body: (declaration_list)? @syntax.impl.body) @syntax.impl.def
                ]
                """,
                extract=lambda node: {
                    "type": "trait",
                    "name": (
                        node["captures"].get("syntax.trait.name", {}).get("text", "") or
                        node["captures"].get("syntax.impl.trait.name", {}).get("text", "")
                    ),
                    "line_number": (
                        node["captures"].get("syntax.trait.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.impl.def", {}).get("start_point", [0])[0]
                    ),
                    "has_generics": "syntax.trait.generics" in node["captures"],
                    "has_bounds": "syntax.trait.bounds" in node["captures"],
                    "is_impl": "syntax.impl.def" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["function", "type", "const"],
                        PatternRelationType.DEPENDS_ON: ["trait", "module"]
                    }
                },
                name="trait",
                description="Matches Rust trait declarations and implementations",
                examples=["trait Display { fn fmt(&self) -> String; }", "impl Debug for Point"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["trait"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[A-Z][a-zA-Z0-9_]*$'
                    }
                }
            )
        }
    },

    PatternCategory.LEARNING: {
        PatternPurpose.FUNCTIONS: {
            "function": AdaptivePattern(
                pattern="""
                [
                    (function_item
                        name: (identifier) @syntax.func.name
                        parameters: (parameters)? @syntax.func.params
                        return_type: (type_identifier)? @syntax.func.return
                        body: (block)? @syntax.func.body) @syntax.func.def,
                    (function_item
                        attributes: (attribute_item)* @syntax.async.func.attrs
                        name: (identifier) @syntax.async.func.name
                        parameters: (parameters)? @syntax.async.func.params
                        return_type: (type_identifier)? @syntax.async.func.return
                        body: (block)? @syntax.async.func.body) @syntax.async.func.def
                        (#match? @syntax.async.func.attrs "async")
                ]
                """,
                extract=lambda node: {
                    "type": "function",
                    "name": (
                        node["captures"].get("syntax.func.name", {}).get("text", "") or
                        node["captures"].get("syntax.async.func.name", {}).get("text", "")
                    ),
                    "line_number": (
                        node["captures"].get("syntax.func.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.async.func.def", {}).get("start_point", [0])[0]
                    ),
                    "is_async": "syntax.async.func.def" in node["captures"],
                    "has_params": (
                        "syntax.func.params" in node["captures"] or
                        "syntax.async.func.params" in node["captures"]
                    ),
                    "has_return_type": (
                        "syntax.func.return" in node["captures"] or
                        "syntax.async.func.return" in node["captures"]
                    ),
                    "relationships": {
                        PatternRelationType.CONTAINS: ["block", "statement"],
                        PatternRelationType.DEPENDS_ON: ["type", "module"]
                    }
                },
                name="function",
                description="Matches Rust function declarations",
                examples=["fn process(data: &str) -> Result<(), Error>", "async fn handle() -> String"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.FUNCTIONS,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["function"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-z_][a-zA-Z0-9_]*$'
                    }
                }
            )
        },
        PatternPurpose.MODULES: {
            "module": AdaptivePattern(
                pattern="""
                [
                    (mod_item
                        name: (identifier) @syntax.mod.name
                        body: (declaration_list)? @syntax.mod.body) @syntax.mod.def,
                    (use_declaration
                        path: (scoped_identifier
                            path: (identifier) @syntax.use.path
                            name: (identifier) @syntax.use.name)) @syntax.use.def
                ]
                """,
                extract=lambda node: {
                    "type": "module",
                    "name": (
                        node["captures"].get("syntax.mod.name", {}).get("text", "") or
                        node["captures"].get("syntax.use.path", {}).get("text", "")
                    ),
                    "line_number": (
                        node["captures"].get("syntax.mod.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.use.def", {}).get("start_point", [0])[0]
                    ),
                    "is_use": "syntax.use.def" in node["captures"],
                    "imported_name": node["captures"].get("syntax.use.name", {}).get("text", ""),
                    "relationships": {
                        PatternRelationType.CONTAINS: ["struct", "enum", "trait", "function"],
                        PatternRelationType.DEPENDS_ON: ["module"]
                    }
                },
                name="module",
                description="Matches Rust module declarations and imports",
                examples=["mod config;", "use std::io::Result;"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.MODULES,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["module"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-z_][a-zA-Z0-9_]*$'
                    }
                }
            )
        }
    }
}

# Initialize pattern learner
pattern_learner = CrossProjectPatternLearner()

async def extract_rust_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """Extract patterns from Rust content for repository learning."""
    patterns = []
    context = RustPatternContext()
    
    try:
        # Process each pattern category
        for category in PatternCategory:
            if category in RUST_PATTERNS:
                category_patterns = RUST_PATTERNS[category]
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
                                    if match["type"] == "struct":
                                        context.struct_names.add(match["name"])
                                        if match["has_generics"]:
                                            context.has_generics = True
                                    elif match["type"] == "enum":
                                        context.enum_names.add(match["name"])
                                        if match["has_generics"]:
                                            context.has_generics = True
                                    elif match["type"] == "trait":
                                        context.trait_names.add(match["name"])
                                        if match["has_generics"]:
                                            context.has_generics = True
                                        if match["has_bounds"]:
                                            context.has_lifetimes = True
                                    elif match["type"] == "function":
                                        context.function_names.add(match["name"])
                                        if match["is_async"]:
                                            context.has_async = True
                                    elif match["type"] == "module":
                                        context.module_names.add(match["name"])
                                    
                            except Exception as e:
                                await log(f"Error processing pattern {pattern_name}: {e}", level="error")
                                continue
    
    except Exception as e:
        await log(f"Error extracting Rust patterns: {e}", level="error")
    
    return patterns

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "struct": {
        PatternRelationType.CONTAINS: ["field", "impl", "trait"],
        PatternRelationType.DEPENDS_ON: ["type", "module"]
    },
    "enum": {
        PatternRelationType.CONTAINS: ["variant", "impl", "trait"],
        PatternRelationType.DEPENDS_ON: ["type", "module"]
    },
    "trait": {
        PatternRelationType.CONTAINS: ["function", "type", "const"],
        PatternRelationType.DEPENDS_ON: ["trait", "module"]
    },
    "function": {
        PatternRelationType.CONTAINS: ["block", "statement"],
        PatternRelationType.DEPENDS_ON: ["type", "module"]
    },
    "module": {
        PatternRelationType.CONTAINS: ["struct", "enum", "trait", "function"],
        PatternRelationType.DEPENDS_ON: ["module"]
    }
}

# Export public interfaces
__all__ = [
    'RUST_PATTERNS',
    'PATTERN_RELATIONSHIPS',
    'extract_rust_patterns_for_learning',
    'RustPatternContext',
    'pattern_learner'
] 