"""
Query patterns for SQL files.
"""

SQL_PATTERNS = {
    "syntax": {
        "function": [
            """
            (create_function
                name: (identifier) @name
                parameters: (parameter_list)? @params
                return_type: (_)? @return_type
                body: (_) @body) @function
            """,
            """
            (create_procedure
                name: (identifier) @name
                parameters: (parameter_list)? @params
                body: (_) @body) @function
            """
        ],
        "class": [
            """
            (create_table
                name: (identifier) @name
                definition: (column_definitions) @columns) @class
            """,
            """
            (create_view
                name: (identifier) @name
                query: (_) @query) @class
            """
        ]
    },
    "structure": {
        "namespace": [
            """
            (create_schema
                name: (identifier) @name) @namespace
            """,
            """
            (create_database
                name: (identifier) @name) @namespace
            """
        ],
        "import": [
            """
            (import_statement
                file: (string) @file) @import
            """
        ]
    },
    "semantics": {
        "variable": [
            """
            (column_definition
                name: (identifier) @name
                type: (_) @type
                constraints: (_)* @constraints) @variable
            """,
            """
            (declare_variable
                name: (identifier) @name
                type: (_) @type) @variable
            """
        ],
        "type": [
            """
            (data_type) @type
            """
        ]
    },
    "documentation": {
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