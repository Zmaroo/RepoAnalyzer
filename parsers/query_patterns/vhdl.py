"""
Query patterns for VHDL files.
"""

VHDL_PATTERNS = {
    "syntax": {
        "function": [
            """
            (function_declaration
                name: (identifier) @name
                parameters: (parameter_list)? @params
                return_type: (_) @return_type) @function
            """,
            """
            (procedure_declaration
                name: (identifier) @name
                parameters: (parameter_list)? @params) @function
            """
        ],
        "class": [
            """
            (entity_declaration
                name: (identifier) @name
                ports: (port_clause)? @ports) @class
            """,
            """
            (architecture_body
                name: (identifier) @name
                entity: (identifier) @entity) @class
            """
        ]
    },
    "structure": {
        "namespace": [
            """
            (package_declaration
                name: (identifier) @name) @namespace
            """,
            """
            (library_clause
                names: (identifier_list) @names) @namespace
            """
        ],
        "import": [
            """
            (use_clause
                names: (selected_name)+ @names) @import
            """
        ]
    },
    "semantics": {
        "variable": [
            """
            (signal_declaration
                names: (identifier_list) @names
                type: (_) @type) @variable
            """,
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
                definition: (_) @definition) @type
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