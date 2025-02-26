"""Lua-specific Tree-sitter patterns."""

from parsers.models import FileType, FileClassification
from .common import COMMON_PATTERNS

LUA_PATTERNS_FOR_LEARNING = {
    "oop_patterns": {
        "pattern": """
        [
            (assignment_statement
                variables: (variable_list
                    (identifier) @oop.class.name)
                values: (expression_list
                    (table_constructor) @oop.class.body)) @oop.class,
                
            (field
                name: (identifier) @oop.method.name
                value: (function_definition) @oop.method.def) @oop.method,
                
            (function_call
                prefix: (identifier) @oop.new.func
                (#match? @oop.new.func "^[nN]ew$")
                arguments: (_) @oop.new.args) @oop.new,
                
            (method_index_expression
                table: (identifier) @oop.self.class
                method: (identifier) @oop.self.method) @oop.self
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "oop_implementation",
            "is_class_definition": "oop.class" in node["captures"],
            "is_method_definition": "oop.method" in node["captures"],
            "is_constructor_call": "oop.new" in node["captures"],
            "is_method_call": "oop.self" in node["captures"],
            "class_name": node["captures"].get("oop.class.name", {}).get("text", ""),
            "method_name": node["captures"].get("oop.method.name", {}).get("text", ""),
            "uses_self_parameter": "self" in (node["captures"].get("oop.method.def", {}).get("text", "") or ""),
            "oop_style": (
                "metatable_based" if "setmetatable" in (node["captures"].get("oop.class.body", {}).get("text", "") or "") else 
                "table_based" if "oop.class" in node["captures"] else
                "other"
            )
        }
    },
    
    "metaprogramming": {
        "pattern": """
        [
            (function_call
                prefix: (identifier) @meta.func.name
                (#match? @meta.func.name "^setmetatable|getmetatable|rawget|rawset|debug\\.|load|loadfile$")
                arguments: (_) @meta.func.args) @meta.func,
                
            (index_expression
                table: (identifier) @meta.index.table
                (#eq? @meta.index.table "_G")
                index: (_) @meta.index.key) @meta.index,
                
            (field
                name: (identifier) @meta.field.name
                (#match? @meta.field.name "^__[a-z]+$")
                value: (_) @meta.field.value) @meta.field
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "metaprogramming",
            "uses_metatable_function": "meta.func" in node["captures"] and node["captures"].get("meta.func.name", {}).get("text", "") in ["setmetatable", "getmetatable"],
            "uses_raw_access": "meta.func" in node["captures"] and node["captures"].get("meta.func.name", {}).get("text", "") in ["rawget", "rawset"],
            "uses_global_table": "meta.index" in node["captures"],
            "uses_metamethod": "meta.field" in node["captures"],
            "metamethod_name": node["captures"].get("meta.field.name", {}).get("text", ""),
            "metaprogramming_technique": (
                "metatable_manipulation" if "meta.func" in node["captures"] and node["captures"].get("meta.func.name", {}).get("text", "") in ["setmetatable", "getmetatable"] else
                "raw_table_access" if "meta.func" in node["captures"] and node["captures"].get("meta.func.name", {}).get("text", "") in ["rawget", "rawset"] else
                "global_manipulation" if "meta.index" in node["captures"] else
                "metamethod_definition" if "meta.field" in node["captures"] else
                "other"
            )
        }
    },
    
    "module_patterns": {
        "pattern": """
        [
            (assignment_statement
                variables: (variable_list
                    (identifier) @module.name)
                values: (expression_list
                    (table_constructor) @module.exports)) @module.def,
                
            (assignment_statement
                variables: (variable_list
                    (index_expression
                        table: (identifier) @module.table
                        index: (identifier) @module.field))
                values: (expression_list
                    (_) @module.value)) @module.field.def,
                
            (function_call
                prefix: (identifier) @module.require.func
                (#match? @module.require.func "^require$")
                arguments: (arguments
                    (string) @module.require.path)) @module.require
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "module_pattern",
            "is_module_definition": "module.def" in node["captures"],
            "is_module_field": "module.field.def" in node["captures"],
            "is_module_import": "module.require" in node["captures"],
            "module_name": node["captures"].get("module.name", {}).get("text", ""),
            "module_table": node["captures"].get("module.table", {}).get("text", ""),
            "module_field": node["captures"].get("module.field", {}).get("text", ""),
            "required_module": node["captures"].get("module.require.path", {}).get("text", "").strip('"\''),
            "module_style": (
                "return_table" if "module.def" in node["captures"] else
                "modify_table" if "module.field.def" in node["captures"] else
                "require_import" if "module.require" in node["captures"] else
                "other"
            )
        }
    },
    
    "error_handling": {
        "pattern": """
        [
            (function_call
                prefix: (identifier) @error.func.name
                (#match? @error.func.name "^pcall|xpcall|assert|error$")
                arguments: (_) @error.func.args) @error.func,
                
            (if_statement
                condition: (_) @error.check.cond
                consequence: (_) @error.check.body
                alternative: (_)? @error.check.else) @error.check,
                
            (binary_expression
                operator: (binary_operator) @error.bin.op
                (#match? @error.bin.op "^and|or$")
                left: (_) @error.bin.left
                right: (_) @error.bin.right) @error.bin
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "error_handling",
            "uses_protected_call": "error.func" in node["captures"] and node["captures"].get("error.func.name", {}).get("text", "") in ["pcall", "xpcall"],
            "uses_assertion": "error.func" in node["captures"] and node["captures"].get("error.func.name", {}).get("text", "") == "assert",
            "raises_error": "error.func" in node["captures"] and node["captures"].get("error.func.name", {}).get("text", "") == "error",
            "uses_condition_check": "error.check" in node["captures"],
            "uses_short_circuit": "error.bin" in node["captures"],
            "error_handling_style": (
                "protected_call" if "error.func" in node["captures"] and node["captures"].get("error.func.name", {}).get("text", "") in ["pcall", "xpcall"] else
                "assertion" if "error.func" in node["captures"] and node["captures"].get("error.func.name", {}).get("text", "") == "assert" else
                "error_raising" if "error.func" in node["captures"] and node["captures"].get("error.func.name", {}).get("text", "") == "error" else
                "condition_check" if "error.check" in node["captures"] else
                "short_circuit" if "error.bin" in node["captures"] else
                "other"
            )
        }
    }
}

LUA_PATTERNS = {
    **COMMON_PATTERNS,
    
    "syntax": {
        "function": {
            "pattern": """
            [
                (function_declaration
                    name: [(identifier) @syntax.function.name
                          (dot_index_expression
                            table: (identifier) @syntax.function.table
                            field: (identifier) @syntax.function.field)
                          (method_index_expression
                            table: (identifier) @syntax.function.class
                            method: (identifier) @syntax.function.method)]
                    parameters: (parameters) @syntax.function.params
                    body: (block) @syntax.function.body) @syntax.function.def,
                (local_function
                    name: (identifier) @syntax.function.local.name
                    parameters: (parameters) @syntax.function.local.params
                    body: (block) @syntax.function.local.body) @syntax.function.local
            ]
            """
        },
        "class": {
            "pattern": """
            (assignment_statement
                variables: (variable_list
                    (identifier) @syntax.class.name)
                values: (expression_list
                    (table_constructor
                        [(field
                            name: (identifier) @syntax.class.method.name
                            value: (function_definition) @syntax.class.method.def)
                         (field
                            name: (identifier) @syntax.class.field.name
                            value: (_) @syntax.class.field.value)]*) @syntax.class.body)) @syntax.class.def
            """
        }
    },

    "semantics": {
        "variable": {
            "pattern": """
            [
                (assignment_statement
                    variables: (variable_list
                        (identifier) @semantics.variable.name)
                    values: (expression_list
                        (_) @semantics.variable.value)) @semantics.variable.def,
                (local_variable_declaration
                    name: (identifier) @semantics.variable.local.name
                    value: (_)? @semantics.variable.local.value) @semantics.variable.local
            ]
            """
        },
        "type": {
            "pattern": """
            (type_declaration
                name: (identifier) @semantics.type.name
                value: (_) @semantics.type.value) @semantics.type.def
            """
        }
    },

    "documentation": {
        "comment": {
            "pattern": """
            [
                (comment) @documentation.comment,
                (comment) @documentation.luadoc {
                    match: "^---"
                },
                (comment) @documentation.luadoc.tag {
                    match: "@[a-zA-Z]+"
                }
            ]
            """
        }
    },

    "structure": {
        "module": {
            "pattern": """
            [
                (assignment_statement
                    variables: (variable_list
                        (identifier) @structure.module.name)
                    values: (expression_list
                        (table_constructor) @structure.module.exports)) @structure.module,
                (function_call
                    prefix: (identifier) @structure.require.func
                    (#match? @structure.require.func "^require$")
                    arguments: (arguments
                        (string) @structure.require.path)) @structure.require
            ]
            """
        }
    },
    
    "REPOSITORY_LEARNING": LUA_PATTERNS_FOR_LEARNING
} 