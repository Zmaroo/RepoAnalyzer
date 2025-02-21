"""Query patterns for Groovy files."""

from parsers.file_classification import FileType
from .common import COMMON_PATTERNS

GROOVY_PATTERNS = {
    **COMMON_PATTERNS,
    
    "syntax": {
        "function": {
            "pattern": """
            [
                (method_declaration
                    name: (identifier) @syntax.function.name
                    parameters: (parameter_list)? @syntax.function.params
                    body: (block) @syntax.function.body) @syntax.function.def,
                (closure_expression
                    parameters: (parameter_list)? @syntax.function.closure.params
                    body: (block) @syntax.function.closure.body) @syntax.function.closure
            ]
            """
        },
        "class": {
            "pattern": """
            (class_declaration
                name: (identifier) @syntax.class.name
                body: (class_body) @syntax.class.body) @syntax.class.def
            """
        },
        "interface": {
            "pattern": """
            (interface_declaration
                name: (identifier) @syntax.interface.name
                body: (interface_body) @syntax.interface.body) @syntax.interface.def
            """
        },
        "enum": {
            "pattern": """
            (enum_declaration
                name: (identifier) @syntax.enum.name
                body: (enum_body) @syntax.enum.body) @syntax.enum.def
            """
        },
        "decorator": {
            "pattern": """
            (annotation
                name: (identifier) @syntax.decorator.name
                arguments: (annotation_argument_list)? @syntax.decorator.args) @syntax.decorator.def
            """
        }
    },

    "semantics": {
        "variable": {
            "pattern": """
            [
                (variable_declaration
                    name: (identifier) @semantics.variable.name
                    value: (_)? @semantics.variable.value) @semantics.variable.def,
                (field_declaration
                    name: (identifier) @semantics.variable.field.name
                    value: (_)? @semantics.variable.field.value) @semantics.variable.field
            ]
            """
        },
        "expression": {
            "pattern": """
            [
                (method_call
                    name: (identifier) @semantics.expression.name
                    arguments: (argument_list)? @semantics.expression.args) @semantics.expression.call,
                (property_expression
                    object: (_) @semantics.expression.property.object
                    property: (identifier) @semantics.expression.property.name) @semantics.expression.property
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
        }
    },

    "structure": {
        "package": {
            "pattern": """
            (package_declaration
                name: (_) @structure.package.name) @structure.package.def
            """
        },
        "import": {
            "pattern": """
            (import_declaration
                name: (_) @structure.import.name) @structure.import.def
            """
        }
    }
} 