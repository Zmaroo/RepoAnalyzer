"""
Query patterns for R files.

This module provides R-specific patterns with enhanced type system and relationships.
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
LANGUAGE = "r"

@dataclass
class RPatternContext(PatternContext):
    """R-specific pattern context."""
    function_names: Set[str] = field(default_factory=set)
    package_names: Set[str] = field(default_factory=set)
    class_names: Set[str] = field(default_factory=set)
    has_s3_classes: bool = False
    has_s4_classes: bool = False
    has_r6_classes: bool = False
    has_tidyverse: bool = False
    has_data_table: bool = False
    
    def get_context_key(self) -> str:
        """Generate unique context key."""
        return f"{super().get_context_key()}:{len(self.function_names)}:{self.has_tidyverse}"

# Initialize pattern metrics
PATTERN_METRICS = {
    "function": PatternPerformanceMetrics(),
    "class": PatternPerformanceMetrics(),
    "package": PatternPerformanceMetrics(),
    "pipe": PatternPerformanceMetrics(),
    "data": PatternPerformanceMetrics()
}

R_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "function": ResilientPattern(
                pattern="""
                [
                    (function_definition
                        name: (identifier) @syntax.func.name
                        parameters: (formal_parameters) @syntax.func.params
                        body: (brace_list) @syntax.func.body) @syntax.func.def,
                    (left_assignment
                        name: (identifier) @syntax.func.assign.name
                        value: (function_definition
                            parameters: (formal_parameters) @syntax.func.assign.params
                            body: (brace_list) @syntax.func.assign.body)) @syntax.func.assign.def
                ]
                """,
                extract=lambda node: {
                    "type": "function",
                    "name": (
                        node["captures"].get("syntax.func.name", {}).get("text", "") or
                        node["captures"].get("syntax.func.assign.name", {}).get("text", "")
                    ),
                    "line_number": node["captures"].get("syntax.func.def", {}).get("start_point", [0])[0],
                    "is_assigned": "syntax.func.assign.def" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["parameter", "block"],
                        PatternRelationType.DEPENDS_ON: ["package", "function"]
                    }
                },
                name="function",
                description="Matches R function declarations",
                examples=["function(x) { x * 2 }", "my_func <- function(data) { }"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["function"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-zA-Z_.][a-zA-Z0-9_.]*$'
                    }
                }
            ),
            "class": ResilientPattern(
                pattern="""
                [
                    (function_call
                        function: (identifier) @syntax.class.s3.name
                        arguments: (arguments
                            (identifier) @syntax.class.s3.class) @syntax.class.s3.args) @syntax.class.s3.def
                        (#match? @syntax.class.s3.name "^class$"),
                    (function_call
                        function: (identifier) @syntax.class.s4.name
                        arguments: (arguments) @syntax.class.s4.args) @syntax.class.s4.def
                        (#match? @syntax.class.s4.name "^setClass$"),
                    (function_call
                        function: (identifier) @syntax.class.r6.name
                        arguments: (arguments) @syntax.class.r6.args) @syntax.class.r6.def
                        (#match? @syntax.class.r6.name "^R6Class$")
                ]
                """,
                extract=lambda node: {
                    "type": "class",
                    "line_number": (
                        node["captures"].get("syntax.class.s3.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.class.s4.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.class.r6.def", {}).get("start_point", [0])[0]
                    ),
                    "class_type": (
                        "s3" if "syntax.class.s3.def" in node["captures"] else
                        "s4" if "syntax.class.s4.def" in node["captures"] else
                        "r6" if "syntax.class.r6.def" in node["captures"] else
                        "unknown"
                    ),
                    "name": (
                        node["captures"].get("syntax.class.s3.class", {}).get("text", "") or
                        node["captures"].get("syntax.class.s4.args", {}).get("text", "") or
                        node["captures"].get("syntax.class.r6.args", {}).get("text", "")
                    ),
                    "relationships": {
                        PatternRelationType.CONTAINS: ["method", "field"],
                        PatternRelationType.DEPENDS_ON: ["package", "class"]
                    }
                },
                name="class",
                description="Matches R class declarations (S3, S4, R6)",
                examples=[
                    "class(obj) <- 'MyClass'",
                    "setClass('Person', slots = c(name = 'character'))",
                    "MyClass <- R6Class('MyClass')"
                ],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["class"],
                    "validation": {
                        "required_fields": ["name", "class_type"],
                        "name_format": r'^[A-Z][a-zA-Z0-9_]*$'
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
                    (function_call
                        function: (identifier) @pkg.lib.name
                        arguments: (arguments
                            (string) @pkg.lib.arg) @pkg.lib.args) @pkg.lib.def
                        (#match? @pkg.lib.name "^library|require$"),
                    (namespace_get
                        namespace: (identifier) @pkg.ns.name
                        function: (identifier) @pkg.ns.func) @pkg.ns.def
                ]
                """,
                extract=lambda node: {
                    "type": "package",
                    "line_number": (
                        node["captures"].get("pkg.lib.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("pkg.ns.def", {}).get("start_point", [0])[0]
                    ),
                    "name": (
                        node["captures"].get("pkg.lib.arg", {}).get("text", "") or
                        node["captures"].get("pkg.ns.name", {}).get("text", "")
                    ),
                    "is_namespace": "pkg.ns.def" in node["captures"],
                    "function": node["captures"].get("pkg.ns.func", {}).get("text", ""),
                    "relationships": {
                        PatternRelationType.PROVIDES: ["function", "class", "data"],
                        PatternRelationType.DEPENDS_ON: ["package"]
                    }
                },
                name="package",
                description="Matches R package imports and namespace usage",
                examples=["library(dplyr)", "require('data.table')", "dplyr::filter"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.PACKAGES,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["package"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-zA-Z][a-zA-Z0-9.]*$'
                    }
                }
            )
        },
        PatternPurpose.DATA_MANIPULATION: {
            "pipe": AdaptivePattern(
                pattern="""
                [
                    (pipe
                        left: (_) @pipe.left
                        right: (_) @pipe.right) @pipe.def,
                    (native_pipe
                        left: (_) @pipe.native.left
                        right: (_) @pipe.native.right) @pipe.native.def
                ]
                """,
                extract=lambda node: {
                    "type": "pipe",
                    "line_number": (
                        node["captures"].get("pipe.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("pipe.native.def", {}).get("start_point", [0])[0]
                    ),
                    "is_native": "pipe.native.def" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONNECTS: ["function", "data"],
                        PatternRelationType.DEPENDS_ON: ["package"]
                    }
                },
                name="pipe",
                description="Matches R pipe operators",
                examples=["data %>% filter()", "data |> select()"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.DATA_MANIPULATION,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["pipe"],
                    "validation": {
                        "required_fields": [],
                        "name_format": None
                    }
                }
            )
        }
    }
}

# Initialize pattern learner
pattern_learner = CrossProjectPatternLearner()

async def extract_r_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """Extract patterns from R content for repository learning."""
    patterns = []
    context = RPatternContext()
    
    try:
        # Process each pattern category
        for category in PatternCategory:
            if category in R_PATTERNS:
                category_patterns = R_PATTERNS[category]
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
                                    if match["type"] == "function":
                                        context.function_names.add(match["name"])
                                    elif match["type"] == "class":
                                        context.class_names.add(match["name"])
                                        if match["class_type"] == "s3":
                                            context.has_s3_classes = True
                                        elif match["class_type"] == "s4":
                                            context.has_s4_classes = True
                                        elif match["class_type"] == "r6":
                                            context.has_r6_classes = True
                                    elif match["type"] == "package":
                                        context.package_names.add(match["name"])
                                        if match["name"] in ["dplyr", "tidyr", "purrr", "ggplot2"]:
                                            context.has_tidyverse = True
                                        elif match["name"] == "data.table":
                                            context.has_data_table = True
                                    
                            except Exception as e:
                                await log(f"Error processing pattern {pattern_name}: {e}", level="error")
                                continue
    
    except Exception as e:
        await log(f"Error extracting R patterns: {e}", level="error")
    
    return patterns

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "function": {
        PatternRelationType.CONTAINS: ["parameter", "block"],
        PatternRelationType.DEPENDS_ON: ["package", "function"]
    },
    "class": {
        PatternRelationType.CONTAINS: ["method", "field"],
        PatternRelationType.DEPENDS_ON: ["package", "class"]
    },
    "package": {
        PatternRelationType.PROVIDES: ["function", "class", "data"],
        PatternRelationType.DEPENDS_ON: ["package"]
    },
    "pipe": {
        PatternRelationType.CONNECTS: ["function", "data"],
        PatternRelationType.DEPENDS_ON: ["package"]
    }
}

# Export public interfaces
__all__ = [
    'R_PATTERNS',
    'PATTERN_RELATIONSHIPS',
    'extract_r_patterns_for_learning',
    'RPatternContext',
    'pattern_learner'
] 