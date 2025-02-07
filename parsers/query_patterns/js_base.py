"""Base patterns shared between JavaScript variants."""

JS_BASE_PATTERNS = {
    # Function patterns
    "function": """
        [
          (function_declaration
            name: (identifier) @function.name
            parameters: (formal_parameters) @function.params
            body: (statement_block) @function.body) @function.def,
          (arrow_function
            parameters: (formal_parameters) @function.arrow.params
            body: (_) @function.arrow.body) @function.arrow
        ]
    """,

    # Class patterns
    "class": """
        [
          (class_declaration
            name: (identifier) @class.name
            body: (class_body) @class.body) @class.def,
          (method_definition
            name: (property_identifier) @class.method.name
            parameters: (formal_parameters) @class.method.params
            body: (statement_block) @class.method.body) @class.method
        ]
    """,

    # Variable patterns
    "variable": """
        [
          (variable_declaration
            kind: (_) @var.kind
            (variable_declarator
              name: (_) @var.name
              value: (_)? @var.value)) @var.decl,
          (lexical_declaration
            kind: (_) @var.lexical.kind
            (variable_declarator
              name: (_) @var.lexical.name
              value: (_)? @var.lexical.value)) @var.lexical
        ]
    """,

    # Control flow patterns
    "control_flow": """
        [
          (if_statement
            condition: (_) @if.condition
            consequence: (_) @if.consequence
            alternative: (_)? @if.alternative) @if,
          (switch_statement
            condition: (_) @switch.condition
            body: (switch_body) @switch.body) @switch,
          (for_statement
            initializer: (_)? @for.init
            condition: (_)? @for.condition
            increment: (_)? @for.increment
            body: (_) @for.body) @for
        ]
    """,

    # Import/Export patterns
    "module": """
        [
          (import_statement
            source: (string) @import.source
            clause: (_)? @import.clause) @import,
          (export_statement
            declaration: (_)? @export.declaration
            source: (string)? @export.source) @export
        ]
    """,

    # Documentation patterns
    "documentation": """
        [
          (comment) @doc.comment
        ]
    """
} 