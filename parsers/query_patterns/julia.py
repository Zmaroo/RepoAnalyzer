"""
Query patterns for Julia files.
"""

from parsers.file_classification import FileType
from .common import COMMON_PATTERNS

JULIA_PATTERNS = {
    **COMMON_PATTERNS,
    
    "syntax": {
        "function": {
            "pattern": """
            [
                (function_definition
                    name: (identifier) @syntax.function.name
                    parameters: (parameter_list) @syntax.function.params
                    body: (block) @syntax.function.body) @syntax.function.def,
                (short_function_definition
                    name: (identifier) @syntax.function.name
                    parameters: (parameter_list) @syntax.function.params
                    body: (_) @syntax.function.body) @syntax.function.def
            ]
            """
        },
        "struct": {
            "pattern": """
            (struct_definition
                name: (identifier) @syntax.struct.name
                body: (field_list) @syntax.struct.body) @syntax.struct.def
            """
        },
        "module": {
            "pattern": """
            [
                (module_definition
                    name: (identifier) @syntax.module.name
                    body: (block) @syntax.module.body) @syntax.module.def,
                (baremodule_definition
                    name: (identifier) @syntax.module.bare.name
                    body: (block) @syntax.module.bare.body) @syntax.module.bare.def
            ]
            """
        }
    },

    "semantics": {
        "variable": {
            "pattern": """
            [
                (assignment
                    left: (identifier) @semantics.variable.name
                    right: (_) @semantics.variable.value) @semantics.variable.def,
                (const_statement
                    name: (identifier) @semantics.variable.const.name
                    value: (_) @semantics.variable.const.value) @semantics.variable.const
            ]
            """
        },
        "type": {
            "pattern": """
            [
                (type_definition
                    name: (identifier) @semantics.type.name
                    value: (_) @semantics.type.value) @semantics.type.def,
                (primitive_definition
                    type: (type_head) @semantics.type.primitive.head) @semantics.type.primitive
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
            (string_literal) @documentation.docstring {
                match: "^\\"\\"\\""
            }
            """
        }
    },

    "structure": {
        "import": {
            "pattern": """
            [
                (import_statement
                    path: (identifier) @structure.import.path) @structure.import.def,
                (using_statement
                    path: (identifier) @structure.import.using.path) @structure.import.using
            ]
            """
        },
        "export": {
            "pattern": """
            (export_statement
                names: (_) @structure.export.names) @structure.export.def
            """
        }
    }
} 