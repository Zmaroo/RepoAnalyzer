"""
Query patterns for Racket files.
"""

RACKET_PATTERNS = {
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
        ],
        "class": [
            """
            (list_lit
                .
                (sym_lit) @def_type
                (#match? @def_type "^(struct|class)$")
                .
                (sym_lit) @name
                .
                (_)* @fields) @class
            """
        ]
    },
    "structure": {
        "namespace": [
            """
            (list_lit
                .
                (sym_lit) @def_type
                (#match? @def_type "^(module|module\\*)$")
                .
                (sym_lit) @name
                .
                (_)* @body) @namespace
            """
        ],
        "import": [
            """
            (list_lit
                .
                (sym_lit) @def_type
                (#match? @def_type "^(require)$")
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
                (#match? @def_type "^(define-values|define-syntax)$")
                .
                (list_lit) @names
                .
                (_)* @value) @variable
            """
        ]
    },
    "documentation": {
        "docstring": [
            """
            (list_lit
                .
                (sym_lit) @doc_type
                (#match? @doc_type "^(doc|document)$")
                .
                (_)* @content) @docstring
            """
        ],
        "comment": [
            """
            (comment) @comment
            """
        ]
    }
} 