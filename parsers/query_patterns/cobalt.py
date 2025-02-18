"""Query patterns for the Cobalt programming language."""

# The following are example patterns for detecting functions in cobalt.
COBALT_PATTERNS = {
    "function": """
        (
            (function_declaration
                name: (identifier) @function.name
                parameters: (parameter_list) @function.params
                return_type: (type_annotation)? @function.return_type
            )
        )
    """,
    
    "class": """
        (
            (class_declaration
                name: (identifier) @class.name
                superclass: (superclass_clause)? @class.superclass
            )
        )
    """,
    
    "variable": """
        (
            (variable_declaration
                kind: (var_or_const) @variable.kind
                name: (identifier) @variable.name
                type: (type_annotation)? @variable.type
                value: (expression)? @variable.value
            )
        )
    """,
    
    "import": """
        (
            (import_declaration
                path: (string_literal) @import.path
                alias: (identifier)? @import.alias
            )
        )
    """,
    
    "comment": """
        (
            (comment) @comment.content
            (#doc_comment) @comment.doc
        )
    """
}

# Additional metadata for pattern categories
PATTERN_METADATA = {
    "syntax": {
        "function": {
            "contains": ["params", "return_type"],
            "contained_by": ["class"]
        },
        "class": {
            "contains": ["superclass"],
            "contained_by": []
        }
    },
    "structure": {
        "import": {
            "contains": [],
            "contained_by": []
        }
    },
    "semantics": {
        "variable": {
            "contains": ["value"],
            "contained_by": ["function"]
        }
    },
    "documentation": {
        "comment": {
            "contains": [],
            "contained_by": ["function"]
        }
    }
} 