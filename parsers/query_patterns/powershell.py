"""Tree-sitter patterns for PowerShell programming language."""

POWERSHELL_PATTERNS = {
    # Basic pattern for function detection
    "function": """
        [
          (function_definition)
        ] @function
    """,
    # Extended pattern for detailed function information
    "function_details": """
        [
          (function_definition
             name: (identifier) @function.name
             parameters: (parameter_block)? @function.params
            body: (script_block) @function.body) @function.def
        ]
    """
} 