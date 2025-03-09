"""Query patterns for Python files.

This module provides Python-specific patterns with enhanced type system and relationships.
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
LANGUAGE = "python"

@dataclass
class PythonPatternContext(PatternContext):
    """Python-specific pattern context."""
    class_names: Set[str] = field(default_factory=set)
    function_names: Set[str] = field(default_factory=set)
    module_names: Set[str] = field(default_factory=set)
    decorator_names: Set[str] = field(default_factory=set)
    has_type_hints: bool = False
    has_async: bool = False
    has_decorators: bool = False
    has_dataclasses: bool = False
    
    def get_context_key(self) -> str:
        """Generate unique context key."""
        return f"{super().get_context_key()}:{len(self.class_names)}:{self.has_type_hints}"

# Initialize pattern metrics
PATTERN_METRICS = {
    "class": PatternPerformanceMetrics(),
    "function": PatternPerformanceMetrics(),
    "module": PatternPerformanceMetrics(),
    "decorator": PatternPerformanceMetrics(),
    "import": PatternPerformanceMetrics()
}

PYTHON_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "class": ResilientPattern(
                pattern="""
                [
                    (class_definition
                        name: (identifier) @syntax.class.name
                        superclasses: (argument_list)? @syntax.class.bases
                        body: (block) @syntax.class.body) @syntax.class.def,
                    (decorated_definition
                        decorators: (decorator)+ @syntax.class.decorator
                        definition: (class_definition
                            name: (identifier) @syntax.class.decorated.name
                            superclasses: (argument_list)? @syntax.class.decorated.bases
                            body: (block) @syntax.class.decorated.body)) @syntax.class.decorated.def
                ]
                """,
                extract=lambda node: {
                    "type": "class",
                    "name": (
                        node["captures"].get("syntax.class.name", {}).get("text", "") or
                        node["captures"].get("syntax.class.decorated.name", {}).get("text", "")
                    ),
                    "line_number": node["captures"].get("syntax.class.def", {}).get("start_point", [0])[0],
                    "is_decorated": "syntax.class.decorated.def" in node["captures"],
                    "has_bases": (
                        "syntax.class.bases" in node["captures"] or
                        "syntax.class.decorated.bases" in node["captures"]
                    ),
                    "relationships": {
                        PatternRelationType.CONTAINS: ["method", "property", "decorator"],
                        PatternRelationType.DEPENDS_ON: ["class", "module"]
                    }
                },
                name="class",
                description="Matches Python class declarations",
                examples=["class MyClass(BaseClass):", "@dataclass\nclass Config:"],
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
                        name: (identifier) @syntax.func.name
                        parameters: (parameters) @syntax.func.params
                        return_type: (type)? @syntax.func.return
                        body: (block) @syntax.func.body) @syntax.func.def,
                    (decorated_definition
                        decorators: (decorator)+ @syntax.func.decorator
                        definition: (function_definition
                            name: (identifier) @syntax.func.decorated.name
                            parameters: (parameters) @syntax.func.decorated.params
                            return_type: (type)? @syntax.func.decorated.return
                            body: (block) @syntax.func.decorated.body)) @syntax.func.decorated.def,
                    (async_function_definition
                        name: (identifier) @syntax.async.name
                        parameters: (parameters) @syntax.async.params
                        return_type: (type)? @syntax.async.return
                        body: (block) @syntax.async.body) @syntax.async.def
                ]
                """,
                extract=lambda node: {
                    "type": "function",
                    "name": (
                        node["captures"].get("syntax.func.name", {}).get("text", "") or
                        node["captures"].get("syntax.func.decorated.name", {}).get("text", "") or
                        node["captures"].get("syntax.async.name", {}).get("text", "")
                    ),
                    "line_number": node["captures"].get("syntax.func.def", {}).get("start_point", [0])[0],
                    "is_decorated": "syntax.func.decorated.def" in node["captures"],
                    "is_async": "syntax.async.def" in node["captures"],
                    "has_return_type": (
                        "syntax.func.return" in node["captures"] or
                        "syntax.func.decorated.return" in node["captures"] or
                        "syntax.async.return" in node["captures"]
                    ),
                    "relationships": {
                        PatternRelationType.CONTAINS: ["parameter", "block", "decorator"],
                        PatternRelationType.DEPENDS_ON: ["class", "module"]
                    }
                },
                name="function",
                description="Matches Python function declarations",
                examples=["def process(data: str) -> None:", "@property\ndef name(self):"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["function"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-z_][a-zA-Z0-9_]*$'
                    }
                }
            )
        }
    },

    PatternCategory.LEARNING: {
        PatternPurpose.DECORATORS: {
            "decorator": AdaptivePattern(
                pattern="""
                [
                    (decorator
                        name: (identifier) @dec.name
                        arguments: (argument_list)? @dec.args) @dec.def,
                    (decorator
                        name: (attribute) @dec.attr.name
                        arguments: (argument_list)? @dec.attr.args) @dec.attr.def
                ]
                """,
                extract=lambda node: {
                    "type": "decorator",
                    "line_number": node["captures"].get("dec.def", {}).get("start_point", [0])[0],
                    "name": (
                        node["captures"].get("dec.name", {}).get("text", "") or
                        node["captures"].get("dec.attr.name", {}).get("text", "")
                    ),
                    "has_arguments": (
                        "dec.args" in node["captures"] or
                        "dec.attr.args" in node["captures"]
                    ),
                    "is_attribute": "dec.attr.def" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINED_BY: ["class", "function", "method"],
                        PatternRelationType.DEPENDS_ON: ["module"]
                    }
                },
                name="decorator",
                description="Matches Python decorators",
                examples=["@property", "@dataclass(frozen=True)"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.DECORATORS,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["decorator"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-zA-Z_][a-zA-Z0-9_]*$'
                    }
                }
            )
        },
        PatternPurpose.IMPORTS: {
            "import": AdaptivePattern(
                pattern="""
                [
                    (import_statement
                        name: (dotted_name) @import.name) @import.def,
                    (import_from_statement
                        module_name: (dotted_name) @import.from.module
                        name: (dotted_name) @import.from.name) @import.from.def,
                    (aliased_import
                        name: (dotted_name) @import.alias.name
                        alias: (identifier) @import.alias.as) @import.alias.def
                ]
                """,
                extract=lambda node: {
                    "type": "import",
                    "line_number": node["captures"].get("import.def", {}).get("start_point", [0])[0],
                    "name": (
                        node["captures"].get("import.name", {}).get("text", "") or
                        node["captures"].get("import.from.name", {}).get("text", "")
                    ),
                    "module": node["captures"].get("import.from.module", {}).get("text", ""),
                    "alias": node["captures"].get("import.alias.as", {}).get("text", ""),
                    "is_from": "import.from.def" in node["captures"],
                    "is_aliased": "import.alias.def" in node["captures"],
                    "relationships": {
                        PatternRelationType.DEPENDS_ON: ["module"]
                    }
                },
                name="import",
                description="Matches Python import statements",
                examples=["import os", "from typing import List", "import numpy as np"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.IMPORTS,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["import"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-zA-Z_][a-zA-Z0-9_.]*$'
                    }
                }
            )
        }
    }
}

# Initialize pattern learner
pattern_learner = CrossProjectPatternLearner()

async def extract_python_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """Extract patterns from Python content for repository learning."""
    patterns = []
    context = PythonPatternContext()
    
    try:
        # Process each pattern category
        for category in PatternCategory:
            if category in PYTHON_PATTERNS:
                category_patterns = PYTHON_PATTERNS[category]
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
                                        if match["is_decorated"]:
                                            context.has_decorators = True
                                    elif match["type"] == "function":
                                        context.function_names.add(match["name"])
                                        if match["is_async"]:
                                            context.has_async = True
                                        if match["has_return_type"]:
                                            context.has_type_hints = True
                                    elif match["type"] == "decorator":
                                        context.has_decorators = True
                                        context.decorator_names.add(match["name"])
                                        if match["name"] == "dataclass":
                                            context.has_dataclasses = True
                                    
                            except Exception as e:
                                await log(f"Error processing pattern {pattern_name}: {e}", level="error")
                                continue
    
    except Exception as e:
        await log(f"Error extracting Python patterns: {e}", level="error")
    
    return patterns

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "class": {
        PatternRelationType.CONTAINS: ["method", "property", "decorator"],
        PatternRelationType.DEPENDS_ON: ["class", "module"]
    },
    "function": {
        PatternRelationType.CONTAINS: ["parameter", "block", "decorator"],
        PatternRelationType.DEPENDS_ON: ["class", "module"]
    },
    "decorator": {
        PatternRelationType.CONTAINED_BY: ["class", "function", "method"],
        PatternRelationType.DEPENDS_ON: ["module"]
    },
    "import": {
        PatternRelationType.DEPENDS_ON: ["module"]
    }
}

# Export public interfaces
__all__ = [
    'PYTHON_PATTERNS',
    'PATTERN_RELATIONSHIPS',
    'extract_python_patterns_for_learning',
    'PythonPatternContext',
    'pattern_learner'
] 