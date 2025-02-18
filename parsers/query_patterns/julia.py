"""
Query patterns for Julia files.
"""

JULIA_PATTERNS = {
    "syntax": {
        "function": [
            """
            (function_definition
                name: (identifier) @name
                parameters: (parameter_list) @params
                body: (block) @body) @function
            """,
            """
            (short_function_definition
                name: (identifier) @name
                parameters: (parameter_list) @params
                body: (_) @body) @function
            """
        ],
        "class": [
            """
            (struct_definition
                name: (identifier) @name
                body: (field_list) @body) @class
            """,
            """
            (abstract_definition
                name: (identifier) @name) @class
            """
        ]
    },
    "structure": {
        "namespace": [
            """
            (module_definition
                name: (identifier) @name
                body: (block) @body) @namespace
            """
        ],
        "import": [
            """
            (import_statement
                (identifier) @module) @import
            """,
            """
            (using_statement
                (identifier) @module) @import
            """
        ]
    },
    "semantics": {
        "variable": [
            """
            (assignment
                left: (identifier) @name
                right: (_) @value) @variable
            """,
            """
            (const_statement
                name: (identifier) @name
                value: (_) @value) @variable
            """
        ],
        "type": [
            """
            (type_definition
                name: (identifier) @name
                value: (_) @type) @type_decl
            """
        ]
    },
    "documentation": {
        "docstring": [
            """
            (string_literal) @docstring
            """
        ],
        "comment": [
            """
            (line_comment) @comment
            """,
            """
            (block_comment) @comment
            """
        ]
    }
} 