"""Elm-specific Tree-sitter patterns.

This module defines basic queries for capturing Elm constructs such as module declarations,
value declarations, type aliases, and union types.
"""

ELM_PATTERNS = {
    # Syntax patterns
    "function": """
        [
          (value_declaration
            pattern: (lower_pattern) @function.name
            type_annotation: (type_annotation)? @function.type
            value: (value_expr) @function.body) @function.def,
          (port_annotation
            name: (lower_name) @function.name
            type_expression: (_) @function.type) @function.port,
          (port_declaration
            name: (lower_name) @function.name
            type_expression: (_) @function.type) @function.port_def
        ]
    """,
    
    "class": [
        """
        (type_declaration
            name: (upper_case_identifier) @name
            type_variables: (lower_pattern)* @type_vars
            constructors: (union_variant)+ @constructors) @class
        """,
        """
        (type_alias_declaration
            name: (upper_case_identifier) @name
            type_variables: (lower_pattern)* @type_vars
            type_expression: (_) @type) @class
        """
    ],
    
    # Structure patterns
    "namespace": [
        """
        (module_declaration
            name: (upper_case_qid) @name
            exposing: (exposed_values)? @exports) @namespace
        """,
        """
        (effect_module_declaration
            name: (upper_case_qid) @name
            exposing: (exposed_values)? @exports) @namespace
        """
    ],
    
    "import": [
        """
        (import_declaration
            module_name: (upper_case_qid) @module
            as_name: (upper_case_identifier)? @alias
            exposing: (exposed_values)? @exposed) @import
        """
    ],
    
    # Semantics patterns
    "variable": [
        """
        (lower_pattern) @variable
        """,
        """
        (record_pattern
            fields: (lower_pattern)+ @fields) @variable
        """,
        """
        (record_type
            name: (lower_name) @name
            fields: (field_type)+ @fields) @variable
        """
    ],
    
    "expression": [
        """
        (call_expr
            target: (_) @function
            arguments: (_)+ @args) @expression
        """,
        """
        (operator_expr
            operator: (_) @operator
            left: (_) @left
            right: (_) @right) @expression
        """,
        """
        (if_else_expr
            if: (_) @condition
            then: (_) @then
            else: (_) @else) @expression
        """,
        """
        (case_of_expr
            expr: (_) @value
            branches: (case_of_branch)+ @branches) @expression
        """,
        """
        (let_in_expr
            declarations: (value_declaration)+ @declarations
            expression: (_) @body) @expression
        """
    ],
    
    # Documentation patterns
    "documentation": """
        [
          (block_comment) @doc.block,
          (line_comment) @doc.line,
          (block_comment
            content: (_) @doc.content
            (#match? @doc.content "^\\|\\s*@docs")) @doc.api
        ]
    """,
    
    "comment": [
        """
        (block_comment) @comment
        """,
        """
        (line_comment) @comment
        """
    ]
}

# Additional metadata for pattern categories
PATTERN_METADATA = {
    "syntax": {
        "function": {
            "contains": ["type", "body"],
            "contained_by": ["namespace"]
        },
        "class": {
            "contains": ["type_vars", "constructors", "type"],
            "contained_by": ["namespace"]
        }
    },
    "structure": {
        "namespace": {
            "contains": ["exports", "function", "class", "variable"],
            "contained_by": []
        },
        "import": {
            "contains": ["exposed"],
            "contained_by": ["namespace"]
        }
    },
    "semantics": {
        "variable": {
            "contains": ["fields"],
            "contained_by": ["function", "expression"]
        },
        "expression": {
            "contains": ["args", "condition", "then", "else", "branches", "declarations"],
            "contained_by": ["function", "let_in_expr"]
        }
    },
    "documentation": {
        "docstring": {
            "contains": [],
            "contained_by": ["function", "class", "namespace"]
        },
        "comment": {
            "contains": [],
            "contained_by": ["function", "class", "namespace", "expression"]
        }
    }
} 