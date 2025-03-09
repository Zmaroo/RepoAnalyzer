"""
Query patterns for Julia files.

This module provides Julia-specific patterns with enhanced type system and relationships.
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
LANGUAGE = "julia"

@dataclass
class JuliaPatternContext(PatternContext):
    """Julia-specific pattern context."""
    function_names: Set[str] = field(default_factory=set)
    type_names: Set[str] = field(default_factory=set)
    module_names: Set[str] = field(default_factory=set)
    macro_names: Set[str] = field(default_factory=set)
    has_multiple_dispatch: bool = False
    has_metaprogramming: bool = False
    has_type_params: bool = False
    
    def get_context_key(self) -> str:
        """Generate unique context key."""
        return f"{super().get_context_key()}:{len(self.function_names)}:{self.has_multiple_dispatch}"

# Initialize pattern metrics
PATTERN_METRICS = {
    "function": PatternPerformanceMetrics(),
    "struct": PatternPerformanceMetrics(),
    "module": PatternPerformanceMetrics(),
    "macro": PatternPerformanceMetrics(),
    "type": PatternPerformanceMetrics()
}

JULIA_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "function": ResilientPattern(
                pattern="""
                [
                    (function_definition
                        name: (identifier) @syntax.function.name
                        parameters: (parameter_list) @syntax.function.params
                        body: (block) @syntax.function.body) @syntax.function.def,
                    (short_function_definition
                        name: (identifier) @syntax.function.name
                        parameters: (parameter_list) @syntax.function.params
                        body: (_) @syntax.function.body) @syntax.function.def
                ]
                """,
                extract=lambda node: {
                    "type": "function",
                    "name": node["captures"].get("syntax.function.name", {}).get("text", ""),
                    "line_number": node["captures"].get("syntax.function.def", {}).get("start_point", [0])[0],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["parameter", "block"],
                        PatternRelationType.DEPENDS_ON: ["type"]
                    }
                },
                name="function",
                description="Matches function definitions",
                examples=["function foo(x::Int) end", "foo(x) = x + 1"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["function"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-zA-Z_][a-zA-Z0-9_!]*$'
                    }
                }
            ),
            "struct": ResilientPattern(
                pattern="""
                (struct_definition
                    name: (identifier) @syntax.struct.name
                    body: (field_list) @syntax.struct.body) @syntax.struct.def
                """,
                extract=lambda node: {
                    "type": "struct",
                    "name": node["captures"].get("syntax.struct.name", {}).get("text", ""),
                    "line_number": node["captures"].get("syntax.struct.def", {}).get("start_point", [0])[0],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["field"],
                        PatternRelationType.DEPENDS_ON: ["type"]
                    }
                },
                name="struct",
                description="Matches struct definitions",
                examples=["struct Point\n    x::Float64\n    y::Float64\nend"],
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
            "module": ResilientPattern(
                pattern="""
                [
                    (module_definition
                        name: (identifier) @syntax.module.name
                        body: (block) @syntax.module.body) @syntax.module.def,
                    (baremodule_definition
                        name: (identifier) @syntax.module.bare.name
                        body: (block) @syntax.module.bare.body) @syntax.module.bare.def
                ]
                """,
                extract=lambda node: {
                    "type": "module",
                    "name": (
                        node["captures"].get("syntax.module.name", {}).get("text", "") or
                        node["captures"].get("syntax.module.bare.name", {}).get("text", "")
                    ),
                    "line_number": node["captures"].get("syntax.module.def", {}).get("start_point", [0])[0],
                    "is_bare": "syntax.module.bare.def" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["function", "struct", "type", "macro"],
                        PatternRelationType.DEPENDS_ON: []
                    }
                },
                name="module",
                description="Matches module definitions",
                examples=["module MyModule\nend", "baremodule MyModule\nend"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["module"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[A-Z][a-zA-Z0-9_]*$'
                    }
                }
            )
        }
    },

    PatternCategory.SEMANTICS: {
        PatternPurpose.UNDERSTANDING: {
            "variable": QueryPattern(
                pattern="""
                [
                    (assignment
                        left: (identifier) @semantics.variable.name
                        right: (_) @semantics.variable.value) @semantics.variable.def,
                    (const_statement
                        name: (identifier) @semantics.variable.const.name
                        value: (_) @semantics.variable.const.value) @semantics.variable.const
                ]
                """,
                extract=lambda node: {
                    "name": (
                        node["captures"].get("semantics.variable.name", {}).get("text", "") or
                        node["captures"].get("semantics.variable.const.name", {}).get("text", "")
                    ),
                    "type": "variable",
                    "is_const": "semantics.variable.const" in node["captures"]
                }
            ),
            "type": QueryPattern(
                pattern="""
                [
                    (type_definition
                        name: (identifier) @semantics.type.name
                        value: (_) @semantics.type.value) @semantics.type.def,
                    (primitive_definition
                        type: (type_head) @semantics.type.primitive.head) @semantics.type.primitive
                ]
                """,
                extract=lambda node: {
                    "name": node["captures"].get("semantics.type.name", {}).get("text", ""),
                    "type": "type",
                    "is_primitive": "semantics.type.primitive" in node["captures"]
                }
            )
        }
    },

    PatternCategory.DOCUMENTATION: {
        PatternPurpose.UNDERSTANDING: {
            "comment": QueryPattern(
                pattern="""
                [
                    (line_comment) @documentation.comment.line,
                    (block_comment) @documentation.comment.block
                ]
                """,
                extract=lambda node: {
                    "text": (
                        node["captures"].get("documentation.comment.line", {}).get("text", "") or
                        node["captures"].get("documentation.comment.block", {}).get("text", "")
                    ),
                    "type": "comment",
                    "is_block": "documentation.comment.block" in node["captures"]
                }
            ),
            "docstring": QueryPattern(
                pattern="""
                (string_literal) @documentation.docstring {
                    match: "^\\"\\"\\""
                }
                """,
                extract=lambda node: {
                    "text": node["captures"].get("documentation.docstring", {}).get("text", ""),
                    "type": "docstring"
                }
            )
        }
    },

    PatternCategory.STRUCTURE: {
        PatternPurpose.UNDERSTANDING: {
            "import": QueryPattern(
                pattern="""
                [
                    (import_statement
                        path: (identifier) @structure.import.path) @structure.import.def,
                    (using_statement
                        path: (identifier) @structure.import.using.path) @structure.import.using
                ]
                """,
                extract=lambda node: {
                    "path": (
                        node["captures"].get("structure.import.path", {}).get("text", "") or
                        node["captures"].get("structure.import.using.path", {}).get("text", "")
                    ),
                    "type": "import",
                    "is_using": "structure.import.using" in node["captures"]
                }
            ),
            "export": QueryPattern(
                pattern="""
                (export_statement
                    names: (_) @structure.export.names) @structure.export.def
                """,
                extract=lambda node: {
                    "names": node["captures"].get("structure.export.names", {}).get("text", ""),
                    "type": "export"
                }
            )
        }
    },

    PatternCategory.LEARNING: {
        PatternPurpose.MULTIPLE_DISPATCH: {
            "multiple_dispatch": AdaptivePattern(
                pattern="""
                [
                    (function_definition
                        name: (identifier) @dispatch.func.name
                        parameters: (parameter_list
                            (parameter
                                type: (_) @dispatch.param.type)*) @dispatch.func.params) @dispatch.func,
                        
                    (short_function_definition
                        name: (identifier) @dispatch.short.name
                        parameters: (parameter_list
                            (parameter
                                type: (_) @dispatch.short.type)*) @dispatch.short.params) @dispatch.short
                ]
                """,
                extract=lambda node: {
                    "type": "multiple_dispatch",
                    "function_name": (
                        node["captures"].get("dispatch.func.name", {}).get("text", "") or
                        node["captures"].get("dispatch.short.name", {}).get("text", "")
                    ),
                    "line_number": node["captures"].get("dispatch.func", {}).get("start_point", [0])[0],
                    "has_typed_parameters": (
                        "dispatch.param.type" in node["captures"] or
                        "dispatch.short.type" in node["captures"]
                    ),
                    "parameter_count": len((
                        node["captures"].get("dispatch.func.params", {}).get("text", "") or
                        node["captures"].get("dispatch.short.params", {}).get("text", "") or ","
                    ).split(",")),
                    "is_specialized_method": True,
                    "relationships": {
                        PatternRelationType.DEPENDS_ON: ["type"],
                        PatternRelationType.REFERENCES: ["function"]
                    }
                },
                name="multiple_dispatch",
                description="Matches multiple dispatch function definitions",
                examples=["f(x::Int) = x + 1", "function f(x::Float64)\n    x * 2\nend"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.MULTIPLE_DISPATCH,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["function"],
                    "validation": {
                        "required_fields": ["function_name"],
                        "name_format": r'^[a-zA-Z_][a-zA-Z0-9_!]*$'
                    }
                }
            )
        },
        PatternPurpose.METAPROGRAMMING: {
            "metaprogramming": AdaptivePattern(
                pattern="""
                [
                    (macro_definition
                        name: (identifier) @meta.macro.name
                        parameters: (parameter_list) @meta.macro.params
                        body: (block) @meta.macro.body) @meta.macro,
                        
                    (quote_expression
                        body: (_) @meta.quote.body) @meta.quote,
                        
                    (macro_expression
                        name: (identifier) @meta.expr.name
                        arguments: (_)* @meta.expr.args) @meta.expr
                ]
                """,
                extract=lambda node: {
                    "type": "metaprogramming",
                    "line_number": node["captures"].get("meta.macro", {}).get("start_point", [0])[0],
                    "uses_macro_definition": "meta.macro" in node["captures"],
                    "uses_quote_expression": "meta.quote" in node["captures"],
                    "uses_macro_call": "meta.expr" in node["captures"],
                    "macro_name": (
                        node["captures"].get("meta.macro.name", {}).get("text", "") or
                        node["captures"].get("meta.expr.name", {}).get("text", "")
                    ),
                    "code_generation_style": (
                        "macro_definition" if "meta.macro" in node["captures"] else
                        "quoting" if "meta.quote" in node["captures"] else
                        "macro_invocation" if "meta.expr" in node["captures"] else
                        "other"
                    ),
                    "relationships": {
                        PatternRelationType.CONTAINS: ["block"],
                        PatternRelationType.REFERENCES: ["macro"]
                    }
                },
                name="metaprogramming",
                description="Matches metaprogramming constructs",
                examples=["macro m(x) end", ":(1 + 2)", "@m(x)"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.METAPROGRAMMING,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["macro"],
                    "validation": {
                        "required_fields": ["macro_name"],
                        "name_format": r'^[a-zA-Z_][a-zA-Z0-9_!]*$'
                    }
                }
            )
        },
        PatternPurpose.TYPE_SAFETY: {
            "type_parameterization": QueryPattern(
                pattern="""
                [
                    (parametric_type_expression
                        name: (_) @type.param.name
                        parameters: (type_parameter_list) @type.param.params) @type.param,
                        
                    (struct_definition
                        name: (_) @type.struct.name
                        parameters: (type_parameter_list)? @type.struct.params) @type.struct,
                        
                    (abstract_definition
                        name: (_) @type.abstract.name
                        parameters: (type_parameter_list)? @type.abstract.params) @type.abstract
                ]
                """,
                extract=lambda node: {
                    "pattern_type": "type_parameterization",
                    "uses_parametric_type": "type.param" in node["captures"],
                    "uses_parametric_struct": "type.struct" in node["captures"] and node["captures"].get("type.struct.params", {}).get("text", ""),
                    "uses_parametric_abstract": "type.abstract" in node["captures"] and node["captures"].get("type.abstract.params", {}).get("text", ""),
                    "type_name": (
                        node["captures"].get("type.param.name", {}).get("text", "") or
                        node["captures"].get("type.struct.name", {}).get("text", "") or
                        node["captures"].get("type.abstract.name", {}).get("text", "")
                    ),
                    "parameter_list": (
                        node["captures"].get("type.param.params", {}).get("text", "") or
                        node["captures"].get("type.struct.params", {}).get("text", "") or
                        node["captures"].get("type.abstract.params", {}).get("text", "")
                    ),
                    "is_generic_programming": True
                }
            )
        },
        PatternPurpose.FUNCTIONAL: {
            "functional_patterns": QueryPattern(
                pattern="""
                [
                    (call_expression
                        function: (identifier) @func.call.name
                        (#match? @func.call.name "^(map|filter|reduce|fold|broadcast|comprehension)") 
                        arguments: (_)* @func.call.args) @func.call,
                        
                    (comprehension_expression
                        generators: (_) @func.comp.gens
                        body: (_) @func.comp.body) @func.comp,
                        
                    (lambda_expression
                        parameters: (_)? @func.lambda.params
                        body: (_) @func.lambda.body) @func.lambda,
                        
                    (binary_expression
                        operator: (operator) @func.pipe.op
                        (#eq? @func.pipe.op "|>")
                        left: (_) @func.pipe.left
                        right: (_) @func.pipe.right) @func.pipe
                ]
                """,
                extract=lambda node: {
                    "pattern_type": "functional_patterns",
                    "uses_higher_order_function": "func.call" in node["captures"],
                    "uses_comprehension": "func.comp" in node["captures"],
                    "uses_lambda": "func.lambda" in node["captures"],
                    "uses_pipe_operator": "func.pipe" in node["captures"],
                    "higher_order_function": node["captures"].get("func.call.name", {}).get("text", ""),
                    "functional_pattern_type": (
                        "higher_order_function" if "func.call" in node["captures"] else
                        "comprehension" if "func.comp" in node["captures"] else
                        "lambda" if "func.lambda" in node["captures"] else
                        "pipe_operator" if "func.pipe" in node["captures"] else
                        "other"
                    )
                }
            )
        }
    }
}

# Initialize pattern learner
pattern_learner = CrossProjectPatternLearner()

async def extract_julia_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """Extract patterns from Julia content for repository learning."""
    patterns = []
    context = JuliaPatternContext()
    
    try:
        # Process each pattern category
        for category in PatternCategory:
            if category in JULIA_PATTERNS:
                category_patterns = JULIA_PATTERNS[category]
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
                                    elif match["type"] == "multiple_dispatch":
                                        context.has_multiple_dispatch = True
                                    elif match["type"] == "metaprogramming":
                                        context.has_metaprogramming = True
                                        if match["uses_macro_definition"]:
                                            context.macro_names.add(match["macro_name"])
                                    elif match["type"] == "struct":
                                        context.type_names.add(match["name"])
                                    elif match["type"] == "module":
                                        context.module_names.add(match["name"])
                                    
                            except Exception as e:
                                await log(f"Error processing pattern {pattern_name}: {e}", level="error")
                                continue
    
    except Exception as e:
        await log(f"Error extracting Julia patterns: {e}", level="error")
    
    return patterns

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "function": {
        PatternRelationType.CONTAINS: ["parameter", "block"],
        PatternRelationType.DEPENDS_ON: ["type"]
    },
    "struct": {
        PatternRelationType.CONTAINS: ["field"],
        PatternRelationType.DEPENDS_ON: ["type"]
    },
    "module": {
        PatternRelationType.CONTAINS: ["function", "struct", "type", "macro"],
        PatternRelationType.DEPENDS_ON: []
    },
    "macro": {
        PatternRelationType.CONTAINS: ["block"],
        PatternRelationType.REFERENCES: ["macro"]
    },
    "type": {
        PatternRelationType.REFERENCED_BY: ["function", "struct"],
        PatternRelationType.DEPENDS_ON: []
    }
}

# Export public interfaces
__all__ = [
    'JULIA_PATTERNS',
    'PATTERN_RELATIONSHIPS',
    'extract_julia_patterns_for_learning',
    'JuliaPatternContext',
    'pattern_learner'
] 