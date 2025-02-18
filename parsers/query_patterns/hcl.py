"""Query patterns for HCL files."""

HCL_PATTERNS = {
    "syntax": {
        "function": [
            """
            (function_call
                name: (identifier) @function.name
                arguments: (_)* @function.args) @function
            """
        ]
    },
    "structure": {
        "namespace": [
            """
            (block
                (identifier) @block.type
                (string_lit)* @block.labels
                (body) @block.body) @namespace
            """
        ]
    },
    "semantics": {
        "variable": [
            """
            (attribute
                name: (identifier) @attr.name
                value: (expression) @attr.value) @variable
            """
        ],
        "expression": [
            """
            (expression
                (_) @expr.content) @expression
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