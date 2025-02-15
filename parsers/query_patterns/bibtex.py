"""BibTeX-specific Tree-sitter patterns."""

BIBTEX_PATTERNS = {
    # Entry patterns (like @article, @book, etc.)
    "entry": """
        [
          (entry
            ty: (entry_type) @entry.type
            key: [
              (key_brace) @entry.key.brace
              (key_paren) @entry.key.paren
            ]
            field: (field)* @entry.fields) @entry.def
        ]
    """,

    # Field patterns (like author, title, year)
    "field": """
        [
          (field
            name: (identifier) @field.name
            value: (value
              (token
                [
                  (identifier) @field.value.identifier
                  (number) @field.value.number
                  (brace_word) @field.value.brace
                  (quote_word) @field.value.quote
                  (command) @field.value.command
                ]*) @field.value.token) @field.value) @field.def
        ]
    """,

    # String definition patterns
    "string": """
        [
          (string
            ty: (string_type) @string.type
            name: (identifier) @string.name
            value: (value) @string.value) @string.def
        ]
    """,

    # Preamble patterns
    "preamble": """
        [
          (preamble
            ty: (preamble_type) @preamble.type
            value: (value) @preamble.value) @preamble.def
        ]
    """,

    # Command patterns (like \textbf, \emph)
    "command": """
        [
          (command
            name: (command_name) @command.name
            [
              (brace_word) @command.arg.brace
              (quote_word) @command.arg.quote
              (command) @command.arg.nested
            ]*) @command.def
        ]
    """,

    # Document structure
    "document": """
        [
          (document
            [
              (entry) @doc.entry
              (string) @doc.string
              (preamble) @doc.preamble
              (comment) @doc.comment
              (junk) @doc.junk
            ]*) @doc.def
        ]
    """,

    # Comment patterns
    "comment": """
        [
          (comment) @comment
        ]
    """
} 