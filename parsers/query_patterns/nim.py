"""
Query patterns for Nim files.
"""

NIM_PATTERNS = {
    "syntax": {
        "function": [
            """
            (proc_declaration
                name: (identifier) @name
                parameters: (parameter_list)? @params
                return_type: (_)? @return_type
                body: (statement_list) @body) @function
            """,
            """
            (func_declaration
                name: (identifier) @name
                parameters: (parameter_list)? @params
                return_type: (_)? @return_type
                body: (statement_list) @body) @function
            """
        ],
        "class": [
            """
            (type_declaration
                name: (identifier) @name
                type_def: (_) @type) @class
            """,
            """
            (object_declaration
                name: (identifier) @name
                fields: (_) @fields) @class
            """
        ]
    },
    "structure": {
        "namespace": [
            """
            (module_declaration
                name: (identifier) @name) @namespace
            """
        ],
        "import": [
            """
            (import_statement
                modules: (import_modules) @modules) @import
            """,
            """
            (from_import_statement
                module: (identifier) @module
                imports: (import_list) @imports) @import
            """
        ]
    },
    "semantics": {
        "variable": [
            """
            (var_declaration
                name: (identifier) @name
                type: (_)? @type
                value: (_)? @value) @variable
            """,
            """
            (const_declaration
                name: (identifier) @name
                value: (_) @value) @variable
            """
        ],
        "type": [
            """
            (type_section
                declarations: (type_declaration) @type) @type_section
            """
        ]
    },
    "documentation": {
        "docstring": [
            """
            (documentation_comment) @docstring
            """
        ],
        "comment": [
            """
            (comment) @comment
            """,
            """
            (multiline_comment) @comment
            """
        ]
    }
} 