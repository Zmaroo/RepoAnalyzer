"""Tree-sitter patterns for Ada programming language."""

ADA_PATTERNS = {
    # Basic pattern for function detection
    "function": """
        [
          (subprogram_body)
        ] @function
    """,
    # Extended pattern for detailed function information
    "function_details": """
        [
          (subprogram_body
             (procedure_specification
                name: (identifier)? @function.name)
            body: (block) @function.body) @function.def,
          (subprogram_body
             (function_specification
                name: (identifier)? @function.name)
            body: (block) @function.body) @function.def
        ]
    """
} 