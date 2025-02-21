"""Query patterns for PowerShell files."""

from .common import COMMON_PATTERNS

POWERSHELL_PATTERNS = {
    **COMMON_PATTERNS,
    
    "syntax": {
        "function": {
            "pattern": """
            [
                (function_statement
                    name: (identifier) @syntax.function.name
                    parameters: (param_block)? @syntax.function.params
                    body: (script_block) @syntax.function.body) @syntax.function.def,
                (filter_statement
                    name: (identifier) @syntax.filter.name
                    parameters: (param_block)? @syntax.filter.params
                    body: (script_block) @syntax.filter.body) @syntax.filter.def
            ]
            """
        },
        "class": {
            "pattern": """
            [
                (class_statement
                    name: (identifier) @syntax.class.name
                    base: (base_class)? @syntax.class.base
                    body: (class_body) @syntax.class.body) @syntax.class.def,
                (enum_statement
                    name: (identifier) @syntax.enum.name
                    body: (enum_body) @syntax.enum.body) @syntax.enum.def
            ]
            """
        },
        "conditional": {
            "pattern": """
            [
                (if_statement
                    condition: (pipeline) @syntax.conditional.if.condition
                    consequence: (statement_block) @syntax.conditional.if.body
                    alternative: (else_clause)? @syntax.conditional.if.else) @syntax.conditional.if,
                (switch_statement
                    condition: (switch_condition) @syntax.conditional.switch.expr
                    body: (switch_body) @syntax.conditional.switch.body) @syntax.conditional.switch
            ]
            """
        },
        "loop": {
            "pattern": """
            [
                (foreach_statement
                    iterator: (variable) @syntax.loop.foreach.var
                    collection: (pipeline) @syntax.loop.foreach.collection
                    body: (statement_block) @syntax.loop.foreach.body) @syntax.loop.foreach,
                (while_statement
                    condition: (while_condition) @syntax.loop.while.condition
                    body: (statement_block) @syntax.loop.while.body) @syntax.loop.while,
                (do_statement
                    body: (statement_block) @syntax.loop.do.body
                    condition: (while_condition) @syntax.loop.do.condition) @syntax.loop.do
            ]
            """
        }
    },

    "structure": {
        "pipeline": {
            "pattern": """
            [
                (pipeline
                    (command
                        name: (command_name) @structure.pipeline.cmd.name
                        arguments: (command_elements)? @structure.pipeline.cmd.args) @structure.pipeline.cmd) @structure.pipeline,
                (pipeline
                    (command
                        name: (command_name_expr) @structure.pipeline.expr.name
                        arguments: (command_elements)? @structure.pipeline.expr.args) @structure.pipeline.expr) @structure.pipeline
            ]
            """
        },
        "exception": {
            "pattern": """
            [
                (try_statement
                    body: (statement_block) @structure.exception.try
                    catch: (catch_clauses)? @structure.exception.catch
                    finally: (finally_clause)? @structure.exception.finally) @structure.exception.try,
                (trap_statement
                    type: (type_literal) @structure.exception.trap.type
                    body: (statement_block) @structure.exception.trap.body) @structure.exception.trap
            ]
            """
        }
    },

    "documentation": {
        "comment": {
            "pattern": """
            [
                (comment) @documentation.comment,
                (comment) @documentation.help {
                    match: "^\\.SYNOPSIS|^\\.DESCRIPTION|^\\.PARAMETER|^\\.EXAMPLE|^\\.NOTES"
                }
            ]
            """
        }
    }
} 