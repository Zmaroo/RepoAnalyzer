"""Query patterns for Fortran files."""

FORTRAN_PATTERNS = {
    "syntax": {
        "function": [
            """
            (function
                name: (name) @function.name
                parameters: (parameter_list)? @function.params
                result: (function_result)? @function.return_type
                body: (_)* @function.body) @function.def
            """,
            """
            (subroutine
                name: (name) @function.name
                parameters: (parameter_list)? @function.params
                body: (_)* @function.body) @function.def
            """
        ],
        "class": [
            """
            (derived_type_definition
                name: (name) @type.name
                body: (_)* @type.body) @class
            """
        ]
    },
    "structure": {
        "namespace": [
            """
            (module
                name: (name) @module.name
                body: (_)* @module.body) @namespace
            """
        ]
    },
    "semantics": {
        "variable": [
            """
            (variable_declaration
                type: (_) @variable.type
                declarator: [
                    (identifier) @variable.name
                    (init_declarator
                        name: (identifier) @variable.name
                        value: (_) @variable.value)
                ]) @variable
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