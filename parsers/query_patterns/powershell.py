"""Query patterns for PowerShell files."""

POWERSHELL_PATTERNS = {
    "syntax": {
        "function": [
            """
            (function_definition
                name: (identifier) @name
                parameters: (parameter_block)? @params
                body: (script_block) @body) @function
            """
        ]
    },
    "structure": {
        "import": [
            """
            (using_statement
                module: (_) @module) @import
            """
        ]
    },
    "semantics": {
        "variable": [
            """
            (variable
                name: (_) @name) @variable
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