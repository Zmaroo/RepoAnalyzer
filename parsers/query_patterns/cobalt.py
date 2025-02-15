"""Cobalt-specific Tree-sitter patterns."""

# The following are example patterns for detecting functions in cobalt.
COBALT_PATTERNS = {
    "function": """
        [
            (cobalt_function_declaration) @function
        ]
    """,
    
    "function_details": """
        [
            (cobalt_function_declaration
                name: (identifier) @function.name
                body: (block) @function.body) @function.def
        ]
    """
} 