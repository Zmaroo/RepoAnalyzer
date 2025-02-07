"""Tree-sitter patterns for Common Lisp programming language.

This module defines two queries:
- "function" – a basic query that detects lists whose first symbol is either "defun" or "lambda".
- "function_details" – a more detailed query that captures the function name (for defun), parameters, and body.
"""

COMMONLISP_PATTERNS = {
    # Basic pattern for function detection using the first element keyword.
    "function": """
        [
          (list
             (symbol) @_kw) @function
        ]
        (#match? @_kw "^(defun|lambda)$")
    """,
    # Extended pattern for detailed function information.
    "function_details": """
        [
          (list
             (symbol) @def_keyword
             (symbol) @function.name
             (list) @function.params
             (_)* @function.body) @function.def
           (#eq? @def_keyword "defun"),
          (list
             (symbol) @lambda_keyword
             (list) @function.params
             (_)* @function.body) @function.def
           (#eq? @lambda_keyword "lambda")
        ]
    """
} 