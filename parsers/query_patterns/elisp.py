"""Emacs Lisp-specific Tree-sitter patterns."""

ELISP_PATTERNS = {
    # Function definition patterns
    "function": """
        [
          (function_definition
            name: (symbol) @function.name
            parameters: (_)? @function.params
            docstring: (string)? @function.doc
            [
              (bytecode) @function.bytecode
              (list) @function.body
              (special_form) @function.special
            ]*) @function.def
        ]
    """,

    # Macro definition patterns
    "macro": """
        [
          (macro_definition
            name: (symbol) @macro.name
            parameters: (_)? @macro.params
            docstring: (string)? @macro.doc
            [
              (list) @macro.body
              (special_form) @macro.special
            ]*) @macro.def
        ]
    """,

    # Special form patterns
    "special_form": """
        [
          (special_form
            [
              (list) @special.list
              (symbol) @special.symbol
              (string) @special.string
              (integer) @special.integer
              (float) @special.float
              (char) @special.char
            ]*) @special.def
        ]
    """,

    # List patterns
    "list": """
        [
          (list
            [
              (symbol) @list.symbol
              (string) @list.string
              (integer) @list.integer
              (float) @list.float
              (char) @list.char
              (list) @list.nested
              (quote) @list.quote
              (unquote) @list.unquote
              (unquote_splice) @list.splice
            ]*) @list.def
        ]
    """,

    # Quote patterns
    "quote": """
        [
          (quote
            [
              (list) @quote.list
              (symbol) @quote.symbol
              (vector) @quote.vector
            ]) @quote.def,
          (unquote
            (_) @unquote.value) @unquote.def,
          (unquote_splice
            (_) @splice.value) @splice.def
        ]
    """,

    # Vector patterns
    "vector": """
        [
          (vector
            [
              (symbol) @vector.symbol
              (string) @vector.string
              (integer) @vector.integer
              (float) @vector.float
              (char) @vector.char
              (list) @vector.list
              (quote) @vector.quote
            ]*) @vector.def
        ]
    """,

    # Hash table patterns
    "hash_table": """
        [
          (hash_table
            [
              (symbol) @hash.key
              (string) @hash.value
              (integer) @hash.value
              (float) @hash.value
              (list) @hash.value
            ]*) @hash.def
        ]
    """,

    # Source file structure
    "source_file": """
        [
          (source_file
            [
              (function_definition) @source.function
              (macro_definition) @source.macro
              (special_form) @source.special
              (list) @source.list
              (comment) @source.comment
            ]*) @source.def
        ]
    """,

    # Value patterns
    "value": """
        [
          (string) @value.string
          (integer) @value.integer
          (float) @value.float
          (char) @value.char
          (symbol) @value.symbol
        ]
    """
} 