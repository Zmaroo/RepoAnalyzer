"""Query patterns for gitignore files."""

from parsers.file_classification import FileType
from .common import COMMON_PATTERNS

GITIGNORE_PATTERNS = {
    **COMMON_PATTERNS,
    
    "syntax": {
        "pattern": {
            "pattern": """
            (pattern
                directory_flag: (_)? @syntax.pattern.directory
                relative_flag: (_)? @syntax.pattern.relative
                [
                    (pattern_char) @syntax.pattern.char
                    (pattern_char_escaped) @syntax.pattern.char_escaped
                    (wildcard_char_single) @syntax.pattern.wildcard_single
                    (wildcard_chars) @syntax.pattern.wildcard
                    (wildcard_chars_allow_slash) @syntax.pattern.wildcard_slash
                    (bracket_expr) @syntax.pattern.bracket
                    (negation) @syntax.pattern.negation
                ]*) @syntax.pattern.def
            """
        }
    },

    "structure": {
        "document": {
            "pattern": """
            (document
                [
                    (pattern) @structure.document.pattern
                    (comment) @structure.document.comment
                ]*) @structure.document.def
            """
        }
    },

    "documentation": {
        "comment": {
            "pattern": "(comment) @documentation.comment"
        }
    }
} 