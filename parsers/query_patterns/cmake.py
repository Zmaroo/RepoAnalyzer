"""CMake-specific Tree-sitter patterns."""

CMAKE_PATTERNS = {
    # Function patterns
    "function": """
        [
          (function_def
            (function_command
              (argument_list) @function.def.args) @function.def.header
            (body) @function.def.body
            (endfunction_command) @function.def.end) @function.def,
          (normal_command
            (identifier) @function.call.name
            (argument_list) @function.call.args) @function.call
        ]
    """,

    # Macro patterns
    "macro": """
        [
          (macro_def
            (macro_command
              (argument_list) @macro.def.args) @macro.def.header
            (body) @macro.def.body
            (endmacro_command) @macro.def.end) @macro.def
        ]
    """,

    # Control flow patterns
    "control_flow": """
        [
          (if_condition
            (if_command
              (argument_list) @if.condition) @if.start
            (body)? @if.body
            (elseif_command
              (argument_list) @if.elseif.condition)* @if.elseif
            (else_command)? @if.else
            (endif_command) @if.end) @if,
          (foreach_loop
            (foreach_command
              (argument_list) @foreach.args) @foreach.start
            (body) @foreach.body
            (endforeach_command) @foreach.end) @foreach,
          (while_loop
            (while_command
              (argument_list) @while.condition) @while.start
            (body) @while.body
            (endwhile_command) @while.end) @while
        ]
    """,

    # Block patterns
    "block": """
        [
          (block_def
            (block_command
              (argument_list) @block.args) @block.start
            (body) @block.body
            (endblock_command) @block.end) @block
        ]
    """,

    # Variable patterns
    "variable": """
        [
          (variable_ref
            (normal_var
              (variable) @var.normal) @var.ref,
            (cache_var
              (variable) @var.cache) @var.cache_ref,
            (env_var
              (variable) @var.env) @var.env_ref) @var
        ]
    """,

    # Argument patterns
    "argument": """
        [
          (argument
            (unquoted_argument
              (escape_sequence)* @arg.unquoted.escape
              (variable_ref)* @arg.unquoted.var) @arg.unquoted,
            (quoted_argument
              (quoted_element
                (escape_sequence)* @arg.quoted.escape
                (variable_ref)* @arg.quoted.var)? @arg.quoted.element) @arg.quoted,
            (bracket_argument) @arg.bracket) @arg
        ]
    """,

    # Command patterns
    "command": """
        [
          (normal_command
            (identifier) @cmd.name
            (argument_list
              (argument)* @cmd.args)?) @cmd
        ]
    """,

    # String patterns
    "string": """
        [
          (quoted_argument
            (quoted_element)? @string.quoted) @string,
          (unquoted_argument
            (escape_sequence)* @string.unquoted.escape) @string.unquoted,
          (bracket_argument) @string.bracket
        ]
    """,

    # Documentation patterns
    "documentation": """
        [
          (line_comment) @doc.line,
          (bracket_comment) @doc.bracket
        ]
    """
} 