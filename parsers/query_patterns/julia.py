"""Julia-specific Tree-sitter patterns."""

JULIA_PATTERNS = {
    # Function patterns
    "function": """
        [
          (function_definition
            name: (_) @function.name
            parameters: (argument_list) @function.params
            body: (_) @function.body) @function.def,
          (short_function_definition
            name: (_) @function.name
            parameters: (argument_list) @function.params
            body: (_) @function.body) @function.def,
          (do_clause
            parameters: (argument_list) @function.params
            body: (_) @function.body) @function.do
        ]
    """,

    # Module patterns
    "module": """
        [
          (module_definition
            name: (_) @module.name
            body: (_) @module.body) @module.def,
          (baremodule_definition
            name: (_) @module.bare.name
            body: (_) @module.bare.body) @module.bare.def
        ]
    """,

    # Type patterns
    "type": """
        [
          (struct_definition
            name: (_) @type.struct.name
            fields: (_) @type.struct.fields) @type.struct,
          (abstract_definition
            name: (_) @type.abstract.name) @type.abstract,
          (primitive_definition
            name: (type_head) @type.primitive.name
            size: (integer_literal) @type.primitive.size) @type.primitive
        ]
    """,

    # Import/Using patterns
    "import": """
        [
          (import_statement
            path: (import_path) @import.path
            alias: (import_alias)? @import.alias) @import,
          (using_statement
            path: (import_path) @using.path
            alias: (import_alias)? @using.alias) @using
        ]
    """,

    # Expression patterns
    "expression": """
        [
          (call_expression
            function: (_) @expr.call.func
            arguments: (argument_list) @expr.call.args) @expr.call,
          (binary_expression
            left: (_) @expr.binary.left
            operator: (_) @expr.binary.op
            right: (_) @expr.binary.right) @expr.binary,
          (unary_expression
            operator: (_) @expr.unary.op
            operand: (_) @expr.unary.value) @expr.unary
        ]
    """,

    # Control flow patterns
    "control_flow": """
        [
          (if_statement
            condition: (_) @if.condition
            body: (_) @if.body
            alternative: (_)? @if.else) @if,
          (for_statement
            iterators: (_) @for.iterators
            body: (_) @for.body) @for,
          (while_statement
            condition: (_) @while.condition
            body: (_) @while.body) @while,
          (try_statement
            body: (_) @try.body
            catch: (_)? @try.catch
            finally: (_)? @try.finally) @try
        ]
    """,

    # Variable declaration patterns
    "variable": """
        [
          (let_statement
            bindings: (_) @var.let.bindings) @var.let,
          (const_statement
            bindings: (_) @var.const.bindings) @var.const,
          (local_statement
            bindings: (_) @var.local.bindings) @var.local,
          (global_statement
            bindings: (_) @var.global.bindings) @var.global
        ]
    """,

    # Macro patterns
    "macro": """
        [
          (macro_definition
            name: (_) @macro.name
            parameters: (_)? @macro.params
            body: (_) @macro.body) @macro.def,
          (macro_identifier) @macro.identifier,
          (macrocall_expression
            name: (_) @macro.call.name
            arguments: (_)? @macro.call.args) @macro.call
        ]
    """,

    # String patterns
    "string": """
        [
          (string_literal) @string,
          (prefixed_string_literal
            prefix: (identifier) @string.prefix) @string.prefixed,
          (command_literal) @string.command,
          (prefixed_command_literal
            prefix: (identifier) @string.command.prefix) @string.command.prefixed
        ]
    """,

    # Comprehension patterns
    "comprehension": """
        [
          (comprehension_expression
            body: (_) @comprehension.body
            iterators: (_) @comprehension.iterators) @comprehension,
          (generator_expression
            body: (_) @generator.body
            iterators: (_) @generator.iterators) @generator
        ]
    """,

    # Documentation patterns
    "documentation": """
        [
          (line_comment) @doc.line
        ]
    """
} 