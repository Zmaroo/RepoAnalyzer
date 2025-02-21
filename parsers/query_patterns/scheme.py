"""
Query patterns for Scheme files.
"""

SCHEME_PATTERNS = {
    "syntax": {
        "function": {
            "pattern": """
            [
                (list
                    .
                    [(identifier) (symbol)] @def_type
                    (#match? @def_type "^(define|lambda)$")
                    .
                    [(identifier) (symbol)] @syntax.function.name
                    .
                    (list)? @syntax.function.params
                    .
                    (_)* @syntax.function.body) @syntax.function.def,
                
                (list
                    .
                    [(identifier) (symbol)] @def_type
                    (#match? @def_type "^(define-syntax)$")
                    .
                    [(identifier) (symbol)] @syntax.macro.name
                    .
                    (_)* @syntax.macro.body) @syntax.macro.def
            ]
            """
        },
        "quote": {
            "pattern": """
            [
                (quote
                    value: (_) @syntax.quote.value) @syntax.quote.def,
                (quasiquote
                    value: (_) @syntax.quasiquote.value) @syntax.quasiquote.def,
                (unquote
                    value: (_) @syntax.unquote.value) @syntax.unquote.def,
                (unquote_splicing
                    value: (_) @syntax.unquote_splicing.value) @syntax.unquote_splicing.def
            ]
            """
        }
    },
    "structure": {
        "module": {
            "pattern": """
            [
                (list
                    .
                    [(identifier) (symbol)] @def_type
                    (#match? @def_type "^(define-module|module)$")
                    .
                    [(identifier) (symbol)] @structure.module.name
                    .
                    (_)* @structure.module.body) @structure.module.def,
                
                (list
                    .
                    [(identifier) (symbol)] @def_type
                    (#match? @def_type "^(import|use)$")
                    .
                    (_)* @structure.import.modules) @structure.import.def
            ]
            """
        }
    },
    "semantics": {
        "variable": {
            "pattern": """
            [
                (list
                    .
                    [(identifier) (symbol)] @def_type
                    (#match? @def_type "^(define)$")
                    .
                    [(identifier) (symbol)] @semantics.variable.name
                    .
                    (_) @semantics.variable.value) @semantics.variable.def
            ]
            """
        }
    },
    "documentation": {
        "comment": {
            "pattern": """
            [
                (comment) @documentation.comment,
                (block_comment) @documentation.block_comment
            ]
            """
        }
    }
} 