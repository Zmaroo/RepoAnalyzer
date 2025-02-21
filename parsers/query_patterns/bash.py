"""Query patterns for Bash files."""

from .common import COMMON_PATTERNS

BASH_PATTERNS = {
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
                    argument: (_)* @syntax.command.args) @syntax.command.def
            ]
            """,
            "extract": lambda node: {
                "name": node["captures"].get("syntax.function.name", {}).get("text", "") or
                       node["captures"].get("syntax.command.name", {}).get("text", ""),
                "type": "function" if "syntax.function.def" in node["captures"] else "command"
            }
        },
        
        "control_flow": {
            "pattern": """
            [
                (if_statement
                    condition: (_) @syntax.if.condition
                    [(elif_clause) @syntax.if.elif
                     (else_clause) @syntax.if.else]*) @syntax.if.def,
                
                (while_statement
                    condition: (_) @syntax.while.condition
                    body: (_) @syntax.while.body) @syntax.while.def,
                
                (for_statement
                    value: (_) @syntax.for.value
                    body: (_) @syntax.for.body) @syntax.for.def,
                
                (case_statement
                    value: (_) @syntax.case.value
                    (case_item
                        value: (_) @syntax.case.pattern
                        body: (_)? @syntax.case.body)*) @syntax.case.def
            ]
            """,
            "extract": lambda node: {
                "type": ("if" if "syntax.if.def" in node["captures"] else
                        "while" if "syntax.while.def" in node["captures"] else
                        "for" if "syntax.for.def" in node["captures"] else
                        "case")
            }
        }
    },
    
    "semantics": {
        "variable": {
            "pattern": """
            [
                (variable_assignment
                    name: (_) @semantics.variable.name
                    value: (_) @semantics.variable.value) @semantics.variable.def,
                
                (simple_expansion
                    [(variable_name) @semantics.variable.ref
                     (special_variable_name) @semantics.variable.special]) @semantics.variable.expansion
            ]
            """,
            "extract": lambda node: {
                "name": node["captures"].get("semantics.variable.name", {}).get("text", "") or
                       node["captures"].get("semantics.variable.ref", {}).get("text", ""),
                "type": "assignment" if "semantics.variable.def" in node["captures"] else "expansion"
            }
        },
        
        "expansion": {
            "pattern": """
            [
                (command_substitution) @semantics.expansion.command,
                (process_substitution) @semantics.expansion.process,
                (arithmetic_expansion) @semantics.expansion.arithmetic,
                (string) @semantics.expansion.string
            ]
            """,
            "extract": lambda node: {
                "type": ("command" if "semantics.expansion.command" in node["captures"] else
                        "process" if "semantics.expansion.process" in node["captures"] else
                        "arithmetic" if "semantics.expansion.arithmetic" in node["captures"] else
                        "string")
            }
        }
    },
    
    "structure": {
        "redirection": {
            "pattern": """
            [
                (redirected_statement
                    body: (_) @structure.redirect.body
                    redirect: [(file_redirect) @structure.redirect.file
                             (heredoc_redirect) @structure.redirect.heredoc
                             (herestring_redirect) @structure.redirect.herestring]) @structure.redirect.def
            ]
            """,
            "extract": lambda node: {
                "type": ("file" if "structure.redirect.file" in node["captures"] else
                        "heredoc" if "structure.redirect.heredoc" in node["captures"] else
                        "herestring")
            }
        }
    },
    
    "documentation": {
        "comments": {
            "pattern": """
            [
                (comment) @documentation.comment
            ]
            """,
            "extract": lambda node: {
                "text": node["captures"].get("documentation.comment", {}).get("text", "")
            }
        }
    }
} 