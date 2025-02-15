"""Pascal-specific Tree-sitter patterns.

These queries take advantage of the node types provided by the tree-sitter pascal language pack.
"""

PASCAL_PATTERNS = {
    "function": """
        [
            (procedure_declaration) @function,
            (function_declaration) @function
        ]
    """,
    
    "function_details": """
        [
            (procedure_declaration
                name: (identifier) @function.name
                parameters: (parameter_list) @function.params
                body: (block) @function.body) @function.def,
            (function_declaration
                name: (identifier) @function.name
                parameters: (parameter_list) @function.params
                body: (block) @function.body) @function.def
        ]
    """
} 