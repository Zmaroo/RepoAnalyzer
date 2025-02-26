"""Query patterns for Starlark files."""

from parsers.types import FileType
from .common import COMMON_PATTERNS

STARLARK_PATTERNS_FOR_LEARNING = {
    "build_rules": {
        "pattern": """
        [
            (call_expression
                function: (identifier) @build.rule.name {
                    match: "^(binary|library|test|repository|toolchain|filegroup|alias)$"
                }
                arguments: (argument_list) @build.rule.args) @build.rule.def,
                
            (function_definition
                name: (identifier) @build.macro.name
                parameters: (parameters) @build.macro.params
                body: (block
                    (expression_statement
                        (call_expression
                            function: (identifier) @build.macro.internal.rule))* @build.macro.body) @build.macro.implementation
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "build_rules",
            "is_rule_call": "build.rule.def" in node["captures"],
            "is_macro_def": "build.macro.implementation" in node["captures"],
            "rule_name": node["captures"].get("build.rule.name", {}).get("text", ""),
            "macro_name": node["captures"].get("build.macro.name", {}).get("text", ""),
            "internal_rule_calls": [rule.get("text", "") for rule in node["captures"].get("build.macro.internal.rule", [])],
            "rule_type": (
                "direct_rule" if "build.rule.def" in node["captures"] else
                "macro" if "build.macro.implementation" in node["captures"] else
                "unknown"
            )
        }
    },
    
    "dependency_management": {
        "pattern": """
        [
            (call_expression
                function: (identifier) @dep.func.name {
                    match: "^(load|register_toolchains|register_execution_platforms|workspace)$"
                }
                arguments: (argument_list) @dep.func.args) @dep.func.call,
                
            (argument
                name: (keyword) @dep.arg.name {
                    match: "^(deps|runtime_deps|exports|data|srcs)$"
                }
                value: (list
                    (string)* @dep.arg.items) @dep.arg.list) @dep.arg,
                
            (string) @dep.label {
                match: "^([@//].*)$"
            }
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "dependency_management",
            "is_load_call": "dep.func.call" in node["captures"] and node["captures"].get("dep.func.name", {}).get("text", "") == "load",
            "is_workspace_call": "dep.func.call" in node["captures"] and node["captures"].get("dep.func.name", {}).get("text", "") == "workspace",
            "is_deps_arg": "dep.arg" in node["captures"] and node["captures"].get("dep.arg.name", {}).get("text", "") in ["deps", "runtime_deps"],
            "is_label": "dep.label" in node["captures"],
            "function_name": node["captures"].get("dep.func.name", {}).get("text", ""),
            "argument_name": node["captures"].get("dep.arg.name", {}).get("text", ""),
            "label_value": node["captures"].get("dep.label", {}).get("text", ""),
            "dependency_items": [item.get("text", "") for item in node["captures"].get("dep.arg.items", [])],
            "dependency_type": (
                "load" if "dep.func.call" in node["captures"] and node["captures"].get("dep.func.name", {}).get("text", "") == "load" else
                "workspace" if "dep.func.call" in node["captures"] and node["captures"].get("dep.func.name", {}).get("text", "") == "workspace" else
                "deps_list" if "dep.arg" in node["captures"] else
                "label" if "dep.label" in node["captures"] else
                "unknown"
            )
        }
    },
    
    "configuration": {
        "pattern": """
        [
            (assignment
                left: (identifier) @config.var.name {
                    match: "^([A-Z][A-Z0-9_]*)$"
                }
                right: (_) @config.var.value) @config.var.def,
                
            (call_expression
                function: (identifier) @config.func.name {
                    match: "^(config_setting|select)$"
                }
                arguments: (argument_list) @config.func.args) @config.func.call,
                
            (dictionary
                (pair
                    key: (string) @config.dict.key {
                        match: "^(\"[^\"]*config[^\"]*\"|\"platform[^\"]*\"|\"constraint[^\"]*\")$"
                    }
                    value: (_) @config.dict.value) @config.dict.entry)* @config.dict
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "configuration",
            "is_constant": "config.var.def" in node["captures"],
            "is_config_setting": "config.func.call" in node["captures"] and node["captures"].get("config.func.name", {}).get("text", "") == "config_setting",
            "is_select": "config.func.call" in node["captures"] and node["captures"].get("config.func.name", {}).get("text", "") == "select",
            "is_config_dict": "config.dict" in node["captures"],
            "constant_name": node["captures"].get("config.var.name", {}).get("text", ""),
            "function_name": node["captures"].get("config.func.name", {}).get("text", ""),
            "config_keys": [key.get("text", "") for key in node["captures"].get("config.dict.key", [])],
            "config_type": (
                "constant" if "config.var.def" in node["captures"] else
                "config_setting" if "config.func.call" in node["captures"] and node["captures"].get("config.func.name", {}).get("text", "") == "config_setting" else
                "select" if "config.func.call" in node["captures"] and node["captures"].get("config.func.name", {}).get("text", "") == "select" else
                "config_dict" if "config.dict" in node["captures"] else
                "unknown"
            )
        }
    },
    
    "comprehensions": {
        "pattern": """
        [
            (list_comprehension
                body: (expression) @comp.list.body
                for_clause: (for_clause
                    left: (identifier) @comp.list.var
                    right: (expression) @comp.list.iter
                    if_clause: (if_clause)? @comp.list.if) @comp.list.for) @comp.list,
                
            (dictionary_comprehension
                key: (expression) @comp.dict.key
                value: (expression) @comp.dict.value
                for_clause: (for_clause
                    left: (identifier) @comp.dict.var
                    right: (expression) @comp.dict.iter
                    if_clause: (if_clause)? @comp.dict.if) @comp.dict.for) @comp.dict
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "comprehensions",
            "is_list_comp": "comp.list" in node["captures"],
            "is_dict_comp": "comp.dict" in node["captures"],
            "variable": node["captures"].get("comp.list.var", {}).get("text", "") or node["captures"].get("comp.dict.var", {}).get("text", ""),
            "iterable": node["captures"].get("comp.list.iter", {}).get("text", "") or node["captures"].get("comp.dict.iter", {}).get("text", ""),
            "has_filter": ("comp.list.if" in node["captures"] and node["captures"].get("comp.list.if", {}).get("text", "") != "") or
                         ("comp.dict.if" in node["captures"] and node["captures"].get("comp.dict.if", {}).get("text", "") != ""),
            "comp_type": "list_comprehension" if "comp.list" in node["captures"] else "dict_comprehension" if "comp.dict" in node["captures"] else "unknown"
        }
    }
}

STARLARK_PATTERNS = {
    **COMMON_PATTERNS,  # Keep as fallback for basic patterns
    
    "syntax": {
        "function": {
            "pattern": """
            [
                (function_definition
                    name: (identifier) @syntax.function.name
                    parameters: (parameters
                        [(parameter
                            name: (identifier) @syntax.function.param.name
                            default: (_)? @syntax.function.param.default)
                         (typed_parameter
                            name: (identifier) @syntax.function.param.typed.name
                            type: (_) @syntax.function.param.typed.type)
                         (typed_default_parameter
                            name: (identifier) @syntax.function.param.typed_default.name
                            type: (_) @syntax.function.param.typed_default.type
                            default: (_) @syntax.function.param.typed_default.value)]*) @syntax.function.params
                    body: (block) @syntax.function.body) @syntax.function.def,
                
                (lambda
                    parameters: (lambda_parameters
                        (parameter
                            name: (identifier) @syntax.function.lambda.param.name)*)? @syntax.function.lambda.params
                    body: (expression) @syntax.function.lambda.body) @syntax.function.lambda
            ]
            """,
            "extract": lambda node: {
                "name": node["captures"].get("syntax.function.name", {}).get("text", ""),
                "parameters": [p.get("text", "") for p in node["captures"].get("syntax.function.param.name", [])]
            }
        }
    },
    
    "structure": {
        "module": {
            "pattern": """
            [
                (import_statement
                    name: (dotted_name) @structure.import.module) @structure.import,
                
                (import_from_statement
                    module_name: (dotted_name) @structure.import.from.module
                    name: (dotted_name) @structure.import.from.name) @structure.import.from,
                
                (expression_statement
                    (assignment
                        left: (identifier) @structure.module.attr.name
                        right: (_) @structure.module.attr.value)) @structure.module.attr
            ]
            """,
            "extract": lambda node: {
                "module": node["captures"].get("structure.import.module", {}).get("text", "") or
                         node["captures"].get("structure.import.from.module", {}).get("text", ""),
                "name": node["captures"].get("structure.import.from.name", {}).get("text", "")
            }
        }
    },
    
    "semantics": {
        "variable": {
            "pattern": """
            [
                (assignment
                    left: [(identifier) @semantics.variable.name
                          (list_pattern) @semantics.variable.list_pattern
                          (tuple_pattern) @semantics.variable.tuple_pattern
                          (dict_pattern) @semantics.variable.dict_pattern]
                    right: (_) @semantics.variable.value) @semantics.variable.assignment,
                
                (for_statement
                    left: [(identifier) @semantics.variable.loop.name
                          (pattern) @semantics.variable.loop.pattern]
                    right: (_) @semantics.variable.loop.iterable) @semantics.variable.loop
            ]
            """,
            "extract": lambda node: {
                "name": node["captures"].get("semantics.variable.name", {}).get("text", ""),
                "value": node["captures"].get("semantics.variable.value", {}).get("text", "")
            }
        }
    },
    
    "documentation": {
        "comment": {
            "pattern": """
            (comment) @documentation.comment
            """,
            "extract": lambda node: {
                "text": node["captures"].get("documentation.comment", {}).get("text", "")
            }
        }
    },
    
    "REPOSITORY_LEARNING": STARLARK_PATTERNS_FOR_LEARNING
} 