"""
Query patterns for Nix files.
"""

NIX_PATTERNS = {
    "syntax": {
        "function": [
            """
            (function
                params: (formal_args) @params
                body: (_) @body) @function
            """,
            """
            (lambda
                params: (formal_args) @params
                body: (_) @body) @function
            """
        ]
    },
    "structure": {
        "namespace": [
            """
            (attrset) @namespace
            """
        ],
        "import": [
            """
            (import_statement
                path: (_) @path) @import
            """,
            """
            (with_statement
                path: (_) @path) @import
            """
        ]
    },
    "semantics": {
        "variable": [
            """
            (binding
                name: (attrpath) @name
                value: (_) @value) @variable
            """,
            """
            (let_binding
                name: (identifier) @name
                value: (_) @value) @variable
            """
        ],
        "expression": [
            """
            (apply_expression
                function: (_) @function
                argument: (_) @argument) @expression
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