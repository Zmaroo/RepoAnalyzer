"""Query patterns for Fish shell files."""

from parsers.types import FileType
from .common import COMMON_PATTERNS

FISH_PATTERNS_FOR_LEARNING = {
    "function_patterns": {
        "pattern": """
        [
            (function_definition
                name: (_) @func.name
                body: (_) @func.body) @func.definition,
                
            (command
                name: (_) @func.call.name
                argument: (_)* @func.call.args) @func.call
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "function" if "func.definition" in node["captures"] else "command",
            "function_name": node["captures"].get("func.name", {}).get("text", ""),
            "has_arguments": "func.call.args" in node["captures"],
            "uses_common_fish_functions": any(
                common_func in (node["captures"].get("func.call.name", {}).get("text", "") or "")
                for common_func in ["set", "test", "read", "string", "math", "echo", "printf"]
            ),
            "is_single_line": "\n" not in (node["captures"].get("func.body", {}).get("text", "") or "")
        }
    },
    
    "variable_usage": {
        "pattern": """
        [
            (variable_expansion) @var.expansion,
            
            (command
                name: (word) @var.cmd.set
                (#eq? @var.cmd.set "set")
                argument: [
                    (word) @var.name
                    (_)* @var.value
                ]) @var.definition
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "variable_expansion" if "var.expansion" in node["captures"] else "variable_definition",
            "variable_name": node["captures"].get("var.name", {}).get("text", ""),
            "uses_expansion": "var.expansion" in node["captures"],
            "uses_scope_flag": any(
                flag in (node["captures"].get("var.definition", {}).get("text", "") or "")
                for flag in ["-g", "-l", "-U", "-x"]
            ),
            "expansion_text": node["captures"].get("var.expansion", {}).get("text", "")
        }
    },
    
    "control_flow": {
        "pattern": """
        [
            (if_statement
                condition: (_) @flow.if.condition
                body: (_) @flow.if.body
                else_if_part: (_)* @flow.if.elseif
                else_part: (_)? @flow.if.else) @flow.if,
                
            (for_statement
                variable: (_) @flow.for.var
                argument: (_)* @flow.for.args
                body: (_) @flow.for.body) @flow.for,
                
            (while_statement
                condition: (_) @flow.while.condition
                body: (_) @flow.while.body) @flow.while,
                
            (begin_statement
                body: (_) @flow.begin.body) @flow.begin,
                
            (switch_statement
                argument: (_) @flow.switch.arg
                case: (_)* @flow.switch.cases) @flow.switch
        ]
        """,
        "extract": lambda node: {
            "control_structure": (
                "if" if "flow.if" in node["captures"] else
                "for" if "flow.for" in node["captures"] else
                "while" if "flow.while" in node["captures"] else
                "begin" if "flow.begin" in node["captures"] else
                "switch" if "flow.switch" in node["captures"] else
                "other"
            ),
            "has_else": "flow.if.else" in node["captures"] and node["captures"].get("flow.if.else", {}).get("text", ""),
            "has_else_if": "flow.if.elseif" in node["captures"] and node["captures"].get("flow.if.elseif", {}).get("text", ""),
            "condition_complexity": len((node["captures"].get("flow.if.condition", {}).get("text", "") or "").split()) if "flow.if.condition" in node["captures"] else 0
        }
    },
    
    "shell_best_practices": {
        "pattern": """
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
        "extract": lambda node: {
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
    }
}

FISH_PATTERNS = {
    **COMMON_PATTERNS,
    
    "syntax": {
        "command": {
            "pattern": """
            (command
                name: (_) @syntax.command.name
                argument: (_)* @syntax.command.args) @syntax.command
            """
        },
        "function": {
            "pattern": """
            (function_definition
                name: (_) @syntax.function.name
                argument: (_)* @syntax.function.args
                body: (_) @syntax.function.body) @syntax.function
            """
        }
    },

    "semantics": {
        "variable": {
            "pattern": """
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
            """
        },
        "expression": {
            "pattern": """
            [
                (redirected_statement
                    body: (_) @semantics.expression.body
                    redirection: (_)+ @semantics.expression.redirection) @semantics.expression.redirected,
                (test_command
                    argument: (_)+ @semantics.expression.test.args) @semantics.expression.test
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
        "conditional": {
            "pattern": """
            [
                (if_statement
                    condition: (_) @structure.conditional.if.condition
                    body: (_) @structure.conditional.if.body
                    else_part: (_)? @structure.conditional.if.else) @structure.conditional.if,
                (switch_statement
                    argument: (_) @structure.conditional.switch.arg
                    case: (_)* @structure.conditional.switch.cases) @structure.conditional.switch
            ]
            """
        },
        "loop": {
            "pattern": """
            [
                (for_statement
                    variable: (_) @structure.loop.for.var
                    argument: (_)* @structure.loop.for.args
                    body: (_) @structure.loop.for.body) @structure.loop.for,
                (while_statement
                    condition: (_) @structure.loop.while.condition
                    body: (_) @structure.loop.while.body) @structure.loop.while
            ]
            """
        }
    },
    
    "REPOSITORY_LEARNING": FISH_PATTERNS_FOR_LEARNING
} 