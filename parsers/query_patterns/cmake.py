"""Query patterns for CMake files."""

from .common import COMMON_PATTERNS

CMAKE_PATTERNS = {
    **COMMON_PATTERNS,  # Keep as fallback for basic patterns
    
    "syntax": {
        "function": {
            "pattern": """
            [
                (function_def
                    (function_command
                        (argument_list) @syntax.function.args) @syntax.function.header
                    (body) @syntax.function.body
                    (endfunction_command) @syntax.function.end) @syntax.function.def,
                
                (macro_def
                    (macro_command
                        (argument_list) @syntax.macro.args) @syntax.macro.header
                    (body) @syntax.macro.body
                    (endmacro_command) @syntax.macro.end) @syntax.macro.def,
                
                (normal_command
                    (identifier) @syntax.command.name
                    (argument_list) @syntax.command.args) @syntax.command.def
            ]
            """,
            "extract": lambda node: {
                "name": node["captures"].get("syntax.command.name", {}).get("text", ""),
                "type": ("function" if "syntax.function.def" in node["captures"] else
                        "macro" if "syntax.macro.def" in node["captures"] else
                        "command")
            }
        },
        
        "control_flow": {
            "pattern": """
            [
                (if_condition
                    (if_command
                        (argument_list) @syntax.if.condition) @syntax.if.start
                    (body) @syntax.if.body
                    [(elseif_command
                        (argument_list) @syntax.if.elseif.condition) @syntax.if.elseif
                     (else_command) @syntax.if.else]*
                    (endif_command) @syntax.if.end) @syntax.if.def,
                
                (foreach_loop
                    (foreach_command
                        (argument_list) @syntax.foreach.args) @syntax.foreach.start
                    (body) @syntax.foreach.body
                    (endforeach_command) @syntax.foreach.end) @syntax.foreach.def,
                
                (while_loop
                    (while_command
                        (argument_list) @syntax.while.condition) @syntax.while.start
                    (body) @syntax.while.body
                    (endwhile_command) @syntax.while.end) @syntax.while.def
            ]
            """,
            "extract": lambda node: {
                "type": ("if" if "syntax.if.def" in node["captures"] else
                        "foreach" if "syntax.foreach.def" in node["captures"] else
                        "while")
            }
        }
    },
    
    "semantics": {
        "variable": {
            "pattern": """
            [
                (variable_ref
                    [(normal_var
                        (variable) @semantics.var.name) @semantics.var.normal
                     (env_var
                        (variable) @semantics.var.env.name) @semantics.var.env
                     (cache_var
                        (variable) @semantics.var.cache.name) @semantics.var.cache]) @semantics.var.ref
            ]
            """,
            "extract": lambda node: {
                "name": (node["captures"].get("semantics.var.name", {}).get("text", "") or
                        node["captures"].get("semantics.var.env.name", {}).get("text", "") or
                        node["captures"].get("semantics.var.cache.name", {}).get("text", "")),
                "type": ("normal" if "semantics.var.normal" in node["captures"] else
                        "env" if "semantics.var.env" in node["captures"] else
                        "cache")
            }
        }
    },
    
    "structure": {
        "block": {
            "pattern": """
            [
                (block_def
                    (block_command
                        (argument_list) @structure.block.args) @structure.block.start
                    (body) @structure.block.body
                    (endblock_command) @structure.block.end) @structure.block.def
            ]
            """,
            "extract": lambda node: {
                "args": node["captures"].get("structure.block.args", {}).get("text", "")
            }
        }
    },
    
    "documentation": {
        "comments": {
            "pattern": """
            [
                (line_comment) @documentation.comment.line,
                (bracket_comment) @documentation.comment.bracket
            ]
            """,
            "extract": lambda node: {
                "text": node["captures"].get("documentation.comment.line", {}).get("text", "") or
                       node["captures"].get("documentation.comment.bracket", {}).get("text", ""),
                "type": "line" if "documentation.comment.line" in node["captures"] else "bracket"
            }
        }
    }
} 