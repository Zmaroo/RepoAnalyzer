"""
Query patterns for R files.
"""

R_PATTERNS = {
    "syntax": {
        "function": [
            """
            (function_definition
                name: (identifier) @name
                parameters: (formal_parameters)? @params
                body: (_) @body) @function
            """
        ],
        "class": [
            """
            (setClass_call
                name: (string_literal) @name
                slots: (_)? @slots) @class
            """
        ]
    },
    "structure": {
        "namespace": [
            """
            (library_call
                package: (identifier) @package) @namespace
            """,
            """
            (source_call
                file: (string_literal) @file) @namespace
            """
        ],
        "import": [
            """
            (library_call
                package: (identifier) @package) @import
            """,
            """
            (require_call
                package: (string_literal) @package) @import
            """
        ]
    },
    "semantics": {
        "variable": [
            """
            (left_assignment
                name: (identifier) @name
                value: (_) @value) @variable
            """,
            """
            (right_assignment
                name: (identifier) @name
                value: (_) @value) @variable
            """
        ],
        "expression": [
            """
            (function_call
                function: (identifier) @name
                arguments: (arguments)? @args) @expression
            """
        ]
    },
    "documentation": {
        "docstring": [
            """
            (roxygen_comment) @docstring
            """
        ],
        "comment": [
            """
            (comment) @comment
            """
        ]
    }
} 