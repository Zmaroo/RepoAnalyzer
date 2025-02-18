"""Query patterns for Squirrel files."""

SQUIRREL_PATTERNS = {
    "syntax": {
        "function": [
            """
            (function_declaration
                name: (identifier) @name
                parameters: (parameter_list)? @params
                body: (block) @body) @function
            """,
            """
            (anonymous_function
                parameters: (parameter_list)? @params
                body: (block) @body) @function
            """
        ]
    },
    "semantics": {
        "variable": [
            """
            (variable_declaration
                name: (identifier) @name
                value: (_)? @value) @variable
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