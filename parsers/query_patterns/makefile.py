"""Query patterns for Makefile files."""

MAKEFILE_PATTERNS = {
    "syntax": {
        "function": [
            """
            (rule
                targets: (_) @name
                prerequisites: (_)? @params
                recipe: (_)* @body) @function
            """
        ]
    },
    "semantics": {
        "variable": [
            """
            (variable_definition
                name: (_) @name
                value: (_) @value) @variable
            """
        ]
    }
}