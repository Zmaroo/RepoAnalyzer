"""
Query patterns for Scala files.
"""

from .common import COMMON_PATTERNS

SCALA_PATTERNS = {
    "syntax": {
        "function": [
            """
            (function_definition
                name: (identifier) @name
                parameters: (parameters)? @params
                return_type: (_)? @return_type
                body: (_) @body) @function
            """,
            """
            (method_definition
                name: (identifier) @name
                parameters: (parameters)? @params
                return_type: (_)? @return_type
                body: (_) @body) @function
            """
        ],
        "class": [
            """
            (class_definition
                name: (identifier) @name
                type_parameters: (type_parameters)? @type_params
                parameters: (parameters)? @params
                body: (_)? @body) @class
            """,
            """
            (object_definition
                name: (identifier) @name
                body: (_)? @body) @class
            """,
            """
            (trait_definition
                name: (identifier) @name
                type_parameters: (type_parameters)? @type_params
                body: (_)? @body) @class
            """
        ]
    },
    "structure": {
        "namespace": [
            """
            (package_clause
                name: (identifier) @name) @namespace
            """
        ],
        "import": [
            """
            (import_declaration
                importers: (import_importers
                    (importer) @importer)) @import
            """
        ]
    },
    "semantics": {
        "variable": [
            """
            (val_definition
                pattern: (identifier) @name
                type: (_)? @type
                value: (_) @value) @variable
            """,
            """
            (var_definition
                pattern: (identifier) @name
                type: (_)? @type
                value: (_) @value) @variable
            """
        ],
        "type": [
            """
            (type_definition
                name: (identifier) @name
                type_parameters: (type_parameters)? @params
                type: (_) @type) @type_decl
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
            """,
            """
            (block_comment) @comment
            """
        ]
    }
} 