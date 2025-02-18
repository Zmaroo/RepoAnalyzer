"""Query patterns for CMake files."""

CMAKE_PATTERNS = {
    "syntax": {
        "function": [
            """
            (function_def
                (function_command
                    (argument_list) @function.def.args) @function.def.header
                (body) @function.def.body
                (endfunction_command) @function.def.end) @function.def
            """,
            """
            (normal_command
                (identifier) @function.call.name
                (argument_list) @function.call.args) @function.call
            """
        ]
    },
    "structure": {
        "namespace": [
            """
            (block_def
                (block_command
                    (argument_list) @block.args) @block.start
                (body) @block.body
                (endblock_command) @block.end) @block
            """
        ]
    },
    "semantics": {
        "variable": [
            """
            (variable_ref
                (normal_var
                    (variable) @var.normal) @var.ref) @var
            """
        ],
        "expression": [
            """
            (argument
                (unquoted_argument
                    (escape_sequence)* @arg.unquoted.escape
                    (variable_ref)* @arg.unquoted.var) @arg.unquoted) @arg
            """
        ]
    },
    "documentation": {
        "comment": [
            """
            (line_comment) @doc.line
            """,
            """
            (bracket_comment) @doc.bracket
            """
        ]
    }
} 