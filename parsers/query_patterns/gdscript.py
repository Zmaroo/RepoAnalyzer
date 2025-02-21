"""Query patterns for GDScript files."""

from parsers.file_classification import FileType
from .common import COMMON_PATTERNS

GDSCRIPT_PATTERNS = {
    **COMMON_PATTERNS,
    
    "syntax": {
        "function": {
            "pattern": """
            [
                (function_definition
                    name: (name) @syntax.function.name
                    parameters: (parameters) @syntax.function.params
                    return_type: (type)? @syntax.function.return_type
                    body: (body) @syntax.function.body) @syntax.function.def,
                (constructor_definition
                    parameters: (parameters) @syntax.function.params
                    body: (body) @syntax.function.body) @syntax.constructor.def
            ]
            """
        },
        "class": {
            "pattern": """
            (class_definition
                name: (name) @syntax.class.name
                body: (body) @syntax.class.body) @syntax.class.def
            """
        }
    },

    "semantics": {
        "variable": {
            "pattern": """
            [
                (variable_statement
                    name: (name) @semantics.variable.name
                    type: (_)? @semantics.variable.type
                    value: (_)? @semantics.variable.value
                    setget: (setget)? @semantics.variable.setget) @semantics.variable.def,
                (onready_variable_statement
                    name: (name) @semantics.variable.name
                    type: (_)? @semantics.variable.type
                    value: (_)? @semantics.variable.value) @semantics.variable.def
            ]
            """
        },
        "expression": {
            "pattern": """
            [
                (call
                    function: (_) @semantics.expression.name
                    arguments: (_)? @semantics.expression.args) @semantics.expression.call,
                (if_statement
                    condition: (_) @semantics.expression.condition
                    body: (_) @semantics.expression.body) @semantics.expression.if
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
                (class_name_statement
                    name: (_) @structure.namespace.name) @structure.namespace.def,
                (tool_statement) @structure.namespace.tool
            ]
            """
        },
        "import": {
            "pattern": """
            (extends_statement
                name: (_) @structure.import.module) @structure.import.def
            """
        }
    }
} 