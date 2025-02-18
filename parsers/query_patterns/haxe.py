"""Haxe-specific Tree-sitter patterns.

This file provides basic queries for detecting function and class declarations
(as well as interfaces, typedefs, and variables) using the node types defined in
node-types/haxe-node-types.json. The queries capture key elements like the identifier,
parameter list, block body, etc.
"""

HAXE_PATTERNS = {
    # Basic pattern for function detection.
    "function": r"""
        (function_declaration) @function
    """,

    # Extended pattern for detailed function information:
    # Captures the function name, parameters (if available), and body.
    "function_details": r"""
        (function_declaration
            name: (identifier) @function.name
            parameters: (parameter_list)? @function.params
            body: (block)? @function.body) @function.def
    """,

    # Pattern for class declarations.
    "class": r"""
        (class_declaration
            name: (identifier) @class.name
            body: (class_body)? @class.body) @class.def
    """,

    # Pattern for interface declarations.
    "interface": r"""
        (interface_declaration
            name: (identifier) @interface.name
            body: (interface_body)? @interface.body) @interface.def
    """,

    # Pattern for typedef declarations.
    "typedef": r"""
        (typedef_declaration
            name: (identifier) @typedef.name
            type: (type)? @typedef.type) @typedef.def
    """,

    # Pattern for variable declarations.
    "variable": r"""
        (variable_declaration
            name: (identifier) @variable.name
            initializer: (expression)? @variable.value) @variable.def
    """
} 