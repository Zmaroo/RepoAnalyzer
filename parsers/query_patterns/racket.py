"""Tree-sitter patterns for Racket programming language."""

RACKET_PATTERNS = {
    # Basic pattern for function detection
    "function": """
        [
          (definition)
          (lambda_expression)
        ] @function
    """,
    # Extended pattern for detailed function information
    "function_details": """
        [
          (definition
             name: (identifier) @function.name
            body: (expression) @function.body) @function.def,
          (lambda_expression
             parameters: (list) @function.params
            body: (expression) @function.body) @function.def
        ]
    """
} 