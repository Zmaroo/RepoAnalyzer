"""Fortran-specific Tree-sitter patterns."""

FORTRAN_PATTERNS = {
    # Function patterns
    "function": """
        [
          (function)
          (subroutine)
          (module_subprogram)
        ] @function
    """,

    # Extended pattern for detailed function information
    "function_details": """
        [
          (function
            name: (name) @function.name
            parameters: (parameter_list)? @function.params
            result: (function_result)? @function.return_type
            body: (_)* @function.body) @function.def,
          
          (subroutine
            name: (name) @function.name
            parameters: (parameter_list)? @function.params
            body: (_)* @function.body) @function.def
        ]
    """,

    # Module patterns
    "module": """
        [
          (module
            name: (name) @module.name
            body: (_)* @module.body) @module.def,
          (submodule
            name: (name) @submodule.name
            body: (_)* @submodule.body) @submodule.def
        ]
    """,

    # Type patterns
    "type": """
        [
          (derived_type_definition
            name: (name) @type.name
            body: (_)* @type.body) @type.def,
          (intrinsic_type) @type.intrinsic
        ]
    """,

    # Variable declaration patterns
    "variable": """
        [
          (variable_declaration
            type: (_) @variable.type
            declarator: [
              (identifier) @variable.name
              (init_declarator
                name: (identifier) @variable.name
                value: (_) @variable.value)
            ]) @variable.def
        ]
    """,

    # Control flow patterns
    "control_flow": """
        [
          (if_statement
            condition: (_) @if.condition
            body: (_)* @if.body) @if,
          
          (do_loop_statement
            variable: (identifier) @loop.var
            range: (_) @loop.range
            body: (_)* @loop.body) @loop,
          
          (where_statement
            condition: (_) @where.condition
            body: (_)* @where.body) @where
        ]
    """,

    # Program unit patterns
    "program": """
        [
          (program
            name: (name) @program.name
            body: (_)* @program.body) @program.def
        ]
    """,

    # Interface patterns
    "interface": """
        [
          (interface
            name: (name)? @interface.name
            body: (_)* @interface.body) @interface.def
        ]
    """
} 