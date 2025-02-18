"""Query patterns for Common Lisp files."""

COMMONLISP_PATTERNS = {
    "syntax": {
        "function": [
            """
            (list
                (symbol) @def_keyword
                (symbol) @function.name
                (list) @function.params
                (_)* @function.body) @function.def
            (#eq? @def_keyword "defun")
            """,
            """
            (list
                (symbol) @lambda_keyword
                (list) @function.params
                (_)* @function.body) @function.def
            (#eq? @lambda_keyword "lambda")
            """
        ]
    },
    "semantics": {
        "expression": [
            """
            (list
                (symbol) @_kw) @expression
            (#match? @_kw "^(defun|lambda)$")
            """
        ]
    }
} 