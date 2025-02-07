"""Bash-specific Tree-sitter patterns."""

BASH_PATTERNS = {
    # Function patterns
    "function": """
        [
          (function_definition)
        ] @function
    """,

    # Extended function details
    "function_details": """
        [
          (function_definition
            name: (word) @function.name
            body: (_) @function.body) @function.def
        ]
    """,

    # Variable patterns
    "variable": """
        [
          (variable_assignment
            name: (_) @variable.name
            value: (_) @variable.value) @variable.def,
          (declaration_command 
            (variable_name) @variable.declared)
        ]
    """,

    # Control flow patterns
    "control_flow": """
        [
          (if_statement
            condition: (_) @if.condition
            consequence: (_) @if.consequence
            alternative: (_)? @if.alternative) @if,
          (while_statement
            condition: (_) @while.condition
            body: (do_group) @while.body) @while,
          (for_statement
            variable: (variable_name) @for.variable
            value: (_)? @for.value
            body: (do_group) @for.body) @for,
          (case_statement
            value: (_) @case.value
            (case_item
              value: (_) @case.pattern
              body: (_)? @case.body)*) @case
        ]
    """,

    # Command patterns
    "command": """
        [
          (command
            name: (command_name) @command.name
            argument: (_)* @command.args) @command,
          (pipeline
            (_)+ @pipeline.commands) @pipeline
        ]
    """,

    # Expansion patterns
    "expansion": """
        [
          (expansion
            variable: (_) @expansion.var
            operator: (_)? @expansion.op) @expansion,
          (command_substitution
            (_) @cmdsubst.command) @cmdsubst,
          (process_substitution
            (_) @procsubst.command) @procsubst
        ]
    """,

    # Redirection patterns
    "redirection": """
        [
          (file_redirect
            descriptor: (file_descriptor)? @redirect.fd
            destination: (_) @redirect.dest) @redirect,
          (heredoc_redirect
            (_) @heredoc.body) @heredoc
        ]
    """,

    # Array patterns
    "array": """
        [
          (array
            (_)* @array.elements) @array
        ]
    """,

    # String patterns
    "string": """
        [
          (string
            (string_content)? @string.content) @string,
          (raw_string) @string.raw,
          (ansi_c_string) @string.ansi
        ]
    """,

    # Arithmetic patterns
    "arithmetic": """
        [
          (arithmetic_expansion
            (_) @arithmetic.expr) @arithmetic,
          (binary_expression
            left: (_) @arithmetic.left
            operator: (_) @arithmetic.operator
            right: (_) @arithmetic.right) @arithmetic.binary
        ]
    """,

    # Test patterns
    "test": """
        [
          (test_command
            (_) @test.condition) @test
        ]
    """
} 