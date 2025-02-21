"""Query patterns for Objective-C files."""

from parsers.file_classification import FileType
from .common import COMMON_PATTERNS

OBJECTIVEC_PATTERNS = {
    **COMMON_PATTERNS,
    
    "syntax": {
        "function": {
            "pattern": """
            [
                (function_definition
                    declarator: (function_declarator
                        declarator: (identifier) @syntax.function.name
                        parameters: (parameter_list) @syntax.function.params)
                    body: (compound_statement) @syntax.function.body) @syntax.function.def,
                (method_definition
                    selector: (selector) @syntax.method.name
                    parameters: (parameter_list)? @syntax.method.params
                    body: (compound_statement) @syntax.method.body) @syntax.method.def
            ]
            """
        },
        "class": {
            "pattern": """
            [
                (class_interface
                    name: (identifier) @syntax.class.name
                    superclass: (superclass_reference)? @syntax.class.super
                    protocols: (protocol_reference_list)? @syntax.class.protocols
                    properties: (property_declaration)* @syntax.class.properties
                    methods: (method_declaration)* @syntax.class.methods) @syntax.class.interface,
                (class_implementation
                    name: (identifier) @syntax.class.impl.name
                    superclass: (superclass_reference)? @syntax.class.impl.super
                    ivars: (instance_variables)? @syntax.class.impl.ivars) @syntax.class.implementation
            ]
            """
        },
        "protocol": {
            "pattern": """
            (protocol_declaration
                name: (identifier) @syntax.protocol.name
                protocols: (protocol_reference_list)? @syntax.protocol.protocols
                methods: (method_declaration)* @syntax.protocol.methods) @syntax.protocol.def
            """
        }
    },

    "semantics": {
        "variable": {
            "pattern": """
            [
                (declaration
                    type: (_) @semantics.variable.type
                    declarator: (identifier) @semantics.variable.name) @semantics.variable.def,
                (property_declaration
                    attributes: (property_attributes)? @semantics.property.attrs
                    type: (_) @semantics.property.type
                    name: (identifier) @semantics.property.name) @semantics.property.def
            ]
            """
        },
        "type": {
            "pattern": """
            [
                (type_identifier) @semantics.type.name,
                (protocol_qualifier) @semantics.type.protocol,
                (type_qualifier) @semantics.type.qualifier
            ]
            """
        }
    },

    "documentation": {
        "comment": {
            "pattern": """
            [
                (comment) @documentation.comment,
                (documentation_comment) @documentation.doc
            ]
            """
        }
    },

    "structure": {
        "import": {
            "pattern": """
            [
                (preproc_include
                    path: (system_lib_string) @structure.import.system.path) @structure.import.system,
                (preproc_include
                    path: (string_literal) @structure.import.local.path) @structure.import.local,
                (import_declaration
                    path: (_) @structure.import.framework.path) @structure.import.framework
            ]
            """
        },
        "category": {
            "pattern": """
            [
                (category_interface
                    name: (identifier) @structure.category.class
                    category: (identifier) @structure.category.name) @structure.category.interface,
                (category_implementation
                    name: (identifier) @structure.category.impl.class
                    category: (identifier) @structure.category.impl.name) @structure.category.implementation
            ]
            """
        }
    }
} 