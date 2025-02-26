"""Shell-specific Tree-sitter patterns."""

from parsers.file_classification import FileType
from .common import COMMON_PATTERNS

SHELL_PATTERNS_FOR_LEARNING = {
    "command_structures": {
        "pattern": """
        [
            (pipeline
                (command
                    name: (command_name) @cmd.pipe.name) @cmd.pipe.command
                (command
                    name: (command_name) @cmd.pipe.next_name) @cmd.pipe.next_command) @cmd.pipe,
                
            (command
                name: (command_name) @cmd.redirect.name
                (_)*
                (redirections) @cmd.redirect.redirs) @cmd.redirect,
                
            (subshell
                (command_substitution) @cmd.subshell.command_sub) @cmd.subshell,
                
            (if_statement
                condition: (_) @cmd.if.condition
                consequence: (_) @cmd.if.then
                alternative: (_)? @cmd.if.else) @cmd.if
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "command_structures",
            "is_pipeline": "cmd.pipe" in node["captures"],
            "is_redirection": "cmd.redirect" in node["captures"],
            "is_subshell": "cmd.subshell" in node["captures"],
            "is_conditional": "cmd.if" in node["captures"],
            "command_name": (
                node["captures"].get("cmd.pipe.name", {}).get("text", "") or
                node["captures"].get("cmd.redirect.name", {}).get("text", "")
            ),
            "command_structure": (
                "pipeline" if "cmd.pipe" in node["captures"] else
                "redirection" if "cmd.redirect" in node["captures"] else
                "subshell" if "cmd.subshell" in node["captures"] else
                "conditional" if "cmd.if" in node["captures"] else
                "unknown"
            )
        }
    },
    
    "scripting_patterns": {
        "pattern": """
        [
            (function_definition
                name: (word) @script.func.name
                body: (compound_statement) @script.func.body) @script.func,
                
            (for_statement
                variable: (variable_name) @script.for.var
                value: (_) @script.for.values
                body: (do_group) @script.for.body) @script.for,
                
            (while_statement
                condition: (_) @script.while.cond
                body: (do_group) @script.while.body) @script.while,
                
            (case_statement
                value: (_) @script.case.value
                cases: (case_item
                    pattern: (_) @script.case.pattern
                    body: (_) @script.case.body)*) @script.case
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "scripting_patterns",
            "is_function_def": "script.func" in node["captures"],
            "is_for_loop": "script.for" in node["captures"],
            "is_while_loop": "script.while" in node["captures"],
            "is_case_statement": "script.case" in node["captures"],
            "function_name": node["captures"].get("script.func.name", {}).get("text", ""),
            "loop_variable": node["captures"].get("script.for.var", {}).get("text", ""),
            "script_structure": (
                "function_definition" if "script.func" in node["captures"] else
                "for_loop" if "script.for" in node["captures"] else
                "while_loop" if "script.while" in node["captures"] else
                "case_statement" if "script.case" in node["captures"] else
                "unknown"
            )
        }
    },
    
    "variable_usage": {
        "pattern": """
        [
            (variable_assignment
                name: (variable_name) @var.assign.name
                value: (_) @var.assign.value) @var.assign,
                
            (expansion
                [
                    (variable_name) @var.expand.name
                    (subscript
                        name: (variable_name) @var.expand.array_name
                        index: (_) @var.expand.index)
                ]) @var.expand,
                
            (command_substitution
                (command
                    name: (command_name) @var.cmd_sub.command) @var.cmd_sub.full_command) @var.cmd_sub,
                
            (arithmetic_expansion
                (_) @var.arith.expression) @var.arith
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "variable_usage",
            "is_assignment": "var.assign" in node["captures"],
            "is_expansion": "var.expand" in node["captures"],
            "is_cmd_substitution": "var.cmd_sub" in node["captures"],
            "is_arithmetic": "var.arith" in node["captures"],
            "variable_name": (
                node["captures"].get("var.assign.name", {}).get("text", "") or
                node["captures"].get("var.expand.name", {}).get("text", "") or
                node["captures"].get("var.expand.array_name", {}).get("text", "")
            ),
            "command_name": node["captures"].get("var.cmd_sub.command", {}).get("text", ""),
            "variable_pattern": (
                "assignment" if "var.assign" in node["captures"] else
                "expansion" if "var.expand" in node["captures"] else
                "command_substitution" if "var.cmd_sub" in node["captures"] else
                "arithmetic_expansion" if "var.arith" in node["captures"] else
                "unknown"
            )
        }
    },
    
    "error_handling": {
        "pattern": """
        [
            (command
                name: (command_name) @error.trap.name
                (#match? @error.trap.name "^trap$")
                argument: (_) @error.trap.action) @error.trap,
                
            (binary_expression
                left: (command
                    name: (command_name) @error.check.cmd) @error.check.left
                operator: (_) @error.check.op
                right: (_) @error.check.right
                (#match? @error.check.op "^(\\|\\||&&)$")) @error.check,
                
            (command
                name: (command_name) @error.exit.name
                (#match? @error.exit.name "^exit$")
                argument: (_) @error.exit.code) @error.exit,
                
            (command 
                name: (command_name) @error.test.name
                (#match? @error.test.name "^(test|\\[)$")
                argument: (_) @error.test.condition) @error.test
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "error_handling",
            "is_trap": "error.trap" in node["captures"],
            "is_condition_check": "error.check" in node["captures"],
            "is_exit": "error.exit" in node["captures"],
            "is_test": "error.test" in node["captures"],
            "command_name": (
                node["captures"].get("error.trap.name", {}).get("text", "") or
                node["captures"].get("error.check.cmd", {}).get("text", "") or
                node["captures"].get("error.exit.name", {}).get("text", "") or
                node["captures"].get("error.test.name", {}).get("text", "")
            ),
            "operator": node["captures"].get("error.check.op", {}).get("text", ""),
            "error_pattern": (
                "trap" if "error.trap" in node["captures"] else
                "conditional_execution" if "error.check" in node["captures"] else
                "exit_code" if "error.exit" in node["captures"] else
                "test_condition" if "error.test" in node["captures"] else
                "unknown"
            )
        }
    }
}

SHELL_PATTERNS = {
    **COMMON_PATTERNS,  # Keep as fallback for basic patterns
    
    "syntax": {
        "function": {
            "pattern": """
            [
                (function_definition
                    name: (word) @syntax.function.name
                    body: (compound_statement) @syntax.function.body) @syntax.function.def,
                
                (command
                    name: (command_name) @syntax.command.name
                    argument: (word) @syntax.command.arg)* @syntax.command
            ]
            """,
            "extract": lambda node: {
                "name": node["captures"].get("syntax.function.name", {}).get("text", "") or
                       node["captures"].get("syntax.command.name", {}).get("text", ""),
                "is_command": "syntax.command" in node["captures"]
            }
        },
        "variable": {
            "pattern": """
            [
                (variable_assignment
                    name: (variable_name) @syntax.variable.name
                    value: (_) @syntax.variable.value) @syntax.variable.assignment,
                
                (expansion
                    [
                        (variable_name) @syntax.variable.reference
                        (subscript
                            name: (variable_name) @syntax.variable.array_name
                            index: (_) @syntax.variable.index) @syntax.variable.array_ref
                    ]) @syntax.variable.expansion
            ]
            """,
            "extract": lambda node: {
                "name": node["captures"].get("syntax.variable.name", {}).get("text", "") or
                       node["captures"].get("syntax.variable.reference", {}).get("text", "") or
                       node["captures"].get("syntax.variable.array_name", {}).get("text", ""),
                "is_assignment": "syntax.variable.assignment" in node["captures"],
                "is_array": "syntax.variable.array_ref" in node["captures"]
            }
        },
        "condition": {
            "pattern": """
            [
                (if_statement
                    condition: (_) @syntax.if.condition
                    consequence: (_) @syntax.if.then
                    alternative: (_)? @syntax.if.else) @syntax.if,
                
                (case_statement
                    value: (_) @syntax.case.value
                    cases: (case_item)* @syntax.case.items) @syntax.case,
                
                (binary_expression
                    left: (_) @syntax.binary.left
                    operator: (_) @syntax.binary.operator
                    right: (_) @syntax.binary.right) @syntax.binary,
                
                (test_command
                    argument: (_)* @syntax.test.args) @syntax.test
            ]
            """,
            "extract": lambda node: {
                "type": ("if" if "syntax.if" in node["captures"] else
                        "case" if "syntax.case" in node["captures"] else
                        "binary" if "syntax.binary" in node["captures"] else
                        "test")
            }
        }
    },
    
    "semantics": {
        "command": {
            "pattern": """
            [
                (pipeline
                    (command
                        name: (command_name) @semantics.pipeline.cmd1) @semantics.pipeline.command1
                    (command
                        name: (command_name) @semantics.pipeline.cmd2) @semantics.pipeline.command2) @semantics.pipeline,
                
                (command
                    name: (command_name) @semantics.redirection.cmd
                    (_)*
                    (redirections
                        [
                            (file_redirect
                                descriptor: (_)? @semantics.redirection.desc
                                operator: (_) @semantics.redirection.op
                                file: (_) @semantics.redirection.file) @semantics.redirection.file_redirect
                            (heredoc_redirect) @semantics.redirection.heredoc
                        ]) @semantics.redirection.all) @semantics.redirection
            ]
            """,
            "extract": lambda node: {
                "is_pipeline": "semantics.pipeline" in node["captures"],
                "is_redirection": "semantics.redirection" in node["captures"],
                "pipeline_commands": [
                    node["captures"].get("semantics.pipeline.cmd1", {}).get("text", ""),
                    node["captures"].get("semantics.pipeline.cmd2", {}).get("text", "")
                ] if "semantics.pipeline" in node["captures"] else [],
                "redirection_command": node["captures"].get("semantics.redirection.cmd", {}).get("text", "")
            }
        },
        "loop": {
            "pattern": """
            [
                (for_statement
                    variable: (variable_name) @semantics.for.var
                    value: (_) @semantics.for.values
                    body: (do_group) @semantics.for.body) @semantics.for,
                
                (while_statement
                    condition: (_) @semantics.while.cond
                    body: (do_group) @semantics.while.body) @semantics.while,
                
                (until_statement
                    condition: (_) @semantics.until.cond
                    body: (do_group) @semantics.until.body) @semantics.until
            ]
            """,
            "extract": lambda node: {
                "type": ("for" if "semantics.for" in node["captures"] else
                        "while" if "semantics.while" in node["captures"] else
                        "until"),
                "variable": node["captures"].get("semantics.for.var", {}).get("text", "")
            }
        }
    },
    
    "structure": {
        "script": {
            "pattern": """
            [
                (shebang) @structure.shebang,
                
                (comment) @structure.comment
            ]
            """,
            "extract": lambda node: {
                "shebang": node["captures"].get("structure.shebang", {}).get("text", ""),
                "comment": node["captures"].get("structure.comment", {}).get("text", "")
            }
        }
    },
    
    "REPOSITORY_LEARNING": SHELL_PATTERNS_FOR_LEARNING
} 