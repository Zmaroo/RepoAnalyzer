"""Query patterns for Starlark files."""

STARLARK_PATTERNS = {
    "syntax": {
        "function": [
            """
            (function_definition
                name: (identifier) @name
                parameters: (parameters) @params
                body: (block) @body) @function
            """,
            """
            (lambda
                parameters: (lambda_parameters)? @params
                body: (expression) @body) @function
            """
        ]
    },
    "structure": {
        "import": [
            """
            (import_statement
                name: (dotted_name) @module) @import
            """,
            """
            (import_from_statement
                module_name: (dotted_name) @module
                name: (dotted_name) @name) @import
            """
        ]
    },
    "semantics": {
        "variable": [
            """
            (assignment
                left: (_) @name
                right: (_) @value) @variable
            """
        ],
        "expression": [
            """
            (call
                function: (_) @function
                arguments: (_)? @args) @expression
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