"""Query patterns for HCL files."""

from parsers.file_classification import FileType
from .common import COMMON_PATTERNS

HCL_PATTERNS = {
    **COMMON_PATTERNS,
    
    "syntax": {
        "function": {
            "pattern": """
            (function_call
                name: (identifier) @syntax.function.name
                arguments: (function_arguments)? @syntax.function.args) @syntax.function.def
            """
        },
        "block": {
            "pattern": """
            (block
                type: (identifier) @syntax.block.type
                labels: (string_lit)* @syntax.block.labels
                body: (body) @syntax.block.body) @syntax.block.def
            """
        }
    },

    "semantics": {
        "variable": {
            "pattern": """
            (attribute
                name: (identifier) @semantics.variable.name
                value: (expression) @semantics.variable.value) @semantics.variable.def
            """
        },
        "expression": {
            "pattern": """
            [
                (expression
                    content: (_) @semantics.expression.content) @semantics.expression.def,
                (template_expr
                    content: (_) @semantics.expression.template.content) @semantics.expression.template
            ]
            """
        },
        "type": {
            "pattern": """
            (type_expr
                name: (identifier) @semantics.type.name) @semantics.type.def
            """
        }
    },

    "documentation": {
        "comment": {
            "pattern": """
            (comment) @documentation.comment
            """
        }
    },

    "structure": {
        "block": {
            "pattern": """
            (config_file
                body: (body) @structure.block.body) @structure.block.def
            """
        }
    }
} 