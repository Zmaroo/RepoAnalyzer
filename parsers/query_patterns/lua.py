"""Query patterns for Lua files."""

from parsers.types import (
    FileType, PatternCategory, PatternPurpose,
    QueryPattern, PatternDefinition
)

LUA_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "function": QueryPattern(
                pattern="""
                [
                    (function_definition
                        name: (_) @syntax.function.name
                        parameters: (parameters
                            (_)* @syntax.function.params)
                        body: (block)? @syntax.function.body) @syntax.function.def,
                    (local_function
                        name: (_) @syntax.function.local.name
                        parameters: (parameters
                            (_)* @syntax.function.local.params)
                        body: (block)? @syntax.function.local.body) @syntax.function.local.def
                ]
                """,
                extract=lambda node: {
                    "name": (
                        node["captures"].get("syntax.function.name", {}).get("text", "") or
                        node["captures"].get("syntax.function.local.name", {}).get("text", "")
                    ),
                    "type": "function",
                    "is_local": "syntax.function.local.def" in node["captures"],
                    "has_params": any(
                        key in node["captures"] for key in 
                        ["syntax.function.params", "syntax.function.local.params"]
                    )
                }
            ),
            "table": QueryPattern(
                pattern="""
                [
                    (table_constructor
                        fields: (field_list
                            (_)* @syntax.table.fields)) @syntax.table.def,
                    (field
                        name: (_)? @syntax.table.field.name
                        value: (_) @syntax.table.field.value) @syntax.table.field
                ]
                """,
                extract=lambda node: {
                    "type": "table",
                    "has_fields": "syntax.table.fields" in node["captures"],
                    "field_name": node["captures"].get("syntax.table.field.name", {}).get("text", ""),
                    "field_value": node["captures"].get("syntax.table.field.value", {}).get("text", "")
                }
            )
        }
    },

    PatternCategory.SEMANTICS: {
        PatternPurpose.UNDERSTANDING: {
            "variable": QueryPattern(
                pattern="""
                [
                    (variable_declaration
                        name: (_) @semantics.var.name
                        value: (_)? @semantics.var.value) @semantics.var.def,
                    (local_variable_declaration
                        name: (_) @semantics.var.local.name
                        value: (_)? @semantics.var.local.value) @semantics.var.local.def
                ]
                """,
                extract=lambda node: {
                    "name": (
                        node["captures"].get("semantics.var.name", {}).get("text", "") or
                        node["captures"].get("semantics.var.local.name", {}).get("text", "")
                    ),
                    "type": "variable",
                    "is_local": "semantics.var.local.def" in node["captures"],
                    "has_value": any(
                        key in node["captures"] for key in 
                        ["semantics.var.value", "semantics.var.local.value"]
                    )
                }
            )
        }
    },

    PatternCategory.DOCUMENTATION: {
        PatternPurpose.UNDERSTANDING: {
            "comment": QueryPattern(
                pattern="""
                [
                    (comment) @documentation.comment.line,
                    (comment_block) @documentation.comment.block
                ]
                """,
                extract=lambda node: {
                    "text": (
                        node["captures"].get("documentation.comment.line", {}).get("text", "") or
                        node["captures"].get("documentation.comment.block", {}).get("text", "")
                    ),
                    "type": "comment",
                    "is_block": "documentation.comment.block" in node["captures"]
                }
            )
        }
    },

    PatternCategory.STRUCTURE: {
        PatternPurpose.UNDERSTANDING: {
            "module": QueryPattern(
                pattern="""
                [
                    (require
                        path: (_) @structure.module.path) @structure.module.require,
                    (return_statement
                        value: (_) @structure.module.return) @structure.module.export
                ]
                """,
                extract=lambda node: {
                    "type": "module",
                    "is_require": "structure.module.require" in node["captures"],
                    "is_export": "structure.module.export" in node["captures"],
                    "path": node["captures"].get("structure.module.path", {}).get("text", ""),
                    "return_value": node["captures"].get("structure.module.return", {}).get("text", "")
                }
            )
        }
    },

    PatternCategory.LEARNING: {
        PatternPurpose.BEST_PRACTICES: {
            "error_handling": QueryPattern(
                pattern="""
                [
                    (function_call
                        name: (_) @learning.error.pcall.name
                        (#match? @learning.error.pcall.name "pcall|xpcall")) @learning.error.pcall,
                    (if_statement
                        condition: (_) @learning.error.check.cond
                        consequence: (block) @learning.error.check.block) @learning.error.check
                ]
                """,
                extract=lambda node: {
                    "pattern_type": "error_handling",
                    "uses_pcall": "learning.error.pcall" in node["captures"],
                    "has_error_check": "learning.error.check" in node["captures"],
                    "pcall_type": node["captures"].get("learning.error.pcall.name", {}).get("text", ""),
                    "check_condition": node["captures"].get("learning.error.check.cond", {}).get("text", "")
                }
            )
        },
        PatternPurpose.PERFORMANCE: {
            "table_optimization": QueryPattern(
                pattern="""
                [
                    (function_call
                        name: (_) @learning.table.opt.name
                        (#match? @learning.table.opt.name "table\\.concat|table\\.pack|table\\.unpack")) @learning.table.opt,
                    (for_statement
                        iterator: (_) @learning.table.iter.var
                        sequence: (_) @learning.table.iter.seq) @learning.table.iter
                ]
                """,
                extract=lambda node: {
                    "pattern_type": "table_optimization",
                    "uses_table_function": "learning.table.opt" in node["captures"],
                    "uses_iterator": "learning.table.iter" in node["captures"],
                    "table_function": node["captures"].get("learning.table.opt.name", {}).get("text", ""),
                    "iterator_var": node["captures"].get("learning.table.iter.var", {}).get("text", "")
                }
            )
        },
        PatternPurpose.METAPROGRAMMING: {
            "meta_features": QueryPattern(
                pattern="""
                [
                    (function_call
                        name: (_) @learning.meta.name
                        (#match? @learning.meta.name "setmetatable|getmetatable|rawget|rawset|debug\\.")) @learning.meta.call,
                    (table_constructor
                        fields: (field_list
                            (_) @learning.meta.table.fields)) @learning.meta.table
                ]
                """,
                extract=lambda node: {
                    "pattern_type": "metaprogramming",
                    "uses_meta_function": "learning.meta.call" in node["captures"],
                    "has_meta_table": "learning.meta.table" in node["captures"],
                    "meta_function": node["captures"].get("learning.meta.name", {}).get("text", ""),
                    "has_fields": "learning.meta.table.fields" in node["captures"]
                }
            )
        }
    }
} 