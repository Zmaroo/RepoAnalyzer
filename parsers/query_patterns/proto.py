"""
Query patterns for Protocol Buffers files.
"""

PROTO_PATTERNS = {
    "syntax": {
        "class": [
            """
            (message_definition
                name: (identifier) @name
                body: (message_body) @body) @class
            """,
            """
            (enum_definition
                name: (identifier) @name
                body: (enum_body) @body) @class
            """
        ],
        "function": [
            """
            (rpc
                name: (identifier) @name
                input_type: (_) @input
                output_type: (_) @output) @function
            """
        ]
    },
    "structure": {
        "namespace": [
            """
            (package_statement
                name: (full_ident) @name) @namespace
            """
        ],
        "import": [
            """
            (import_statement
                path: (string_literal) @path) @import
            """
        ]
    },
    "semantics": {
        "variable": [
            """
            (field
                name: (identifier) @name
                type: (_) @type
                number: (_) @number) @variable
            """
        ],
        "type": [
            """
            (message_type
                name: (identifier) @name) @type
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