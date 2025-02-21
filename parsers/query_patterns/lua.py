"""Lua-specific Tree-sitter patterns."""

from parsers.file_classification import FileType
from .common import COMMON_PATTERNS

LUA_PATTERNS = {
    **COMMON_PATTERNS,
    
    "syntax": {
        "function": {
            "pattern": """
            [
                (function_declaration
                    name: [(identifier) @syntax.function.name
                          (dot_index_expression
                            table: (identifier) @syntax.function.table
                            field: (identifier) @syntax.function.field)
                          (method_index_expression
                            table: (identifier) @syntax.function.class
                            method: (identifier) @syntax.function.method)]
                    parameters: (parameters) @syntax.function.params
                    body: (block) @syntax.function.body) @syntax.function.def,
                (local_function
                    name: (identifier) @syntax.function.local.name
                    parameters: (parameters) @syntax.function.local.params
                    body: (block) @syntax.function.local.body) @syntax.function.local
            ]
            """
        },
        "class": {
            "pattern": """
            (assignment_statement
                variables: (variable_list
                    (identifier) @syntax.class.name)
                values: (expression_list
                    (table_constructor
                        [(field
                            name: (identifier) @syntax.class.method.name
                            value: (function_definition) @syntax.class.method.def)
                         (field
                            name: (identifier) @syntax.class.field.name
                            value: (_) @syntax.class.field.value)]*) @syntax.class.body)) @syntax.class.def
            """
        }
    },

    "semantics": {
        "variable": {
            "pattern": """
            [
                (assignment_statement
                    variables: (variable_list
                        (identifier) @semantics.variable.name)
                    values: (expression_list
                        (_) @semantics.variable.value)) @semantics.variable.def,
                (local_variable_declaration
                    name: (identifier) @semantics.variable.local.name
                    value: (_)? @semantics.variable.local.value) @semantics.variable.local
            ]
            """
        },
        "type": {
            "pattern": """
            (type_declaration
                name: (identifier) @semantics.type.name
                value: (_) @semantics.type.value) @semantics.type.def
            """
        }
    },

    "documentation": {
        "comment": {
            "pattern": """
            [
                (comment) @documentation.comment,
                (comment) @documentation.luadoc {
                    match: "^---"
                },
                (comment) @documentation.luadoc.tag {
                    match: "@[a-zA-Z]+"
                }
            ]
            """
        }
    },

    "structure": {
        "module": {
            "pattern": """
            [
                (assignment_statement
                    variables: (variable_list
                        (identifier) @structure.module.name)
                    values: (expression_list
                        (table_constructor) @structure.module.exports)) @structure.module,
                (function_call
                    prefix: (identifier) @structure.require.func
                    (#match? @structure.require.func "^require$")
                    arguments: (arguments
                        (string) @structure.require.path)) @structure.require
            ]
            """
        }
    }
} 