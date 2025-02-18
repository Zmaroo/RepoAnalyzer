"""Hack-specific Tree-sitter patterns.

This file provides basic queries for detecting functions (both free functions and methods)
and class declarations. The queries rely on node types such as "function_declaration",
"methodish_declaration", "class_declaration", and field names ("name", "parameters", "body")
as defined in node-types/hack-node-types.json.
"""

HACK_PATTERNS = {
    # Basic pattern for function detection (free functions and methods)
    "function": r"""
        [
          (function_declaration) @function,
          (methodish_declaration) @function
        ]
    """,

    # Extended pattern for detailed function definitions:
    # Captures the function name, parameters, and body.
    "function_details": r"""
        [
          (function_declaration
            name: (name) @function.name
            parameters: (parameters) @function.params
            body: (body) @function.body) @function.def,
          (methodish_declaration
            name: (name) @function.name
            parameters: (parameters) @function.params
            body: (body) @function.body) @function.def
        ]
    """,

    # Pattern for class declarations:
    # Captures the class name and its body.
    "class": r"""
        (class_declaration
            name: (name) @class.name
            body: (body) @class.body) @class.def
    """,

    # Optional: Pattern for variable declarations:
    # (Assumes a node type "variable_declaration" with a "name" field and an optional initializer.)
    "variable": r"""
        (variable_declaration
            name: (name) @variable.name
            initializer: (binary_expression)? @variable.value) @variable.def
    """
} 