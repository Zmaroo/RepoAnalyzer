"""Query patterns for Fish shell files."""

from parsers.file_classification import FileType
from .common import COMMON_PATTERNS

FISH_PATTERNS = {
    **COMMON_PATTERNS,
    
    "syntax": {
        "function": {
            "pattern": """
            (function_definition
                name: (_) @syntax.function.name
                option: (_)* @syntax.function.options
                body: [
                    (command) @syntax.function.command
                    (begin_statement) @syntax.function.block
                    (if_statement) @syntax.function.if
                    (while_statement) @syntax.function.while
                    (for_statement) @syntax.function.for
                    (switch_statement) @syntax.function.switch
                    (return) @syntax.function.return
                ]*) @syntax.function.def
            """
        }
    },

    "semantics": {
        "variable": {
            "pattern": """
            [
                (variable_expansion
                    name: (variable_name) @semantics.variable.name
                    index: (list_element_access)? @semantics.variable.index) @semantics.variable.def,
                (variable_name) @semantics.variable.name
            ]
            """
        },
        "expression": {
            "pattern": """
            [
                (command
                    name: (_) @semantics.expression.command
                    argument: (_)* @semantics.expression.args) @semantics.expression.def,
                (conditional_execution) @semantics.expression.conditional,
                (pipe) @semantics.expression.pipe
            ]
            """
        }
    },

    "documentation": {
        "comment": {
            "pattern": "(comment) @documentation.comment"
        }
    },

    "structure": {
        "namespace": {
            "pattern": """
            [
                (begin_statement
                    body: (_)* @structure.namespace.body) @structure.namespace.def,
                (if_statement
                    condition: (_) @structure.namespace.condition
                    body: (_)* @structure.namespace.body) @structure.namespace.if
            ]
            """
        }
    }
} 