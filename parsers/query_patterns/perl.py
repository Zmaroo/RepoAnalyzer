"""Tree-sitter patterns for Perl programming language."""

PERL_PATTERNS = {
    # Basic pattern for function detection
    "function": """
        [
          (subroutine_definition)
        ] @function
    """,
    # Extended pattern for detailed function information
    "function_details": """
        [
          (subroutine_definition
             name: (identifier) @function.name
            body: (block) @function.body) @function.def
        ]
    """
} 