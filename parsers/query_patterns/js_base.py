"""Base patterns shared between JavaScript variants."""

from .js_ts_shared import JS_TS_SHARED_PATTERNS

JS_BASE_PATTERNS = {
    # Use the more detailed shared patterns
    "function": JS_TS_SHARED_PATTERNS["function"],
    "class": JS_TS_SHARED_PATTERNS["class"],
    "import": JS_TS_SHARED_PATTERNS["import"],

    # Additional JavaScript-specific patterns
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
            body: (_) @for.body) @for,
          (try_statement
            body: (_) @try.body
            handler: (catch_clause
              parameter: (_)? @try.catch.param
              body: (_) @try.catch.body)? @try.catch
            finalizer: (_)? @try.finally) @try
        ]
    """,

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

    "documentation": """
        [
          (comment) @doc.comment,
          (hash_bang_line) @doc.hashbang
        ]
    """
} 