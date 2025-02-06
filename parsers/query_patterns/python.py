"""Tree-sitter patterns for Python programming language."""

PYTHON_PATTERNS = {
    # Basic pattern for function detection
    "function": """
        [
          (function_definition)
          (lambda)
        ] @function
    """,
    # Extended pattern for detailed function information
    "function_details": """
        [
          (function_definition
            name: (identifier) @function.name
            parameters: (parameters) @function.params
            body: (block) @function.body
            [
              (string) @function.docstring
            ]?) @function.def,
          (lambda
            parameters: (lambda_parameters)? @function.params
            body: (_) @function.body) @function.def
        ]
    """,
    # Class patterns
    "class": """
        [
          (class_definition)
        ] @class
    """,
    "class_details": """
        [
          (class_definition
            name: (identifier) @class.name
            [
              (argument_list
                (identifier)* @class.bases)
            ]?
            body: (block
              [
                (string) @class.docstring
                (function_definition)* @class.methods
                (expression_statement
                  (assignment) @class.field)*
              ])) @class.def
        ]
    """,
    # Import patterns
    "import": """
        [
          (import_statement
            name: (dotted_name) @import.module) @import,
          (import_from_statement
            module_name: (dotted_name) @import.from
            name: (dotted_name) @import.name) @import
        ]
    """,
    # Decorator patterns
    "decorator": """
        [
          (decorator
            name: (identifier) @decorator.name
            arguments: (argument_list)? @decorator.args) @decorator
        ]
    """
} 