"""Query patterns for TCL files."""

TCL_PATTERNS = {
    "syntax": {
        "procedure": {
            "pattern": """
            (procedure
                name: (simple_word) @syntax.procedure.name
                arguments: (arguments) @syntax.procedure.params
                body: (_)* @syntax.procedure.body) @syntax.procedure.def
            """
        },
        "control_flow": {
            "pattern": """
            [
                (conditional
                    condition: (expr) @syntax.if.condition
                    (elseif)* @syntax.if.elseif
                    (else)? @syntax.if.else) @syntax.if.def,
                
                (while
                    condition: (expr) @syntax.while.condition
                    body: (_)* @syntax.while.body) @syntax.while.def,
                
                (foreach
                    (simple_word) @syntax.foreach.var
                    (simple_word) @syntax.foreach.list
                    body: (_)* @syntax.foreach.body) @syntax.foreach.def
            ]
            """
        },
        "namespace": {
            "pattern": """
            (namespace
                (word_list) @syntax.namespace.path) @syntax.namespace.def
            """
        }
    },
    "semantics": {
        "variable": {
            "pattern": """
            [
                (set
                    (simple_word) @semantics.variable.name
                    (_)? @semantics.variable.value) @semantics.variable.def,
                
                (variable_substitution
                    (id) @semantics.variable.ref) @semantics.variable.use
            ]
            """
        },
        "expression": {
            "pattern": """
            [
                (expr_cmd
                    (expr) @semantics.expression.value) @semantics.expression.def,
                
                (unary_expr
                    (_) @semantics.expression.operand) @semantics.expression.unary,
                
                (binop_expr
                    (_) @semantics.expression.left
                    (_) @semantics.expression.right) @semantics.expression.binary
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