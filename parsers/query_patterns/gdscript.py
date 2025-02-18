"""Query patterns for GDScript files."""

GDSCRIPT_PATTERNS = {
    "syntax": {
        "function": [
            """
            (function_definition
                name: (name) @function.name
                parameters: (parameters) @function.params
                return_type: (type)? @function.return_type
                body: (body) @function.body) @function.def
            """,
            """
            (constructor_definition
                parameters: (parameters) @constructor.params
                body: (body) @function.body) @constructor.def
            """
        ],
        "class": [
            """
            (class_definition
                name: (name) @class.name
                body: (body) @class.body) @class.def
            """
        ]
    },
    "structure": {
        "namespace": [
            """
            (class_name_statement
                name: (_) @class.declaration) @namespace
            """
        ]
    },
    "semantics": {
        "variable": [
            """
            (variable_statement
                name: (name) @var.name
                type: (_)? @var.type
                setget: (setget)? @var.setget) @variable
            """
        ],
        "expression": [
            """
            (call
                function: (_) @expr.call.func
                arguments: (_)? @expr.call.args) @expression
            """
        ]
    },
    "documentation": {
        "comment": [
            """
            (comment) @comment
            """
        ]
    }
} 