"""Query patterns for C files."""

C_PATTERNS = {
    "syntax": {
        "function": [
            """
            (function_definition
                type: (_) @function.return_type
                declarator: (function_declarator
                    declarator: (identifier) @name
                    parameters: (parameter_list) @params)
                body: (compound_statement) @body) @function
            """
        ],
        "class": [
            """
            (struct_specifier
                name: (type_identifier) @name
                body: (field_declaration_list) @body) @class
            """
        ]
    },
    "structure": {
        "namespace": [
            """
            (translation_unit
                (_)* @content) @namespace
            """
        ],
        "import": [
            """
            (preproc_include
                path: (_) @path) @import
            """
        ]
    },
    "semantics": {
        "variable": [
            """
            (declaration
                type: (_) @variable.type
                declarator: (init_declarator
                    declarator: (identifier) @name
                    value: (_)? @value)) @variable
            """
        ],
        "type": [
            """
            (type_definition
                type: (_) @type.definition
                declarator: (_) @type.name) @type
            """
        ]
    },
    "documentation": {
        "comment": [
            """
            [(comment) (comment_multiline)] @comment
            """
        ]
    }
} 