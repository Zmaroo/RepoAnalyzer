"""Tree-sitter patterns for Groovy programming language."""

GROOVY_PATTERNS = {
    # Basic pattern for function detection
    "function": """
        [
          (method_declaration)
          (closure_expression)
        ] @function
    """,
    # Extended pattern for detailed function information
    "function_details": """
        [
          (method_declaration
             name: (identifier) @function.name
             parameters: (parameter_list)? @function.params
            body: (block) @function.body) @function.def,
          (closure_expression
             parameters: (parameter_list)? @function.params
            body: (block) @function.body) @function.def
        ]
    """
} 