"""Dart-specific Tree-sitter patterns."""

DART_PATTERNS = {
    # Function patterns
    "function": """
        [
          (function_signature)
          (function_body)
          (function_expression)
        ] @function
    """,

    # Class patterns
    "class": """
        [
          (class_definition
            name: (type_identifier) @class.name
            body: (_) @class.body) @class.def,
          (mixin_declaration
            name: (type_identifier) @mixin.name
            body: (_) @mixin.body) @mixin.def
        ]
    """,

    # Variable patterns
    "variable": """
        [
          (initialized_identifier_list
            (identifier) @variable.name
            type: (_)? @variable.type
            value: (_)? @variable.value) @variable.def,
          (static_final_declaration_list
            (identifier) @variable.static.name
            type: (_)? @variable.static.type
            value: (_)? @variable.static.value) @variable.static.def
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
            body: (_) @switch.body) @switch,
          (for_statement
            body: (_) @for.body) @for,
          (while_statement
            condition: (_) @while.condition
            body: (_) @while.body) @while,
          (do_statement
            body: (_) @do.body
            condition: (_) @do.condition) @do
        ]
    """,

    # Expression patterns
    "expression": """
        [
          (binary_expression
            left: (_) @binary.left
            operator: (_) @binary.operator
            right: (_) @binary.right) @binary,
          (unary_expression
            operand: (_) @unary.operand
            operator: (_) @unary.operator) @unary,
          (conditional_expression
            condition: (_) @conditional.condition
            consequence: (_) @conditional.consequence
            alternative: (_) @conditional.alternative) @conditional
        ]
    """,

    # Type patterns
    "type": """
        [
          (type_identifier) @type.name,
          (nullable_type) @type.nullable,
          (function_type) @type.function,
          (type_arguments
            (_)* @type.argument) @type.arguments
        ]
    """,

    # Import/Export patterns
    "import": """
        [
          (import_or_export
            path: (string_literal) @import.path
            configuration: (_)? @import.config) @import
        ]
    """,

    # Annotation patterns
    "annotation": """
        [
          (annotation
            name: (_) @annotation.name
            arguments: (_)? @annotation.args) @annotation
        ]
    """,

    # Error handling patterns
    "error_handling": """
        [
          (try_statement
            body: (_) @try.body
            (catch_clause
              type: (_)? @catch.type
              parameter: (_)? @catch.param
              body: (_) @catch.body)*
            (finally_clause
              body: (_) @finally.body)?) @try,
          (throw_expression
            (_) @throw.value) @throw
        ]
    """,

    # Async patterns
    "async": """
        [
          (async_function_body
            (_) @async.body) @async,
          (await_expression
            (_) @await.value) @await
        ]
    """,

    # Pattern matching
    "pattern": """
        [
          (pattern_variable_declaration
            pattern: (_) @pattern.match
            value: (_) @pattern.value) @pattern.def,
          (constant_pattern
            value: (_) @pattern.const.value) @pattern.const,
          (null_check_pattern
            pattern: (_) @pattern.null_check.inner) @pattern.null_check,
          (null_assert_pattern
            pattern: (_) @pattern.null_assert.inner) @pattern.null_assert
        ]
    """
} 