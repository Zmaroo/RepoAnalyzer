"""Purescript-specific Tree-sitter patterns.

These queries capture key constructs in Purescript:
  - Module declarations.
  - Value declarations (used for functions).
  - Data declarations.
  - Class declarations.
  
Adjust node names as needed to match your Purescript grammar.
"""

PURESCRIPT_PATTERNS = {
    "module": r"""
        (module_declaration
            name: (module_identifier) @module.name
            exports: (export_list)? @module.exports) @module.def
    """,
    "function": r"""
        (value_declaration) @function
    """,
    "function_details": r"""
        (value_declaration
            name: (lower_identifier) @function.name
            value: (expression)? @function.body) @function.def
    """,
    "data": r"""
        (data_declaration
            name: (upper_identifier) @datatype.name
            constructors: (data_constructor_list)? @datatype.constructors) @datatype.def
    """,
    "class": r"""
        (class_declaration
            name: (upper_identifier) @class.name
            members: (class_member_list)? @class.members) @class.def
    """
}