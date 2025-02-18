"""Query patterns for gitignore files."""

GITIGNORE_PATTERNS = {
    "syntax": {
        "function": [
            """
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
                ]*) @function
            """
        ]
    },
    "structure": {
        "namespace": [
            """
            (file
                [
                    (pattern) @file.pattern
                    (comment) @file.comment
                ]*) @namespace
            """
        ]
    },
    "documentation": {
        "comment": [
            """
            (comment) @comment
            """
        ]
    }
} 