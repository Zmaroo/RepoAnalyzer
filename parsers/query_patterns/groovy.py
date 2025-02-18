"""Query patterns for Groovy files."""

GROOVY_PATTERNS = {
    "syntax": {
        "function": [
            """
            (method_declaration
                name: (identifier) @function.name
                parameters: (parameter_list)? @params
                body: (block) @body) @function
            """,
            """
            (closure_expression
                parameters: (parameter_list)? @params
                body: (block) @body) @function
            """
        ]
    },
    "structure": {
        "namespace": [
            """
            (class_declaration
                name: (identifier) @class.name
                body: (class_body) @class.body) @namespace
            """
        ]
    },
    "semantics": {
        "variable": [
            """
            (variable_declaration
                name: (identifier) @name
                value: (_)? @value) @variable
            """
        ],
        "expression": [
            """
            (method_call
                name: (identifier) @method.name
                arguments: (argument_list)? @method.args) @expression
            """
        ]
    },
    "documentation": {
        "comment": [
            """
            [(line_comment) (block_comment)] @comment
            """
        ]
    }
} 