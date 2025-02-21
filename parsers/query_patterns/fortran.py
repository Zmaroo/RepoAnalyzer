"""Query patterns for Fortran files."""

from parsers.file_classification import FileType
from .common import COMMON_PATTERNS

FORTRAN_PATTERNS = {
    **COMMON_PATTERNS,
    
    "syntax": {
        "function": {
            "pattern": """
            [
                (function
                    name: (name) @syntax.function.name
                    parameters: (parameter_list)? @syntax.function.params
                    result: (function_result)? @syntax.function.return_type
                    body: (_)* @syntax.function.body) @syntax.function.def,
                (subroutine
                    name: (name) @syntax.function.name
                    parameters: (parameter_list)? @syntax.function.params
                    body: (_)* @syntax.function.body) @syntax.function.def
            ]
            """
        },
        "module": {
            "pattern": """
            [
                (module_statement
                    name: (name) @syntax.module.name) @syntax.module.def,
                (submodule_statement
                    name: (name) @syntax.module.name
                    ancestor: (module_name) @syntax.module.parent) @syntax.module.def
            ]
            """
        }
    },

    "semantics": {
        "variable": {
            "pattern": """
            [
                (variable_declaration
                    type: (_) @semantics.variable.type
                    declarator: [
                        (identifier) @semantics.variable.name
                        (init_declarator
                            name: (identifier) @semantics.variable.name
                            value: (_) @semantics.variable.value)
                    ]) @semantics.variable.def,
                (derived_type_definition
                    name: (name) @semantics.type.name) @semantics.type.def
            ]
            """
        },
        "expression": {
            "pattern": """
            [
                (call_expression
                    name: (_) @semantics.expression.name
                    arguments: (argument_list)? @semantics.expression.args) @semantics.expression.call,
                (arithmetic_if_statement
                    condition: (_) @semantics.expression.condition) @semantics.expression.if
            ]
            """
        }
    },

    "documentation": {
        "comment": {
            "pattern": "(comment) @documentation.comment"
        }
    },

    "structure": {
        "namespace": {
            "pattern": """
            [
                (program
                    body: (_)* @structure.namespace.body) @structure.namespace.program,
                (module
                    body: (_)* @structure.namespace.body) @structure.namespace.module,
                (interface
                    body: (_)* @structure.namespace.body) @structure.namespace.interface
            ]
            """
        },
        "import": {
            "pattern": """
            [
                (import_statement
                    names: (_)* @structure.import.names) @structure.import.def,
                (include_statement
                    path: (_) @structure.import.path) @structure.import.include
            ]
            """
        }
    }
} 