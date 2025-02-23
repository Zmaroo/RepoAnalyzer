"""Elm-specific Tree-sitter patterns.

This module defines basic queries for capturing Elm constructs such as module declarations,
value declarations, type aliases, and union types.
"""

from parsers.types import FileType
from .common import COMMON_PATTERNS

ELM_PATTERNS = {
    **COMMON_PATTERNS,
    
    "syntax": {
        "function": {
            "pattern": """
            (value_declaration
              pattern: (lower_pattern) @syntax.function.name
              type_annotation: (type_annotation)? @syntax.function.type
              value: (value_expr) @syntax.function.body) @syntax.function.def
            """,
            "extract": lambda node: {
                "name": node["captures"].get("syntax.function.name", {}).get("text", ""),
                "type": "function"
            }
        },
        "class": {
            "pattern": """
            [
                (type_declaration
                    name: (upper_case_identifier) @syntax.class.name
                    type_variables: (lower_pattern)* @syntax.class.type_vars
                    constructors: (union_variant)+ @syntax.class.constructors) @syntax.class.def,
                (type_alias_declaration
                    name: (upper_case_identifier) @syntax.class.name
                    type_variables: (lower_pattern)* @syntax.class.type_vars
                    type_expression: (_) @syntax.class.type) @syntax.class.def
            ]
            """
        }
    },

    "semantics": {
        "type": {
            "pattern": """
            [
                (type_annotation
                    name: (_) @semantics.type.name
                    expression: (_) @semantics.type.expr) @semantics.type.def,
                (type_variable
                    name: (lower_case_identifier) @semantics.type.var) @semantics.type.def
            ]
            """
        },
        "variable": {
            "pattern": """
            [
                (lower_pattern) @semantics.variable,
                (record_pattern
                    fields: (lower_pattern)+ @semantics.variable.fields) @semantics.variable.def
            ]
            """
        }
    },

    "documentation": {
        "comment": {
            "pattern": """
            [
                (line_comment) @documentation.comment.line,
                (block_comment) @documentation.comment.block
            ]
            """
        },
        "docstring": {
            "pattern": """
            (block_comment
                content: (_) @documentation.docstring.content
                (#match? @documentation.docstring.content "^\\|\\s*@docs")) @documentation.docstring.def
            """
        }
    },

    "structure": {
        "module": {
            "pattern": """
            (module_declaration
                name: (upper_case_qid) @structure.module.name
                exposing: (exposed_values)? @structure.module.exports) @structure.module.def
            """
        },
        "import": {
            "pattern": """
            (import_declaration
                module_name: (upper_case_qid) @structure.import.module
                as_name: (upper_case_identifier)? @structure.import.alias
                exposing: (exposed_values)? @structure.import.exposed) @structure.import.def
            """
        }
    }
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