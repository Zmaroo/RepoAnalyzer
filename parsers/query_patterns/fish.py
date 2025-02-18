"""Query patterns for Fish shell files."""

FISH_PATTERNS = {
    "syntax": {
        "function": [
            """
            (function_definition
                name: (_) @function.name
                option: (_)* @function.options
                [
                    (command) @function.command
                    (begin_statement) @function.block
                    (if_statement) @function.if
                    (while_statement) @function.while
                    (for_statement) @function.for
                    (switch_statement) @function.switch
                    (return) @function.return
                ]*) @function.def
            """
        ]
    },
    "structure": {
        "namespace": [
            """
            (begin_statement) @namespace
            """
        ]
    },
    "semantics": {
        "variable": [
            """
            (variable_expansion
                (variable_name) @var.name
                (list_element_access)? @var.index) @variable
            """
        ],
        "expression": [
            """
            (command
                name: (_) @command.name
                argument: (_)* @command.args) @expression
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