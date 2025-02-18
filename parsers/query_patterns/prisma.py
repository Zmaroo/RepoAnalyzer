"""
Query patterns for Prisma schema files.
"""

PRISMA_PATTERNS = {
    "syntax": {
        "class": [
            """
            (model_declaration
                name: (identifier) @name
                properties: (property_declarations) @properties) @class
            """,
            """
            (enum_declaration
                name: (identifier) @name
                values: (enum_value_declarations) @values) @class
            """
        ],
        "function": [
            """
            (field_declaration
                name: (identifier) @name
                type: (field_type) @type
                attributes: (attribute_list)? @attributes) @function
            """
        ]
    },
    "structure": {
        "namespace": [
            """
            (datasource_declaration
                name: (identifier) @name
                properties: (property_declarations) @properties) @namespace
            """,
            """
            (generator_declaration
                name: (identifier) @name
                properties: (property_declarations) @properties) @namespace
            """
        ]
    },
    "semantics": {
        "variable": [
            """
            (property_declaration
                name: (identifier) @name
                value: (_) @value) @variable
            """
        ],
        "type": [
            """
            (field_type) @type
            """
        ]
    },
    "documentation": {
        "docstring": [
            """
            (doc_comment) @docstring
            """
        ],
        "comment": [
            """
            (comment) @comment
            """
        ]
    }
} 