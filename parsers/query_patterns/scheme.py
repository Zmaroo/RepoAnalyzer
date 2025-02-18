"""
Query patterns for Scheme files.
"""

SCHEME_PATTERNS = {
    "syntax": {
        "function": [
            """
            (list_lit
                .
                (sym_lit) @def_type
                (#match? @def_type "^(define|lambda)$")
                .
                (sym_lit) @name
                .
                (list_lit)? @params
                .
                (_)* @body) @function
            """
        ]
    },
    "structure": {
        "namespace": [
            """
            (list_lit
                .
                (sym_lit) @def_type
                (#match? @def_type "^(library|module)$")
                .
                (list_lit) @name
                .
                (_)* @body) @namespace
            """
        ],
        "import": [
            """
            (list_lit
                .
                (sym_lit) @def_type
                (#match? @def_type "^(import)$")
                .
                (_)* @imports) @import
            """
        ]
    },
    "semantics": {
        "variable": [
            """
            (list_lit
                .
                (sym_lit) @def_type
                (#match? @def_type "^(define)$")
                .
                (sym_lit) @name
                .
                (_) @value) @variable
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