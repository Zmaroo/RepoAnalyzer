"""
Query patterns for Julia files.
"""

from parsers.types import FileType
from .common import COMMON_PATTERNS

JULIA_PATTERNS_FOR_LEARNING = {
    "multiple_dispatch": {
        "pattern": """
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
        "extract": lambda node: {
            "pattern_type": "multiple_dispatch",
            "function_name": (
                node["captures"].get("dispatch.func.name", {}).get("text", "") or
                node["captures"].get("dispatch.short.name", {}).get("text", "")
            ),
            "has_typed_parameters": (
                "dispatch.param.type" in node["captures"] or
                "dispatch.short.type" in node["captures"]
            ),
            "parameter_count": len((
                node["captures"].get("dispatch.func.params", {}).get("text", "") or
                node["captures"].get("dispatch.short.params", {}).get("text", "") or ","
            ).split(",")),
            "is_specialized_method": True
        }
    },
    
    "metaprogramming": {
        "pattern": """
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
        "extract": lambda node: {
            "pattern_type": "metaprogramming",
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
            )
        }
    },
    
    "type_parameterization": {
        "pattern": """
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
        "extract": lambda node: {
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
    },
    
    "functional_patterns": {
        "pattern": """
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
        "extract": lambda node: {
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
    }
}

JULIA_PATTERNS = {
    **COMMON_PATTERNS,
    
    "syntax": {
        "function": {
            "pattern": """
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
            """
        },
        "struct": {
            "pattern": """
            (struct_definition
                name: (identifier) @syntax.struct.name
                body: (field_list) @syntax.struct.body) @syntax.struct.def
            """
        },
        "module": {
            "pattern": """
            [
                (module_definition
                    name: (identifier) @syntax.module.name
                    body: (block) @syntax.module.body) @syntax.module.def,
                (baremodule_definition
                    name: (identifier) @syntax.module.bare.name
                    body: (block) @syntax.module.bare.body) @syntax.module.bare.def
            ]
            """
        }
    },

    "semantics": {
        "variable": {
            "pattern": """
            [
                (assignment
                    left: (identifier) @semantics.variable.name
                    right: (_) @semantics.variable.value) @semantics.variable.def,
                (const_statement
                    name: (identifier) @semantics.variable.const.name
                    value: (_) @semantics.variable.const.value) @semantics.variable.const
            ]
            """
        },
        "type": {
            "pattern": """
            [
                (type_definition
                    name: (identifier) @semantics.type.name
                    value: (_) @semantics.type.value) @semantics.type.def,
                (primitive_definition
                    type: (type_head) @semantics.type.primitive.head) @semantics.type.primitive
            ]
            """
        }
    },

    "documentation": {
        "comment": {
            "pattern": """
            [
                (line_comment) @documentation.comment.line,
                (block_comment) @documentation.comment.block
            ]
            """
        },
        "docstring": {
            "pattern": """
            (string_literal) @documentation.docstring {
                match: "^\\"\\"\\""
            }
            """
        }
    },

    "structure": {
        "import": {
            "pattern": """
            [
                (import_statement
                    path: (identifier) @structure.import.path) @structure.import.def,
                (using_statement
                    path: (identifier) @structure.import.using.path) @structure.import.using
            ]
            """
        },
        "export": {
            "pattern": """
            (export_statement
                names: (_) @structure.export.names) @structure.export.def
            """
        }
    },
    
    "REPOSITORY_LEARNING": JULIA_PATTERNS_FOR_LEARNING
} 