"""
Query patterns for QML files.
"""

QML_PATTERNS = {
    "syntax": {
        "class": [
            """
            (component_definition
                name: (identifier) @name
                body: (object_definition_body) @body) @class
            """
        ],
        "function": [
            """
            (function_declaration
                name: (identifier) @name
                parameters: (formal_parameter_list)? @params
                body: (statement_block) @body) @function
            """
        ]
    },
    "structure": {
        "namespace": [
            """
            (import_statement
                (string_literal) @module) @namespace
            """
        ],
        "import": [
            """
            (import_statement
                (string_literal) @module
                (identifier)? @alias) @import
            """
        ]
    },
    "semantics": {
        "variable": [
            """
            (property_declaration
                name: (identifier) @name
                type: (_)? @type) @variable
            """,
            """
            (binding
                name: (identifier) @name
                value: (_) @value) @variable
            """
        ],
        "expression": [
            """
            (method_call
                name: (identifier) @name
                arguments: (argument_list)? @args) @expression
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