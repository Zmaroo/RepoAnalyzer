"""
Query patterns for R files.
"""

R_PATTERNS = {
    "syntax": {
        "function": {
            "pattern": """
            [
                (function_definition
                    name: (identifier) @syntax.function.name
                    parameters: (formal_parameters
                        (parameter
                            name: (identifier) @syntax.function.param.name
                            default: (_)? @syntax.function.param.default)*)? @syntax.function.params
                    body: (_) @syntax.function.body) @syntax.function.def
            ]
            """
        },
        "control": {
            "pattern": """
            [
                (if_statement
                    condition: (_) @syntax.control.if.condition
                    consequence: (_) @syntax.control.if.consequence
                    alternative: (_)? @syntax.control.if.alternative) @syntax.control.if,
                
                (for_statement
                    sequence: (_) @syntax.control.for.sequence
                    body: (_) @syntax.control.for.body) @syntax.control.for,
                
                (while_statement
                    condition: (_) @syntax.control.while.condition
                    body: (_) @syntax.control.while.body) @syntax.control.while,
                
                (repeat_statement
                    body: (_) @syntax.control.repeat.body) @syntax.control.repeat
            ]
            """
        }
    },
    "structure": {
        "namespace": {
            "pattern": """
            [
                (namespace_operator
                    lhs: (identifier) @structure.namespace.package
                    operator: "::" @structure.namespace.operator
                    rhs: (identifier) @structure.namespace.symbol) @structure.namespace.def,
                
                (library_call
                    package: (identifier) @structure.namespace.package) @structure.namespace.import
            ]
            """
        },
        "import": [
            """
            (library_call
                package: (identifier) @package) @import
            """,
            """
            (require_call
                package: (string_literal) @package) @import
            """
        ]
    },
    "semantics": {
        "variable": {
            "pattern": """
            [
                (binary_operator
                    operator: ["<-" "=" "<<-"] @semantics.variable.operator
                    lhs: (identifier) @semantics.variable.name
                    rhs: (_) @semantics.variable.value) @semantics.variable.def,
                
                (binary_operator
                    operator: ["->" "->>" "="] @semantics.variable.operator
                    lhs: (_) @semantics.variable.value
                    rhs: (identifier) @semantics.variable.name) @semantics.variable.def
            ]
            """
        },
        "call": {
            "pattern": """
            (call
                function: [(identifier) (namespace_operator)] @semantics.call.function
                arguments: (arguments)? @semantics.call.args) @semantics.call.def
            """
        }
    },
    "documentation": {
        "comment": {
            "pattern": """
            [
                (comment) @documentation.comment,
                (roxygen_comment) @documentation.docstring
            ]
            """
        }
    }
} 