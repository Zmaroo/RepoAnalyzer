"""
Query patterns for GraphQL schema files.
"""

GRAPHQL_PATTERNS = {
    "syntax": {
        "class": [
            """
            (type_definition
                name: (name) @name) @class
            """,
            """
            (interface_type_definition
                name: (name) @name) @class
            """
        ],
        "function": [
            """
            (field_definition
                name: (name) @name
                type: (_) @return_type) @function
            """
        ]
    },
    "structure": {
        "namespace": [
            """
            (schema_definition) @namespace
            """
        ],
        "import": [
            """
            (directive_definition
                name: (name) @name) @import
            """
        ]
    },
    "semantics": {
        "type": [
            """
            (named_type
                name: (name) @name) @type
            """
        ],
        "variable": [
            """
            (input_value_definition
                name: (name) @name
                type: (_) @type) @variable
            """
        ]
    },
    "documentation": {
        "docstring": [
            """
            (description) @docstring
            """
        ],
        "comment": [
            """
            (comment) @comment
            """
        ]
    }
} 