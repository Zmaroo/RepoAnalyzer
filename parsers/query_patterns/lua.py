"""Tree-sitter patterns for Lua programming language."""

LUA_PATTERNS = {
    # Basic pattern for function detection
    "function": """
        [
          (function_declaration)
          (local_function)
        ] @function
    """,
    # Extended pattern for detailed function information
    "function_details": """
        [
          (function_declaration
             name: (identifier)? @function.name
             parameters: (parameter_list)? @function.params
            body: (block) @function.body) @function.def,
          (local_function
             name: (identifier) @function.name
             parameters: (parameter_list)? @function.params
            body: (block) @function.body) @function.def
        ]
    """
} 