"""Query patterns for CMake files."""

from parsers.types import (
    FileType, PatternCategory, PatternPurpose,
    QueryPattern, PatternDefinition
)
from .common import COMMON_PATTERNS

CMAKE_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "function": QueryPattern(
                pattern="""
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
                extract=lambda node: {
                    "name": node["captures"].get("syntax.command.name", {}).get("text", ""),
                    "type": ("function" if "syntax.function.def" in node["captures"] else
                            "macro" if "syntax.macro.def" in node["captures"] else
                            "command")
                }
            ),
            
            "control_flow": QueryPattern(
                pattern="""
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
                extract=lambda node: {
                    "type": ("if" if "syntax.if.def" in node["captures"] else
                            "foreach" if "syntax.foreach.def" in node["captures"] else
                            "while")
                }
            )
        }
    },
    
    PatternCategory.SEMANTICS: {
        PatternPurpose.UNDERSTANDING: {
            "variable": QueryPattern(
                pattern="""
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
                extract=lambda node: {
                    "name": (node["captures"].get("semantics.var.name", {}).get("text", "") or
                            node["captures"].get("semantics.var.env.name", {}).get("text", "") or
                            node["captures"].get("semantics.var.cache.name", {}).get("text", "")),
                    "type": ("normal" if "semantics.var.normal" in node["captures"] else
                            "env" if "semantics.var.env" in node["captures"] else
                            "cache")
                }
            )
        }
    },
    
    PatternCategory.STRUCTURE: {
        PatternPurpose.UNDERSTANDING: {
            "block": QueryPattern(
                pattern="""
                [
                    (block_def
                        (block_command
                            (argument_list) @structure.block.args) @structure.block.start
                            (body) @structure.block.body
                            (endblock_command) @structure.block.end) @structure.block.def
                ]
                """,
                extract=lambda node: {
                    "args": node["captures"].get("structure.block.args", {}).get("text", "")
                }
            )
        }
    },
    
    PatternCategory.DOCUMENTATION: {
        PatternPurpose.UNDERSTANDING: {
            "comments": QueryPattern(
                pattern="""
                [
                    (line_comment) @documentation.comment.line,
                    (bracket_comment) @documentation.comment.bracket
                ]
                """,
                extract=lambda node: {
                    "text": node["captures"].get("documentation.comment.line", {}).get("text", "") or
                           node["captures"].get("documentation.comment.bracket", {}).get("text", ""),
                    "type": "line" if "documentation.comment.line" in node["captures"] else "bracket"
                }
            )
        }
    },
    
    PatternCategory.LEARNING: {
        PatternPurpose.BEST_PRACTICES: {
            "naming_conventions": QueryPattern(
                pattern="""
                [
                    (function_def
                        (function_command
                            (argument_list) @naming.function.args)) @naming.function,
                            
                    (normal_command
                        (identifier) @naming.command.name) @naming.command,
                        
                    (variable_ref
                        [(normal_var
                            (variable) @naming.var.name) @naming.var
                         (cache_var 
                            (variable) @naming.cache.name) @naming.cache]) @naming.variable
                ]
                """,
                extract=lambda node: {
                    "type": "naming_convention_pattern",
                    "entity_type": ("function" if "naming.function" in node["captures"] else
                                   "command" if "naming.command" in node["captures"] else
                                   "variable"),
                    "name": (node["captures"].get("naming.function.args", {}).get("text", "") or
                            node["captures"].get("naming.command.name", {}).get("text", "") or
                            node["captures"].get("naming.var.name", {}).get("text", "") or
                            node["captures"].get("naming.cache.name", {}).get("text", "")),
                    "is_uppercase": all(c.isupper() or not c.isalpha() for c in 
                                      (node["captures"].get("naming.var.name", {}).get("text", "") or 
                                       node["captures"].get("naming.cache.name", {}).get("text", "") or "")),
                    "is_snake_case": "_" in (node["captures"].get("naming.function.args", {}).get("text", "") or
                                            node["captures"].get("naming.command.name", {}).get("text", "") or "")
                }
            ),
            "command_usage": QueryPattern(
                pattern="""
                [
                    (normal_command
                        (identifier) @command.name
                        (argument_list) @command.args) @command.def
                ]
                """,
                extract=lambda node: {
                    "type": "command_usage_pattern",
                    "command": node["captures"].get("command.name", {}).get("text", "").lower(),
                    "is_project_command": node["captures"].get("command.name", {}).get("text", "").lower() == "project",
                    "is_find_package": node["captures"].get("command.name", {}).get("text", "").lower() == "find_package",
                    "is_add_executable": node["captures"].get("command.name", {}).get("text", "").lower() == "add_executable",
                    "is_add_library": node["captures"].get("command.name", {}).get("text", "").lower() == "add_library",
                    "args_count": len(node["captures"].get("command.args", {}).get("text", "").split())
                }
            )
        },
        PatternPurpose.CODE_ORGANIZATION: {
            "code_structure": QueryPattern(
                pattern="""
                [
                    (normal_command
                        (identifier) @structure.command.name
                        (#match? @structure.command.name "^(project|add_executable|add_library|add_subdirectory)$")) @structure.project.command,
                        
                    (normal_command
                        (identifier) @structure.test.command
                        (#match? @structure.test.command "^(add_test|enable_testing)$")) @structure.test.def
                ]
                """,
                extract=lambda node: {
                    "type": "code_structure_pattern",
                    "command": node["captures"].get("structure.command.name", {}).get("text", "") or
                              node["captures"].get("structure.test.command", {}).get("text", ""),
                    "has_testing": "structure.test.def" in node["captures"],
                    "is_project_structure": "structure.project.command" in node["captures"]
                }
            )
        }
    }
} 