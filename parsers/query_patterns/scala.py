"""
Query patterns for Scala files.

This module provides Scala-specific patterns with enhanced type system and relationships.
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
LANGUAGE = "scala"

@dataclass
class ScalaPatternContext(PatternContext):
    """Scala-specific pattern context."""
    class_names: Set[str] = field(default_factory=set)
    trait_names: Set[str] = field(default_factory=set)
    object_names: Set[str] = field(default_factory=set)
    function_names: Set[str] = field(default_factory=set)
    package_names: Set[str] = field(default_factory=set)
    has_implicits: bool = False
    has_case_classes: bool = False
    has_type_classes: bool = False
    has_for_comprehension: bool = False
    has_pattern_matching: bool = False
    
    def get_context_key(self) -> str:
        """Generate unique context key."""
        return f"{super().get_context_key()}:{len(self.class_names)}:{self.has_implicits}"

# Initialize pattern metrics
PATTERN_METRICS = {
    "class": PatternPerformanceMetrics(),
    "trait": PatternPerformanceMetrics(),
    "object": PatternPerformanceMetrics(),
    "function": PatternPerformanceMetrics(),
    "package": PatternPerformanceMetrics()
}

SCALA_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "class": ResilientPattern(
                pattern="""
                [
                    (class_definition
                        modifiers: [(case) (abstract)]* @syntax.class.modifier
                        name: (identifier) @syntax.class.name
                        type_parameters: (type_parameters)? @syntax.class.type_params
                        parameters: (parameters)? @syntax.class.params
                        extends: (extends_clause)? @syntax.class.extends
                        body: (template_body)? @syntax.class.body) @syntax.class.def,
                    (object_definition
                        name: (identifier) @syntax.object.name
                        extends: (extends_clause)? @syntax.object.extends
                        body: (template_body)? @syntax.object.body) @syntax.object.def
                ]
                """,
                extract=lambda node: {
                    "type": "class",
                    "name": (
                        node["captures"].get("syntax.class.name", {}).get("text", "") or
                        node["captures"].get("syntax.object.name", {}).get("text", "")
                    ),
                    "line_number": (
                        node["captures"].get("syntax.class.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.object.def", {}).get("start_point", [0])[0]
                    ),
                    "is_case": "case" in (node["captures"].get("syntax.class.modifier", {}).get("text", "") or ""),
                    "is_abstract": "abstract" in (node["captures"].get("syntax.class.modifier", {}).get("text", "") or ""),
                    "is_object": "syntax.object.def" in node["captures"],
                    "has_type_params": "syntax.class.type_params" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["method", "field", "type"],
                        PatternRelationType.DEPENDS_ON: ["trait", "class"]
                    }
                },
                name="class",
                description="Matches Scala class and object declarations",
                examples=["class Point[T](x: T, y: T)", "case class Person(name: String)", "object Main"],
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
            "trait": ResilientPattern(
                pattern="""
                [
                    (trait_definition
                        name: (identifier) @syntax.trait.name
                        type_parameters: (type_parameters)? @syntax.trait.type_params
                        extends: (extends_clause)? @syntax.trait.extends
                        body: (template_body)? @syntax.trait.body) @syntax.trait.def
                ]
                """,
                extract=lambda node: {
                    "type": "trait",
                    "name": node["captures"].get("syntax.trait.name", {}).get("text", ""),
                    "line_number": node["captures"].get("syntax.trait.def", {}).get("start_point", [0])[0],
                    "has_type_params": "syntax.trait.type_params" in node["captures"],
                    "has_extends": "syntax.trait.extends" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["method", "type", "abstract"],
                        PatternRelationType.DEPENDS_ON: ["trait"]
                    }
                },
                name="trait",
                description="Matches Scala trait declarations",
                examples=["trait Printable[T]", "trait Monad[F[_]] extends Functor[F]"],
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
            ),
            "function": ResilientPattern(
                pattern="""
                [
                    (function_definition
                        modifiers: [(implicit) (override)]* @syntax.func.modifier
                        name: (identifier) @syntax.func.name
                        type_parameters: (type_parameters)? @syntax.func.type_params
                        parameters: (parameters)? @syntax.func.params
                        return_type: (type_annotation)? @syntax.func.return
                        body: (_)? @syntax.func.body) @syntax.func.def,
                    (val_definition
                        pattern: (identifier) @syntax.val.name
                        type_annotation: (type_annotation)? @syntax.val.type
                        value: (_)? @syntax.val.value) @syntax.val.def
                ]
                """,
                extract=lambda node: {
                    "type": "function",
                    "name": (
                        node["captures"].get("syntax.func.name", {}).get("text", "") or
                        node["captures"].get("syntax.val.name", {}).get("text", "")
                    ),
                    "line_number": (
                        node["captures"].get("syntax.func.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.val.def", {}).get("start_point", [0])[0]
                    ),
                    "is_implicit": "implicit" in (node["captures"].get("syntax.func.modifier", {}).get("text", "") or ""),
                    "is_override": "override" in (node["captures"].get("syntax.func.modifier", {}).get("text", "") or ""),
                    "is_val": "syntax.val.def" in node["captures"],
                    "has_type_params": "syntax.func.type_params" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["parameter", "expression"],
                        PatternRelationType.DEPENDS_ON: ["type", "class"]
                    }
                },
                name="function",
                description="Matches Scala function and value declarations",
                examples=["def process[T](data: T): Option[T]", "implicit val ordering: Ordering[Int]"],
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
        PatternPurpose.PACKAGES: {
            "package": AdaptivePattern(
                pattern="""
                [
                    (package_clause
                        name: (identifier) @pkg.name) @pkg.def,
                    (import_declaration
                        path: (identifier) @pkg.import.path
                        selectors: (import_selectors)? @pkg.import.selectors) @pkg.import.def
                ]
                """,
                extract=lambda node: {
                    "type": "package",
                    "name": (
                        node["captures"].get("pkg.name", {}).get("text", "") or
                        node["captures"].get("pkg.import.path", {}).get("text", "")
                    ),
                    "line_number": (
                        node["captures"].get("pkg.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("pkg.import.def", {}).get("start_point", [0])[0]
                    ),
                    "is_import": "pkg.import.def" in node["captures"],
                    "has_selectors": "pkg.import.selectors" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["class", "trait", "object"],
                        PatternRelationType.DEPENDS_ON: ["package"]
                    }
                },
                name="package",
                description="Matches Scala package declarations and imports",
                examples=["package com.example", "import scala.collection.mutable"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.PACKAGES,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["package"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-z][a-zA-Z0-9_.]*$'
                    }
                }
            )
        }
    }
}

# Initialize pattern learner
pattern_learner = CrossProjectPatternLearner()

async def extract_scala_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """Extract patterns from Scala content for repository learning."""
    patterns = []
    context = ScalaPatternContext()
    
    try:
        # Process each pattern category
        for category in PatternCategory:
            if category in SCALA_PATTERNS:
                category_patterns = SCALA_PATTERNS[category]
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
                                        if match["is_case"]:
                                            context.has_case_classes = True
                                        if match["is_object"]:
                                            context.object_names.add(match["name"])
                                    elif match["type"] == "trait":
                                        context.trait_names.add(match["name"])
                                        if match["has_type_params"]:
                                            context.has_type_classes = True
                                    elif match["type"] == "function":
                                        context.function_names.add(match["name"])
                                        if match["is_implicit"]:
                                            context.has_implicits = True
                                    elif match["type"] == "package":
                                        context.package_names.add(match["name"])
                                    
                            except Exception as e:
                                await log(f"Error processing pattern {pattern_name}: {e}", level="error")
                                continue
    
    except Exception as e:
        await log(f"Error extracting Scala patterns: {e}", level="error")
    
    return patterns

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "class": {
        PatternRelationType.CONTAINS: ["method", "field", "type"],
        PatternRelationType.DEPENDS_ON: ["trait", "class"]
    },
    "trait": {
        PatternRelationType.CONTAINS: ["method", "type", "abstract"],
        PatternRelationType.DEPENDS_ON: ["trait"]
    },
    "function": {
        PatternRelationType.CONTAINS: ["parameter", "expression"],
        PatternRelationType.DEPENDS_ON: ["type", "class"]
    },
    "package": {
        PatternRelationType.CONTAINS: ["class", "trait", "object"],
        PatternRelationType.DEPENDS_ON: ["package"]
    }
}

# Export public interfaces
__all__ = [
    'SCALA_PATTERNS',
    'PATTERN_RELATIONSHIPS',
    'extract_scala_patterns_for_learning',
    'ScalaPatternContext',
    'pattern_learner'
] 