"""Query patterns for Erlang files."""

from parsers.file_classification import FileType
from .common import COMMON_PATTERNS

ERLANG_PATTERNS = {
    **COMMON_PATTERNS,
    
    "syntax": {
        "function": {
            "pattern": """
            [
                (fun_decl
                    clause: (_) @syntax.function.clause) @syntax.function.def,
                (fun_clause
                    name: (_)? @syntax.function.name
                    args: (expr_args) @syntax.function.params
                    guard: (_)? @syntax.function.guard
                    body: (clause_body) @syntax.function.body) @syntax.function.clause
            ]
            """
        },
        "type": {
            "pattern": """
            [
                (type_attribute
                    name: (_) @syntax.type.name
                    args: (_)? @syntax.type.args
                    value: (_) @syntax.type.value) @syntax.type.def,
                (opaque
                    name: (_) @syntax.type.name
                    args: (_)? @syntax.type.args
                    value: (_) @syntax.type.value) @syntax.type.def
            ]
            """
        }
    },

    "semantics": {
        "variable": {
            "pattern": """
            [
                (var) @semantics.variable,
                (record_field
                    name: (_) @semantics.variable.name
                    expr: (_)? @semantics.variable.value) @semantics.variable.def
            ]
            """
        },
        "expression": {
            "pattern": """
            [
                (binary_op_expr
                    lhs: (_) @semantics.expression.left
                    rhs: (_) @semantics.expression.right) @semantics.expression.binary,
                (call
                    expr: (_) @semantics.expression.target
                    args: (_) @semantics.expression.args) @semantics.expression.call
            ]
            """
        }
    },

    "documentation": {
        "comment": {
            "pattern": "(comment) @documentation.comment"
        },
        "docstring": {
            "pattern": """
            (comment 
                (#match? @documentation.comment "^%+\\s*@doc")) @documentation.docstring
            """
        }
    },

    "structure": {
        "module": {
            "pattern": """
            (module_attribute
                name: (_) @structure.module.name) @structure.module.def
            """
        },
        "import": {
            "pattern": """
            [
                (import_attribute
                    module: (_) @structure.import.module
                    functions: (_) @structure.import.functions) @structure.import.def,
                (behaviour_attribute
                    module: (_) @structure.import.module) @structure.import.behaviour
            ]
            """
        }
    }
} 