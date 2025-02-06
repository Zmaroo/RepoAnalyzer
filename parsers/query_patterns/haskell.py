"""Tree-sitter patterns for Haskell programming language."""

HASKELL_PATTERNS = {
    # Basic pattern for function detection
    "function": """
        [
          (function_declaration)
          (lambda_expression)
        ] @function
    """,
    # Extended pattern for detailed function information
    "function_details": """
        [
          (function_declaration
             name: (identifier) @function.name
             parameters: (parameter_list)? @function.params
            body: (expression) @function.body) @function.def,
          (lambda_expression
             parameters: (parameter_list)? @function.params
            body: (expression) @function.body) @function.def
        ]
    """,
    "import": """
        (import_declaration 
            module: (module_name) @import.name) @import
    """
} 