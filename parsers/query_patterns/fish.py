"""Fish shell-specific Tree-sitter patterns."""

FISH_PATTERNS = {
    # Function patterns
    "function": """
        [
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
        ]
    """,

    # Control flow patterns
    "control_flow": """
        [
          (if_statement
            condition: (_)* @if.condition
            (else_clause)? @if.else
            (else_if_clause
              condition: (_)* @if.elseif.condition)* @if.elseif) @if,
          
          (while_statement
            condition: (_)* @while.condition) @while,
          
          (for_statement
            variable: (variable_name) @for.var
            value: (_)* @for.values) @for,
          
          (switch_statement
            value: (_) @switch.value
            (case_clause)* @switch.cases) @switch,
            
          (begin_statement) @block
        ]
    """,

    # Command patterns
    "command": """
        [
          (command
            name: (_) @command.name
            argument: (_)* @command.args
            redirect: [
              (file_redirect
                operator: (direction) @command.redirect.op
                destination: (_) @command.redirect.dest)
              (stream_redirect) @command.redirect.stream
            ]?) @command,
          
          (pipe
            (_)* @pipe.commands) @pipe
        ]
    """,

    # Variable patterns
    "variable": """
        [
          (variable_expansion
            (variable_name) @var.name
            (list_element_access)? @var.index) @var.expansion
        ]
    """,

    # String patterns
    "string": """
        [
          (double_quote_string
            (command_substitution)? @string.command
            (variable_expansion)? @string.var
            (escape_sequence)? @string.escape) @string.double,
          
          (single_quote_string
            (escape_sequence)? @string.escape) @string.single
        ]
    """,

    # Program structure
    "program": """
        [
          (program
            [
              (function_definition) @program.function
              (command) @program.command
              (begin_statement) @program.block
              (if_statement) @program.if
              (while_statement) @program.while
              (for_statement) @program.for
              (switch_statement) @program.switch
            ]*) @program.def
        ]
    """,

    # Error handling and flow control
    "error_handling": """
        [
          (break) @break,
          (continue) @continue,
          (return
            (_)? @return.value) @return
        ]
    """,

    # Command substitution
    "substitution": """
        [
          (command_substitution
            (_)* @subst.commands) @subst,
          (brace_expansion
            (_)* @brace.content) @brace
        ]
    """
} 