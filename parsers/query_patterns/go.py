"""Go-specific Tree-sitter patterns."""

from parsers.file_classification import FileType
from .common import COMMON_PATTERNS

GO_PATTERNS = {
    **COMMON_PATTERNS,
    
    "syntax": {
        "function": {
            "pattern": """
            [
                (function_declaration
                    name: (identifier) @syntax.function.name
                    parameters: (parameter_list) @syntax.function.params
                    result: (_)? @syntax.function.return_type
                    body: (block) @syntax.function.body) @syntax.function.def,
                (method_declaration
                    receiver: (parameter_list) @syntax.function.method.receiver
                    name: (identifier) @syntax.function.method.name
                    parameters: (parameter_list) @syntax.function.method.params
                    result: (_)? @syntax.function.method.return_type
                    body: (block) @syntax.function.method.body) @syntax.function.method
            ]
            """
        },
        "type": {
            "pattern": """
            [
                (type_declaration
                    name: (type_identifier) @syntax.type.name
                    type: [(struct_type) (interface_type)] @syntax.type.definition) @syntax.type.def,
                (type_spec
                    name: (type_identifier) @syntax.type.spec.name
                    type: (_) @syntax.type.spec.value) @syntax.type.spec
            ]
            """
        }
    },

    "semantics": {
        "variable": {
            "pattern": """
            [
                (var_declaration
                    name: (_) @semantics.variable.name
                    type: (_)? @semantics.variable.type
                    value: (_)? @semantics.variable.value) @semantics.variable.def,
                (const_declaration
                    name: (_) @semantics.variable.const.name
                    type: (_)? @semantics.variable.const.type
                    value: (_) @semantics.variable.const.value) @semantics.variable.const
            ]
            """
        },
        "concurrency": {
            "pattern": """
            [
                (go_expression
                    expression: (_) @semantics.concurrency.go.expr) @semantics.concurrency.go,
                (channel_type
                    value: (_) @semantics.concurrency.chan.type) @semantics.concurrency.chan,
                (select_statement
                    body: (communication_case)* @semantics.concurrency.select.cases) @semantics.concurrency.select
            ]
            """
        }
    },

    "documentation": {
        "comment": {
            "pattern": """
            [
                (comment) @documentation.comment,
                (comment
                    text: /\\/\\/\\s*[A-Z].*/) @documentation.godoc.line,
                (comment
                    text: /\\/\\*\\s*[A-Z].*?\\*\\/) @documentation.godoc.block
            ]
            """
        }
    },

    "structure": {
        "package": {
            "pattern": """
            [
                (package_clause
                    name: (identifier) @structure.package.name) @structure.package.def,
                (import_declaration
                    specs: (import_spec_list) @structure.import.specs) @structure.import.def
            ]
            """
        }
    }
} 