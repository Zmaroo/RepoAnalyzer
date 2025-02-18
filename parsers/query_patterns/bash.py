"""Query patterns for Bash files."""

BASH_PATTERNS = {
    "syntax": {
        "function": [
            """
            (function_definition
                name: (word) @name
                body: (_) @body) @function
            """
        ]
    },
    "structure": {
        "namespace": [
            """
            (case_statement
                value: (_) @case.value
                (case_item
                    value: (_) @case.pattern
                    body: (_)? @case.body)*) @namespace
            """
        ]
    },
    "semantics": {
        "variable": [
            """
            (variable_assignment
                name: (_) @name
                value: (_) @value) @variable
            """,
            """
            (declaration_command 
                (variable_name) @variable)
            """
        ],
        "expression": [
            """
            (command
                name: (command_name) @name
                argument: (_)* @args) @expression
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