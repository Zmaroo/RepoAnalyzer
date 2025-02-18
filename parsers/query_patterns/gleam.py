"""Query patterns for Gleam files."""

GLEAM_PATTERNS = {
    "syntax": {
        "function": [
            """
            (function_definition
                name: (identifier) @function.name
                parameters: (function_parameters) @function.params
                return_type: (_)? @function.return_type
                body: (function_body) @function.body) @function.def
            """,
            """
            (anonymous_function
                parameters: (function_parameters) @function.anon.params
                return_type: (_)? @function.anon.return_type
                body: (function_body) @function.anon.body) @function.anon
            """
        ],
        "class": [
            """
            (type_definition
                name: (type_name) @type.name
                constructors: (data_constructors
                    (data_constructor
                        name: (constructor_name) @type.constructor.name
                        arguments: (data_constructor_arguments)? @type.constructor.args)*) @type.constructors) @class
            """
        ]
    },
    "structure": {
        "namespace": [
            """
            (module
                name: (_) @module.name) @namespace
            """
        ],
        "import": [
            """
            (import
                module: (module) @import.module
                alias: (_)? @import.alias
                imports: (unqualified_imports)? @import.unqualified) @import
            """
        ]
    },
    "semantics": {
        "variable": [
            """
            (let
                pattern: (_) @let.pattern
                type: (_)? @let.type
                value: (_) @let.value) @variable
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