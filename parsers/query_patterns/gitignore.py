"""Gitignore-specific Tree-sitter patterns."""

GITIGNORE_PATTERNS = {
    # Pattern definitions
    "pattern": """
        [
          (pattern
            directory_flag: (_)? @pattern.directory
            relative_flag: (_)? @pattern.relative
            [
              (pattern_char) @pattern.char
              (pattern_char_escaped) @pattern.char_escaped
              (wildcard_char_single) @pattern.wildcard_single
              (wildcard_chars) @pattern.wildcard
              (wildcard_chars_allow_slash) @pattern.wildcard_slash
              (bracket_expr) @pattern.bracket
              (negation) @pattern.negation
            ]*) @pattern.def
        ]
    """,

    # Bracket expressions
    "bracket": """
        [
          (bracket_expr
            [
              (bracket_char) @bracket.char
              (bracket_char_escaped) @bracket.char_escaped
              (bracket_char_class) @bracket.char_class
              (bracket_range) @bracket.range
              (bracket_negation) @bracket.negation
            ]*) @bracket.def
        ]
    """,

    # Comments
    "comment": """
        [
          (comment) @comment
        ]
    """,

    # Document structure
    "document": """
        [
          (document
            [
              (pattern) @doc.pattern
              (comment) @doc.comment
            ]*) @doc.def
        ]
    """
} 