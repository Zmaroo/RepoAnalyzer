"""Query patterns for Elixir files."""

ELIXIR_PATTERNS = {
    "syntax": {
        "function": [
            """
            (stab_clause
                left: (arguments) @function.params
                operator: (_) @function.operator
                right: (body) @function.body) @function.def
            """
        ],
        "class": [
            """
            (do_block
                (stab_clause)* @block.clauses) @class
            """
        ]
    },
    "structure": {
        "namespace": [
            """
            (block
                (_)* @block.content) @namespace
            """
        ]
    },
    "semantics": {
        "variable": [
            """
            (string
                quoted_content: (_)? @string.content
                interpolation: (_)* @string.interpolation) @variable
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