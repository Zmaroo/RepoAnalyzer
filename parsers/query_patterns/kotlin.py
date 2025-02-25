"""Kotlin-specific Tree-sitter patterns."""

from parsers.types import FileType
from .common import COMMON_PATTERNS

KOTLIN_PATTERNS = {
    **COMMON_PATTERNS,
    
    "syntax": {
        "function": {
            "pattern": """
            [
                (function_declaration
                    modifiers: [(public) (private) (protected) (internal) (override) (suspend) (inline) (tailrec)]* @syntax.function.modifier
                    name: (simple_identifier) @syntax.function.name
                    type_parameters: (type_parameters)? @syntax.function.type_params
                    value_parameters: (value_parameters)? @syntax.function.params
                    type: (type_reference)? @syntax.function.return_type
                    body: [(block) (expression)]? @syntax.function.body) @syntax.function.def,
                    
                (getter
                    modifiers: [(public) (private) (protected) (internal)]* @syntax.function.getter.modifier
                    body: [(block) (expression)]? @syntax.function.getter.body) @syntax.function.getter,
                    
                (setter
                    modifiers: [(public) (private) (protected) (internal)]* @syntax.function.setter.modifier
                    parameter: (parameter)? @syntax.function.setter.param
                    body: [(block) (expression)]? @syntax.function.setter.body) @syntax.function.setter
            ]
            """
        },
        "class": {
            "pattern": """
            (class_declaration
                modifiers: [(public) (private) (protected) (internal) (abstract) (final) (sealed) (inner) (data)]* @syntax.class.modifier
                name: (type_identifier) @syntax.class.name
                type_parameters: (type_parameters)? @syntax.class.type_params
                primary_constructor: (class_parameters)? @syntax.class.constructor
                delegation_specifiers: (delegation_specifiers)? @syntax.class.delegation
                body: (class_body)? @syntax.class.body) @syntax.class.def
            """
        },
        "interface": {
            "pattern": """
            (interface_declaration
                modifiers: [(public) (private) (protected) (internal)]* @syntax.interface.modifier
                name: (type_identifier) @syntax.interface.name
                type_parameters: (type_parameters)? @syntax.interface.type_params
                delegation_specifiers: (delegation_specifiers)? @syntax.interface.extends
                body: (class_body)? @syntax.interface.body) @syntax.interface.def
            """
        }
    },

    "semantics": {
        "type": {
            "pattern": """
            [
                (type_alias
                    modifiers: [(public) (private) (protected) (internal)]* @semantics.type.alias.modifier
                    name: (type_identifier) @semantics.type.alias.name
                    type_parameters: (type_parameters)? @semantics.type.alias.params
                    type: (type_reference) @semantics.type.alias.value) @semantics.type.alias,
                    
                (type_constraint
                    annotation: (annotation)* @semantics.type.constraint.annotation
                    type: (type_reference) @semantics.type.constraint.type) @semantics.type.constraint
            ]
            """
        }
    },

    "documentation": {
        "comment": {
            "pattern": """
            [
                (comment) @documentation.comment,
                (kdoc
                    content: (_) @documentation.kdoc.content
                    tag: (kdoc_tag)* @documentation.kdoc.tag) @documentation.kdoc
            ]
            """
        }
    },

    "structure": {
        "package": {
            "pattern": """
            (package_header
                identifier: (identifier) @structure.package.name) @structure.package.def
            """
        },
        "import": {
            "pattern": """
            (import_header
                identifier: (identifier) @structure.import.path
                alias: (import_alias)? @structure.import.alias) @structure.import.def
            """
        }
    }
} 