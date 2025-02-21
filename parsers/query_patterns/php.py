"""Query patterns for PHP files."""

from .common import COMMON_PATTERNS

PHP_PATTERNS = {
    **COMMON_PATTERNS,
    
    "syntax": {
        "function": {
            "pattern": """
            [
                (function_definition
                    name: (name) @syntax.function.name
                    parameters: (formal_parameters) @syntax.function.params
                    body: (compound_statement) @syntax.function.body) @syntax.function.def,
                (method_declaration
                    modifiers: [(public) (private) (protected) (static) (final) (abstract)]* @syntax.method.modifier
                    name: (name) @syntax.method.name
                    parameters: (formal_parameters) @syntax.method.params
                    body: (compound_statement)? @syntax.method.body) @syntax.method.def,
                (arrow_function 
                    parameters: (formal_parameters) @syntax.function.arrow.params
                    body: (_) @syntax.function.arrow.body) @syntax.function.arrow
            ]
            """
        },
        "class": {
            "pattern": """
            [
                (class_declaration
                    modifiers: [(abstract) (final)]* @syntax.class.modifier
                    name: (name) @syntax.class.name
                    base_clause: (base_clause)? @syntax.class.extends
                    interfaces: (class_interface_clause)? @syntax.class.implements
                    body: (declaration_list) @syntax.class.body) @syntax.class.def,
                (interface_declaration
                    name: (name) @syntax.interface.name
                    interfaces: (interface_base_clause)? @syntax.interface.extends
                    body: (declaration_list) @syntax.interface.body) @syntax.interface.def,
                (trait_declaration
                    name: (name) @syntax.trait.name
                    body: (declaration_list) @syntax.trait.body) @syntax.trait.def
            ]
            """
        },
        "attribute": {
            "pattern": """
            [
                (attribute
                    name: (qualified_name) @syntax.attribute.name
                    arguments: (arguments)? @syntax.attribute.args) @syntax.attribute
            ]
            """
        }
    },

    "structure": {
        "namespace": {
            "pattern": """
            [
                (namespace_definition
                    name: (namespace_name)? @structure.namespace.name
                    body: (compound_statement) @structure.namespace.body) @structure.namespace,
                (namespace_use_declaration
                    clauses: (namespace_use_clause
                        name: (qualified_name) @structure.use.name
                        alias: (namespace_aliasing_clause)? @structure.use.alias)*) @structure.use
            ]
            """
        },
        "import": {
            "pattern": """
            [
                (namespace_use_declaration
                    kind: [(function) (const)]? @structure.import.kind
                    clauses: (namespace_use_clause
                        name: (qualified_name) @structure.import.name
                        alias: (namespace_aliasing_clause)? @structure.import.alias)*) @structure.import
            ]
            """
        }
    },

    "documentation": {
        "comment": {
            "pattern": """
            [
                (comment) @documentation.comment,
                (comment) @documentation.phpdoc {
                    match: "^/\\*\\*"
                }
            ]
            """
        }
    }
} 