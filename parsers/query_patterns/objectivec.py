"""Tree-sitter patterns for Objective-C programming language."""

OBJECTIVEC_PATTERNS = {
    # Basic pattern for function detection
    "function": """
        [
          (method_declaration)
        ] @function
    """,
    # Extended pattern for detailed function information
    "function_details": """
        [
          (method_declaration
             receiver: (object)?
             selector: (selector) @function.name
             parameters: (parameter_list)? @function.params
            body: (compound_statement) @function.body) @function.def
        ]
    """
} 