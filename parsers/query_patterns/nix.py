"""
Query patterns for Nix files.
"""

from parsers.file_classification import FileType
from .common import COMMON_PATTERNS

NIX_PATTERNS = {
    **COMMON_PATTERNS,
    
    "syntax": {
        "function": {
            "pattern": """
            [
                (function_expression
                    params: (formals) @syntax.function.params
                    body: (_) @syntax.function.body) @syntax.function.def,
                (lambda
                    params: (formals) @syntax.function.lambda.params
                    body: (_) @syntax.function.lambda.body) @syntax.function.lambda
            ]
            """
        },
        "conditional": {
            "pattern": """
            (if_expression
                condition: (_) @syntax.conditional.if.condition
                consequence: (_) @syntax.conditional.if.body
                alternative: (_)? @syntax.conditional.if.else) @syntax.conditional.if
            """
        },
        "let": {
            "pattern": """
            [
                (let_expression
                    body: (_) @syntax.let.body) @syntax.let.def,
                (let_attrset_expression
                    bindings: (binding_set) @syntax.let.attrs.bindings) @syntax.let.attrs
            ]
            """
        }
    },

    "semantics": {
        "variable": {
            "pattern": """
            [
                (binding
                    attrpath: (attrpath) @semantics.variable.name
                    expression: (_) @semantics.variable.value) @semantics.variable.def,
                (inherit
                    attrs: (inherited_attrs) @semantics.variable.inherit.attrs) @semantics.variable.inherit,
                (inherit_from
                    expression: (_) @semantics.variable.inherit.from.expr
                    attrs: (inherited_attrs) @semantics.variable.inherit.from.attrs) @semantics.variable.inherit.from
            ]
            """
        },
        "expression": {
            "pattern": """
            [
                (binary_expression
                    left: (_) @semantics.expression.binary.left
                    operator: _ @semantics.expression.binary.op
                    right: (_) @semantics.expression.binary.right) @semantics.expression.binary,
                (unary_expression
                    operator: _ @semantics.expression.unary.op
                    argument: (_) @semantics.expression.unary.arg) @semantics.expression.unary
            ]
            """
        }
    },

    "structure": {
        "namespace": {
            "pattern": """
            [
                (attrset_expression
                    bindings: (binding_set) @structure.namespace.attrs) @structure.namespace.def,
                (rec_attrset_expression
                    bindings: (binding_set) @structure.namespace.rec.attrs) @structure.namespace.rec
            ]
            """
        },
        "import": {
            "pattern": """
            [
                (import_expression
                    path: (_) @structure.import.path) @structure.import.def,
                (with_expression
                    environment: (_) @structure.with.env
                    body: (_) @structure.with.body) @structure.with
            ]
            """
        }
    },

    "documentation": {
        "comment": {
            "pattern": """
            (comment) @documentation.comment
            """
        }
    }
} 