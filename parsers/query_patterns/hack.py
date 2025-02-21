"""Query patterns for Hack files."""

from parsers.file_classification import FileType
from .common import COMMON_PATTERNS

HACK_PATTERNS = {
    **COMMON_PATTERNS,
    
    "syntax": {
        "function": {
            "pattern": """
            [
                (function_declaration
                    name: (identifier) @syntax.function.name
                    parameters: (parameter_list) @syntax.function.params
                    body: (compound_statement) @syntax.function.body) @syntax.function.def,
                (method_declaration
                    name: (identifier) @syntax.function.method.name
                    parameters: (parameter_list) @syntax.function.method.params
                    body: (compound_statement) @syntax.function.method.body) @syntax.function.method
            ]
            """
        },
        "class": {
            "pattern": """
            [
                (class_declaration
                    name: (identifier) @syntax.class.name
                    body: (member_declarations) @syntax.class.body) @syntax.class.def,
                (trait_declaration
                    name: (identifier) @syntax.trait.name
                    body: (member_declarations) @syntax.trait.body) @syntax.trait.def
            ]
            """
        },
        "interface": {
            "pattern": """
            (interface_declaration
                name: (identifier) @syntax.interface.name
                body: (member_declarations) @syntax.interface.body) @syntax.interface.def
            """
        },
        "enum": {
            "pattern": """
            [
                (enum_declaration
                    name: (identifier) @syntax.enum.name
                    body: (enum_members) @syntax.enum.body) @syntax.enum.def,
                (enum_class_declaration
                    name: (identifier) @syntax.enum.class.name
                    body: (member_declarations) @syntax.enum.class.body) @syntax.enum.class.def
            ]
            """
        },
        "typedef": {
            "pattern": """
            (alias_declaration
                name: (identifier) @syntax.typedef.name
                type: (_) @syntax.typedef.type) @syntax.typedef.def
            """
        }
    },

    "semantics": {
        "variable": {
            "pattern": """
            [
                (property_declaration
                    type: (_)? @semantics.variable.type
                    value: (_)? @semantics.variable.value) @semantics.variable.property,
                (variable_declaration
                    name: (_) @semantics.variable.name
                    value: (_)? @semantics.variable.value) @semantics.variable.def
            ]
            """
        },
        "expression": {
            "pattern": """
            [
                (call_expression
                    function: (_) @semantics.expression.name
                    arguments: (_)? @semantics.expression.args) @semantics.expression.call,
                (binary_expression
                    left: (_) @semantics.expression.binary.left
                    right: (_) @semantics.expression.binary.right) @semantics.expression.binary
            ]
            """
        }
    },

    "documentation": {
        "comment": {
            "pattern": """
            [
                (comment) @documentation.comment,
                (doc_comment) @documentation.comment.doc
            ]
            """
        }
    },

    "structure": {
        "namespace": {
            "pattern": """
            (namespace_declaration
                name: (_) @structure.namespace.name) @structure.namespace.def
            """
        },
        "import": {
            "pattern": """
            [
                (use_declaration
                    clauses: (_) @structure.import.clauses) @structure.import.use,
                (require_clause
                    path: (_) @structure.import.path) @structure.import.require
            ]
            """
        }
    }
} 