"""
Query patterns for Racket files.
"""

RACKET_PATTERNS = {
    "syntax": {
        "function": {
            "pattern": """
            [
                (list_lit
                    .
                    (sym_lit) @def_type
                    (#match? @def_type "^(define|lambda)$")
                    .
                    [(sym_lit) (list_lit)] @syntax.function.name
                    .
                    (list_lit)? @syntax.function.params
                    .
                    (_)* @syntax.function.body) @syntax.function.def
            ]
            """
        },
        "macro": {
            "pattern": """
            [
                (list_lit
                    .
                    (sym_lit) @def_type
                    (#match? @def_type "^(define-syntax|define-syntax-rule)$")
                    .
                    (sym_lit) @syntax.macro.name
                    .
                    (_)* @syntax.macro.body) @syntax.macro.def
            ]
            """
        },
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
        "module": {
            "pattern": """
            [
                (list_lit
                    .
                    (sym_lit) @def_type
                    (#match? @def_type "^(module|module\\*)$")
                    .
                    (sym_lit) @structure.module.name
                    .
                    (sym_lit) @structure.module.lang
                    .
                    (_)* @structure.module.body) @structure.module.def
            ]
            """
        },
        "require": {
            "pattern": """
            (list_lit
                .
                (sym_lit) @def_type
                (#match? @def_type "^(require)$")
                .
                (_)* @structure.require.specs) @structure.require.def
            """
        }
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
        "comment": {
            "pattern": """
            [
                (comment) @documentation.comment,
                (block_comment) @documentation.block_comment,
                (sexp_comment) @documentation.sexp_comment
            ]
            """
        }
    }
} 