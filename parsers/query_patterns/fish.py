"""Query patterns for Fish shell files."""

from parsers.types import (
    FileType, PatternCategory, PatternPurpose,
    QueryPattern, PatternDefinition
)
from .common import COMMON_PATTERNS

FISH_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "command": QueryPattern(
                pattern="""
                (command
                    name: (_) @syntax.command.name
                    argument: (_)* @syntax.command.args) @syntax.command
                """,
                extract=lambda node: {
                    "name": node["captures"].get("syntax.command.name", {}).get("text", ""),
                    "type": "command"
                }
            ),
            "function": QueryPattern(
                pattern="""
                (function_definition
                    name: (_) @syntax.function.name
                    argument: (_)* @syntax.function.args
                    body: (_) @syntax.function.body) @syntax.function
                """,
                extract=lambda node: {
                    "name": node["captures"].get("syntax.function.name", {}).get("text", ""),
                    "type": "function"
                }
            )
        }
    },

    PatternCategory.SEMANTICS: {
        PatternPurpose.UNDERSTANDING: {
            "variable": QueryPattern(
                pattern="""
                [
                    (variable_expansion) @semantics.variable.usage,
                    (command
                        name: (word) @semantics.variable.set.cmd
                        (#eq? @semantics.variable.set.cmd "set")
                        argument: [
                            (word) @semantics.variable.name
                            (_)* @semantics.variable.value
                        ]) @semantics.variable.definition
                ]
                """,
                extract=lambda node: {
                    "name": node["captures"].get("semantics.variable.name", {}).get("text", ""),
                    "type": "variable",
                    "is_definition": "semantics.variable.definition" in node["captures"]
                }
            ),
            "expression": QueryPattern(
                pattern="""
                [
                    (redirected_statement
                        body: (_) @semantics.expression.body
                        redirection: (_)+ @semantics.expression.redirection) @semantics.expression.redirected,
                    (test_command
                        argument: (_)+ @semantics.expression.test.args) @semantics.expression.test
                ]
                """,
                extract=lambda node: {
                    "type": "expression",
                    "expression_type": "redirected" if "semantics.expression.redirected" in node["captures"] else "test"
                }
            )
        }
    },

    PatternCategory.DOCUMENTATION: {
        PatternPurpose.UNDERSTANDING: {
            "comment": QueryPattern(
                pattern="(comment) @documentation.comment",
                extract=lambda node: {
                    "text": node["captures"].get("documentation.comment", {}).get("text", ""),
                    "type": "comment"
                }
            )
        }
    },

    PatternCategory.STRUCTURE: {
        PatternPurpose.UNDERSTANDING: {
            "conditional": QueryPattern(
                pattern="""
                [
                    (if_statement
                        condition: (_) @structure.conditional.if.condition
                        body: (_) @structure.conditional.if.body
                        else_part: (_)? @structure.conditional.if.else) @structure.conditional.if,
                    (switch_statement
                        argument: (_) @structure.conditional.switch.arg
                        case: (_)* @structure.conditional.switch.cases) @structure.conditional.switch
                ]
                """,
                extract=lambda node: {
                    "type": "conditional",
                    "conditional_type": "if" if "structure.conditional.if" in node["captures"] else "switch"
                }
            ),
            "loop": QueryPattern(
                pattern="""
                [
                    (for_statement
                        variable: (_) @structure.loop.for.var
                        argument: (_)* @structure.loop.for.args
                        body: (_) @structure.loop.for.body) @structure.loop.for,
                    (while_statement
                        condition: (_) @structure.loop.while.condition
                        body: (_) @structure.loop.while.body) @structure.loop.while
                ]
                """,
                extract=lambda node: {
                    "type": "loop",
                    "loop_type": "for" if "structure.loop.for" in node["captures"] else "while"
                }
            )
        }
    },
    
    PatternCategory.LEARNING: {
        PatternPurpose.BEST_PRACTICES: {
            "shell_best_practices": QueryPattern(
                pattern="""
                [
                    (command
                        name: (word) @best.cmd.name
                        argument: (_)* @best.cmd.args) @best.command,
                        
                    (redirection
                        operator: (_) @best.redir.op
                        argument: (_) @best.redir.arg) @best.redirection,
                        
                    (comment) @best.comment
                ]
                """,
                extract=lambda node: {
                    "pattern_type": (
                        "command" if "best.command" in node["captures"] else
                        "redirection" if "best.redirection" in node["captures"] else
                        "comment" if "best.comment" in node["captures"] else
                        "other"
                    ),
                    "uses_subcommand": "(" in (node["captures"].get("best.cmd.args", {}).get("text", "") or ""),
                    "uses_pipe": "|" in (node["captures"].get("best.command", {}).get("text", "") or ""),
                    "uses_redirection": "best.redirection" in node["captures"],
                    "redirection_type": node["captures"].get("best.redir.op", {}).get("text", ""),
                    "has_comments": "best.comment" in node["captures"],
                    "command_name": node["captures"].get("best.cmd.name", {}).get("text", "")
                }
            )
        },
        PatternPurpose.CODE_ORGANIZATION: {
            "function_patterns": QueryPattern(
                pattern="""
                [
                    (function_definition
                        name: (_) @func.name
                        body: (_) @func.body) @func.definition,
                        
                    (command
                        name: (_) @func.call.name
                        argument: (_)* @func.call.args) @func.call
                ]
                """,
                extract=lambda node: {
                    "pattern_type": "function" if "func.definition" in node["captures"] else "command",
                    "function_name": node["captures"].get("func.name", {}).get("text", ""),
                    "has_arguments": "func.call.args" in node["captures"],
                    "uses_common_fish_functions": any(
                        common_func in (node["captures"].get("func.call.name", {}).get("text", "") or "")
                        for common_func in ["set", "test", "read", "string", "math", "echo", "printf"]
                    ),
                    "is_single_line": "\n" not in (node["captures"].get("func.body", {}).get("text", "") or "")
                }
            )
        },
        PatternPurpose.ERROR_HANDLING: {
            "error_handling": QueryPattern(
                pattern="""
                [
                    (if_statement
                        condition: (_) @error.if.condition
                        body: (_) @error.if.body
                        else_part: (_)? @error.if.else) @error.if,
                        
                    (command
                        name: (word) @error.cmd.name
                        (#match? @error.cmd.name "^(status|test|return)$")
                        argument: (_)* @error.cmd.args) @error.cmd
                ]
                """,
                extract=lambda node: {
                    "pattern_type": "error_handling",
                    "uses_status_check": "error.cmd" in node["captures"] and "status" in (node["captures"].get("error.cmd.name", {}).get("text", "") or ""),
                    "uses_test": "error.cmd" in node["captures"] and "test" in (node["captures"].get("error.cmd.name", {}).get("text", "") or ""),
                    "uses_return": "error.cmd" in node["captures"] and "return" in (node["captures"].get("error.cmd.name", {}).get("text", "") or ""),
                    "has_error_handling": "error.if" in node["captures"],
                    "has_else": "error.if.else" in node["captures"]
                }
            )
        }
    }
} 