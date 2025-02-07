"""Svelte-specific Tree-sitter patterns."""

SVELTE_PATTERNS = {
    # Document patterns
    "document": """
        [
          (document
            (_)* @document.content) @document
        ]
    """,

    # Script patterns
    "script": """
        [
          (script_element
            (start_tag) @script.open
            (raw_text)? @script.content
            (end_tag) @script.close) @script
        ]
    """,

    # Style patterns
    "style": """
        [
          (style_element
            (start_tag) @style.open
            (raw_text)? @style.content
            (end_tag) @style.close) @style
        ]
    """,

    # Element patterns
    "element": """
        [
          (element
            (start_tag
              (tag_name) @element.name
              (attribute)* @element.attrs) @element.open
            (_)* @element.content
            (end_tag)? @element.close) @element
        ]
    """,

    # Control flow patterns
    "control_flow": """
        [
          (if_statement
            condition: (_) @if.condition
            (_)* @if.content) @if,
          (each_statement
            (each_start_expr) @each.start
            (_)* @each.content
            (each_end_expr) @each.end) @each,
          (await_statement
            (_)* @await.content) @await
        ]
    """,

    # Expression patterns
    "expression": """
        [
          (expression
            (_) @expr.content) @expr
        ]
    """,

    # Block patterns
    "block": """
        [
          (const_expr
            (_)* @const.content) @const,
          (debug_expr
            (_)* @debug.content) @debug,
          (html_expr
            (_)* @html.content) @html
        ]
    """,

    # Attribute patterns
    "attribute": """
        [
          (attribute
            name: (attribute_name) @attr.name
            value: (_)? @attr.value) @attr
        ]
    """,

    # Special patterns
    "special": """
        [
          (snippet_statement
            (snippet_start_expr) @snippet.start
            (_)* @snippet.content
            (snippet_end_expr) @snippet.end) @snippet,
          (key_statement
            (_)* @key.content) @key
        ]
    """,

    # Documentation patterns
    "documentation": """
        [
          (comment) @doc.comment
        ]
    """
} 