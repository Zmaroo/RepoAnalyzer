"""Tree-sitter patterns for Squirrel programming language."""

SQUIRREL_PATTERNS = {
    # Basic pattern for function detection
    "function": """
        [
          (function_declaration)
          (anonymous_function)
        ] @function
    """,
    # Extended pattern for detailed function information
    "function_details": """
        [
          (function_declaration
             name: (identifier) @function.name
             parameters: (parameter_list)? @function.params
            body: (block) @function.body) @function.def,
          (anonymous_function
             parameters: (parameter_list)? @function.params
            body: (block) @function.body) @function.def
        ]
    """
} 