"""Query patterns for Haxe files."""

from parsers.file_classification import FileType
from .common import COMMON_PATTERNS

HAXE_PATTERNS = {
    **COMMON_PATTERNS,
    
    "syntax": {
        "function": {
            "pattern": """
            (function_declaration
                name: (identifier) @syntax.function.name
                parameters: (parameter_list)? @syntax.function.params
                body: (block)? @syntax.function.body) @syntax.function.def
            """
        },
        "class": {
            "pattern": """
            (class_declaration
                name: (identifier) @syntax.class.name
                body: (class_body)? @syntax.class.body) @syntax.class.def
            """
        },
        "interface": {
            "pattern": """
            (interface_declaration
                name: (identifier) @syntax.interface.name
                body: (interface_body)? @syntax.interface.body) @syntax.interface.def
            """
        },
        "typedef": {
            "pattern": """
            (typedef_declaration
                name: (identifier) @syntax.typedef.name
                type: (type)? @syntax.typedef.type) @syntax.typedef.def
            """
        }
    },

    "semantics": {
        "variable": {
            "pattern": """
            (variable_declaration
                name: (identifier) @semantics.variable.name
                initializer: (expression)? @semantics.variable.value) @semantics.variable.def
            """
        },
        "type": {
            "pattern": """
            (type
                name: (identifier) @semantics.type.name) @semantics.type.def
            """
        }
    },

    "documentation": {
        "comment": {
            "pattern": """
            (comment) @documentation.comment
            """
        }
    },

    "structure": {
        "import": {
            "pattern": """
            (import_statement
                package: (package_name)? @structure.import.package
                type: (type_name)? @structure.import.type) @structure.import.def
            """
        },
        "package": {
            "pattern": """
            (package_statement
                name: (package_name) @structure.package.name) @structure.package.def
            """
        }
    }
} 