"""C-specific Tree-sitter patterns."""

C_PATTERNS = {
    # Basic pattern for function detection
    "function": """
        [
          (function_definition)
        ] @function
    """,
    
    # Extended pattern for detailed function information
    "function_details": """
        [
          (function_definition
            type: (_) @function.return_type
            declarator: (function_declarator
              declarator: (identifier) @function.name
              parameters: (parameter_list
                (parameter_declaration
                  type: (_) @function.param.type
                  declarator: (_)? @function.param.name)*) @function.params)
            body: (compound_statement) @function.body) @function.def
        ]
    """,

    # Struct patterns
    "struct": """
        [
          (struct_specifier
            name: (type_identifier) @struct.name
            body: (field_declaration_list
              (field_declaration
                type: (_) @struct.field.type
                declarator: (field_identifier) @struct.field.name)*) @struct.body) @struct.def
        ]
    """,

    # Type patterns
    "type": """
        [
          (type_identifier) @type.name,
          (primitive_type) @type.primitive,
          (sized_type_specifier) @type.sized,
          (type_qualifier) @type.qualifier,
          (enum_specifier
            name: (type_identifier) @enum.name
            body: (enumerator_list
              (enumerator
                name: (identifier) @enum.value.name
                value: (_)? @enum.value.init)*)) @enum.def
        ]
    """,

    # Preprocessor patterns
    "preprocessor": """
        [
          (preproc_include
            path: (_) @include.path) @include,
          (preproc_def
            name: (identifier) @define.name
            value: (_)? @define.value) @define,
          (preproc_ifdef
            name: (identifier) @ifdef.name) @ifdef,
          (preproc_function_def
            name: (identifier) @macro.name
            parameters: (preproc_params)? @macro.params) @macro
        ]
    """,

    # Control flow patterns
    "control_flow": """
        [
          (if_statement
            condition: (parenthesized_expression) @if.condition
            consequence: (_) @if.consequence
            alternative: (_)? @if.alternative) @if,
          (while_statement
            condition: (parenthesized_expression) @while.condition
            body: (_) @while.body) @while,
          (for_statement
            initializer: (_)? @for.init
            condition: (_)? @for.condition
            update: (_)? @for.update
            body: (_) @for.body) @for,
          (switch_statement
            condition: (parenthesized_expression) @switch.condition
            body: (compound_statement
              (case_statement
                value: (_) @case.value
                body: (_)? @case.body)*)) @switch
        ]
    """,

    # Variable declaration patterns
    "variable": """
        [
          (declaration
            type: (_) @variable.type
            declarator: (init_declarator
              declarator: (identifier) @variable.name
              value: (_)? @variable.value)) @variable.def
        ]
    """,

    # Array patterns
    "array": """
        [
          (array_declarator
            declarator: (_) @array.name
            size: (_)? @array.size) @array.def
        ]
    """,

    # Pointer patterns
    "pointer": """
        [
          (pointer_declarator
            declarator: (_) @pointer.name) @pointer.def,
          (pointer_expression
            operator: (_) @pointer.operator
            argument: (_) @pointer.argument) @pointer
        ]
    """
} 