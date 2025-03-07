"""
Query patterns for MATLAB files.
"""

from parsers.types import (
    FileType, PatternCategory, PatternPurpose,
    QueryPattern, PatternDefinition
)
from .common import COMMON_PATTERNS

MATLAB_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "function": QueryPattern(
                pattern="""
                [
                    (function_definition
                        name: (_) @syntax.function.name
                        parameters: (parameter_list
                            (_)* @syntax.function.params)
                        returns: (return_list
                            (_)* @syntax.function.returns)
                        body: (block)? @syntax.function.body) @syntax.function.def,
                    (nested_function
                        name: (_) @syntax.function.nested.name
                        parameters: (parameter_list
                            (_)* @syntax.function.nested.params)
                        returns: (return_list
                            (_)* @syntax.function.nested.returns)
                        body: (block)? @syntax.function.nested.body) @syntax.function.nested.def
                ]
                """,
                extract=lambda node: {
                    "name": (
                        node["captures"].get("syntax.function.name", {}).get("text", "") or
                        node["captures"].get("syntax.function.nested.name", {}).get("text", "")
                    ),
                    "type": "function",
                    "is_nested": "syntax.function.nested.def" in node["captures"],
                    "has_params": any(
                        key in node["captures"] for key in 
                        ["syntax.function.params", "syntax.function.nested.params"]
                    ),
                    "has_returns": any(
                        key in node["captures"] for key in 
                        ["syntax.function.returns", "syntax.function.nested.returns"]
                    )
                }
            ),
            "class": QueryPattern(
                pattern="""
                [
                    (classdef
                        name: (_) @syntax.class.name
                        superclasses: (superclass_list
                            (_)* @syntax.class.super)
                        properties: (property_block
                            (_)* @syntax.class.props)
                        methods: (method_block
                            (_)* @syntax.class.methods)) @syntax.class.def
                ]
                """,
                extract=lambda node: {
                    "name": node["captures"].get("syntax.class.name", {}).get("text", ""),
                    "type": "class",
                    "has_superclasses": "syntax.class.super" in node["captures"],
                    "has_properties": "syntax.class.props" in node["captures"],
                    "has_methods": "syntax.class.methods" in node["captures"]
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
                        left: (_) @semantics.var.name
                        right: (_) @semantics.var.value) @semantics.var.def,
                    (global_variable
                        name: (_) @semantics.var.global.name) @semantics.var.global.def,
                    (persistent_variable
                        name: (_) @semantics.var.persistent.name) @semantics.var.persistent.def
                ]
                """,
                extract=lambda node: {
                    "name": (
                        node["captures"].get("semantics.var.name", {}).get("text", "") or
                        node["captures"].get("semantics.var.global.name", {}).get("text", "") or
                        node["captures"].get("semantics.var.persistent.name", {}).get("text", "")
                    ),
                    "type": "variable",
                    "is_global": "semantics.var.global.def" in node["captures"],
                    "is_persistent": "semantics.var.persistent.def" in node["captures"],
                    "has_value": "semantics.var.value" in node["captures"]
                }
            )
        }
    },

    PatternCategory.DOCUMENTATION: {
        PatternPurpose.UNDERSTANDING: {
            "comment": QueryPattern(
                pattern="""
                [
                    (comment) @documentation.comment.line,
                    (block_comment) @documentation.comment.block,
                    (help_comment) @documentation.comment.help
                ]
                """,
                extract=lambda node: {
                    "text": (
                        node["captures"].get("documentation.comment.line", {}).get("text", "") or
                        node["captures"].get("documentation.comment.block", {}).get("text", "") or
                        node["captures"].get("documentation.comment.help", {}).get("text", "")
                    ),
                    "type": "comment",
                    "is_block": "documentation.comment.block" in node["captures"],
                    "is_help": "documentation.comment.help" in node["captures"]
                }
            )
        }
    },

    PatternCategory.LEARNING: {
        PatternPurpose.BEST_PRACTICES: {
            "error_handling": QueryPattern(
                pattern="""
                [
                    (try_statement
                        body: (_) @learning.error.try.body
                        catch: (_) @learning.error.catch.body) @learning.error.try,
                    (function_call
                        name: (_) @learning.error.func.name
                        (#match? @learning.error.func.name "error|warning|assert")) @learning.error.func
                ]
                """,
                extract=lambda node: {
                    "pattern_type": "error_handling",
                    "uses_try_catch": "learning.error.try" in node["captures"],
                    "uses_error_function": "learning.error.func" in node["captures"],
                    "error_function": node["captures"].get("learning.error.func.name", {}).get("text", ""),
                    "has_catch_block": "learning.error.catch.body" in node["captures"]
                }
            )
        },
        PatternPurpose.PERFORMANCE: {
            "vectorization": QueryPattern(
                pattern="""
                [
                    (for_loop
                        iterator: (_) @learning.vec.loop.iter
                        body: (_) @learning.vec.loop.body) @learning.vec.loop,
                    (array_expression
                        elements: (_) @learning.vec.array.elements) @learning.vec.array,
                    (function_call
                        name: (_) @learning.vec.func.name
                        (#match? @learning.vec.func.name "arrayfun|cellfun|bsxfun")) @learning.vec.func
                ]
                """,
                extract=lambda node: {
                    "pattern_type": "vectorization",
                    "uses_loop": "learning.vec.loop" in node["captures"],
                    "uses_array_operation": "learning.vec.array" in node["captures"],
                    "uses_vectorized_function": "learning.vec.func" in node["captures"],
                    "vectorized_function": node["captures"].get("learning.vec.func.name", {}).get("text", "")
                }
            )
        },
        PatternPurpose.OOP: {
            "class_patterns": QueryPattern(
                pattern="""
                [
                    (property_block
                        attributes: (_)? @learning.oop.prop.attrs
                        properties: (_)* @learning.oop.prop.list) @learning.oop.prop,
                    (method_block
                        attributes: (_)? @learning.oop.method.attrs
                        methods: (_)* @learning.oop.method.list) @learning.oop.method,
                    (event_block
                        events: (_)* @learning.oop.event.list) @learning.oop.event
                ]
                """,
                extract=lambda node: {
                    "pattern_type": "class_organization",
                    "has_properties": "learning.oop.prop" in node["captures"],
                    "has_methods": "learning.oop.method" in node["captures"],
                    "has_events": "learning.oop.event" in node["captures"],
                    "property_attributes": node["captures"].get("learning.oop.prop.attrs", {}).get("text", ""),
                    "method_attributes": node["captures"].get("learning.oop.method.attrs", {}).get("text", "")
                }
            )
        }
    },

    "structure": {
        "module": {
            "pattern": """
            [
                (source_file) @structure.module,
                (function_file
                    function: (function_definition) @structure.module.function) @structure.module.file
            ]
            """
        },
        "import": {
            "pattern": """
            (import_statement
                path: (_) @structure.import.path) @structure.import.def
            """
        }
    }
} 