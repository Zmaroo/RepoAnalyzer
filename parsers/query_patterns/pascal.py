"""
Query patterns for Pascal files.
"""

from .common import COMMON_PATTERNS

PASCAL_PATTERNS = {
    "syntax": {
        "function": [
            """
            (function_declaration
                name: (identifier) @name
                parameters: (formal_parameter_list)? @params
                return_type: (type_identifier)? @return_type
                block: (block) @body) @function
            """,
            """
            (procedure_declaration
                name: (identifier) @name
                parameters: (formal_parameter_list)? @params
                block: (block) @body) @function
            """
        ],
        "class": [
            """
            (type_declaration
                name: (identifier) @name
                type: (record_type)? @fields) @class
            """
        ]
    },
    "structure": {
        "namespace": [
            """
            (program
                name: (identifier) @name) @namespace
            """,
            """
            (unit
                name: (identifier) @name) @namespace
            """
        ],
        "import": [
            """
            (uses_clause
                units: (identifier_list) @units) @import
            """
        ]
    },
    "semantics": {
        "variable": [
            """
            (variable_declaration
                names: (identifier_list) @names
                type: (_) @type) @variable
            """
        ],
        "type": [
            """
            (type_declaration
                name: (identifier) @name
                type: (_) @type) @type_decl
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