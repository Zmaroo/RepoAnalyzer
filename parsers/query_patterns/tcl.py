"""Query patterns for TCL files."""

from parsers.types import (
    FileType, PatternCategory, PatternPurpose,
    QueryPattern, PatternDefinition
)
from .common import COMMON_PATTERNS

TCL_PATTERNS_FOR_LEARNING = {
    "procedural_patterns": {
        "pattern": """
        [
            (command
                name: (_) @proc.def.name {
                    match: "^proc$"
                }
                argument: [(braced_word) (quoted_word)] @proc.def.name_arg
                argument: (braced_word
                    (word)* @proc.def.param) @proc.def.params
                argument: (braced_word) @proc.def.body) @proc.def,
                
            (command
                name: (_) @proc.call.name
                argument: (_)* @proc.call.arg) @proc.call {
                filter: { @proc.call.name is not null && @proc.call.name !~ "^(proc|if|while|for|foreach|switch|set)$" }
            },
                
            (command
                name: (_) @proc.return.name {
                    match: "^return$"
                }
                argument: (_)? @proc.return.value) @proc.return,
                
            (command
                name: (_) @proc.uplevel.name {
                    match: "^uplevel$"
                }
                argument: (_)+ @proc.uplevel.arg) @proc.uplevel
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "procedural_patterns",
            "is_proc_def": "proc.def" in node["captures"],
            "is_proc_call": "proc.call" in node["captures"],
            "is_return": "proc.return" in node["captures"],
            "is_uplevel": "proc.uplevel" in node["captures"],
            "proc_name": node["captures"].get("proc.def.name_arg", {}).get("text", "") if "proc.def" in node["captures"] else node["captures"].get("proc.call.name", {}).get("text", ""),
            "num_params": len([param for param in node["captures"].get("proc.def.param", [])]) if "proc.def.params" in node["captures"] else 0,
            "num_args": len([arg for arg in node["captures"].get("proc.call.arg", [])]) if "proc.call" in node["captures"] else 0,
            "has_return_value": "proc.return.value" in node["captures"] and node["captures"].get("proc.return.value", {}).get("text", "") != "",
            "proc_type": (
                "definition" if "proc.def" in node["captures"] else
                "call" if "proc.call" in node["captures"] else
                "return" if "proc.return" in node["captures"] else
                "uplevel" if "proc.uplevel" in node["captures"] else
                "unknown"
            )
        }
    },
    
    "control_flow": {
        "pattern": """
        [
            (command
                name: (_) @flow.if.name {
                    match: "^if$"
                }
                argument: (_) @flow.if.cond
                argument: (braced_word) @flow.if.then
                argument: (_) @flow.if.else_part {
                    match: "^else$"
                }
                argument: (braced_word)? @flow.if.else) @flow.if,
                
            (command
                name: (_) @flow.while.name {
                    match: "^while$"
                }
                argument: (_) @flow.while.cond
                argument: (braced_word) @flow.while.body) @flow.while,
                
            (command
                name: (_) @flow.for.name {
                    match: "^for$"
                }
                argument: (braced_word) @flow.for.init
                argument: (_) @flow.for.cond
                argument: (braced_word) @flow.for.incr
                argument: (braced_word) @flow.for.body) @flow.for,
                
            (command
                name: (_) @flow.foreach.name {
                    match: "^foreach$"
                }
                argument: [(word) (quoted_word)] @flow.foreach.var
                argument: (_) @flow.foreach.list
                argument: (braced_word) @flow.foreach.body) @flow.foreach,
                
            (command
                name: (_) @flow.switch.name {
                    match: "^switch$"
                }
                argument: (_)+ @flow.switch.arg) @flow.switch
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "control_flow",
            "is_if": "flow.if" in node["captures"],
            "is_while": "flow.while" in node["captures"],
            "is_for": "flow.for" in node["captures"],
            "is_foreach": "flow.foreach" in node["captures"],
            "is_switch": "flow.switch" in node["captures"],
            "has_else": "flow.if.else" in node["captures"] and node["captures"].get("flow.if.else", {}).get("text", "") != "",
            "condition": (
                node["captures"].get("flow.if.cond", {}).get("text", "") or
                node["captures"].get("flow.while.cond", {}).get("text", "") or
                node["captures"].get("flow.for.cond", {}).get("text", "")
            ),
            "iterator_var": node["captures"].get("flow.foreach.var", {}).get("text", ""),
            "flow_type": (
                "if" if "flow.if" in node["captures"] else
                "while" if "flow.while" in node["captures"] else
                "for" if "flow.for" in node["captures"] else
                "foreach" if "flow.foreach" in node["captures"] else
                "switch" if "flow.switch" in node["captures"] else
                "unknown"
            )
        }
    },
    
    "variable_handling": {
        "pattern": """
        [
            (command
                name: (_) @var.set.name {
                    match: "^set$"
                }
                argument: [(word) (quoted_word)] @var.set.var
                argument: (_)? @var.set.value) @var.set,
                
            (command
                name: (_) @var.array.name {
                    match: "^array$"
                }
                argument: (word) @var.array.op {
                    match: "^(set|get|exists|names|size)$"
                }
                argument: (_)+ @var.array.arg) @var.array,
                
            (command
                name: (_) @var.incr.name {
                    match: "^(incr|append|lappend)$"
                }
                argument: [(word) (quoted_word)] @var.incr.var
                argument: (_)? @var.incr.value) @var.incr,
                
            (variable_substitution
                name: (_) @var.subst.name) @var.subst
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "variable_handling",
            "is_set": "var.set" in node["captures"],
            "is_array_op": "var.array" in node["captures"],
            "is_incr_op": "var.incr" in node["captures"],
            "is_var_subst": "var.subst" in node["captures"],
            "var_name": (
                node["captures"].get("var.set.var", {}).get("text", "") or
                node["captures"].get("var.incr.var", {}).get("text", "") or
                node["captures"].get("var.subst.name", {}).get("text", "")
            ),
            "array_op": node["captures"].get("var.array.op", {}).get("text", ""),
            "has_value": (
                ("var.set" in node["captures"] and "var.set.value" in node["captures"] and node["captures"].get("var.set.value", {}).get("text", "") != "") or
                ("var.incr" in node["captures"] and "var.incr.value" in node["captures"] and node["captures"].get("var.incr.value", {}).get("text", "") != "")
            ),
            "var_op_type": (
                "set" if "var.set" in node["captures"] else
                "array_operation" if "var.array" in node["captures"] else
                "increment_append" if "var.incr" in node["captures"] else
                "substitution" if "var.subst" in node["captures"] else
                "unknown"
            )
        }
    },
    
    "namespaces": {
        "pattern": """
        [
            (command
                name: (_) @ns.def.name {
                    match: "^namespace$"
                }
                argument: (word) @ns.def.op {
                    match: "^eval$"
                }
                argument: [(word) (quoted_word)] @ns.def.ns_name
                argument: (braced_word) @ns.def.body) @ns.def,
                
            (command
                name: (_) @ns.import.name {
                    match: "^namespace$"
                }
                argument: (word) @ns.import.op {
                    match: "^import$"
                }
                argument: (_)+ @ns.import.args) @ns.import,
                
            (command
                name: (_) @ns.export.name {
                    match: "^namespace$"
                }
                argument: (word) @ns.export.op {
                    match: "^export$"
                }
                argument: (_)+ @ns.export.args) @ns.export,
                
            (command
                name: (_) @ns.current.name {
                    match: "^namespace$"
                }
                argument: (word) @ns.current.op {
                    match: "^(current|qualifiers|parent)$"
                }
                argument: (_)* @ns.current.args) @ns.current
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "namespaces",
            "is_namespace_def": "ns.def" in node["captures"],
            "is_namespace_import": "ns.import" in node["captures"],
            "is_namespace_export": "ns.export" in node["captures"],
            "is_namespace_util": "ns.current" in node["captures"],
            "namespace_name": node["captures"].get("ns.def.ns_name", {}).get("text", ""),
            "namespace_op": (
                node["captures"].get("ns.def.op", {}).get("text", "") or
                node["captures"].get("ns.import.op", {}).get("text", "") or
                node["captures"].get("ns.export.op", {}).get("text", "") or
                node["captures"].get("ns.current.op", {}).get("text", "")
            ),
            "namespace_type": (
                "definition" if "ns.def" in node["captures"] else
                "import" if "ns.import" in node["captures"] else
                "export" if "ns.export" in node["captures"] else
                "utility" if "ns.current" in node["captures"] else
                "unknown"
            )
        }
    }
}

TCL_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "command": QueryPattern(
                pattern="""
                (command
                    name: (_) @syntax.command.name
                    argument: (_)* @syntax.command.arg) @syntax.command
                """,
                extract=lambda node: {
                    "name": node["captures"].get("syntax.command.name", {}).get("text", ""),
                    "arg_count": len([arg for arg in node["captures"].get("syntax.command.arg", [])])
                }
            ),
            
            "procedure": QueryPattern(
                pattern="""
                (command
                    name: (_) @syntax.proc.cmd {
                        match: "^proc$"
                    }
                    argument: (_) @syntax.proc.name
                    argument: (braced_word) @syntax.proc.params
                    argument: (braced_word) @syntax.proc.body) @syntax.proc
                """,
                extract=lambda node: {
                    "name": node["captures"].get("syntax.proc.name", {}).get("text", ""),
                    "params": node["captures"].get("syntax.proc.params", {}).get("text", "")
                }
            )
        }
    },

    PatternCategory.SEMANTICS: {
        PatternPurpose.UNDERSTANDING: {
            "variable": QueryPattern(
                pattern="""
                [
                    (command
                        name: (_) @semantics.variable.set {
                            match: "^set$"
                        }
                        argument: (_) @semantics.variable.name
                        argument: (_)? @semantics.variable.value) @semantics.variable.assignment,
                    
                    (variable_substitution
                        name: (_) @semantics.variable.reference) @semantics.variable.usage
                ]
                """,
                extract=lambda node: {
                    "name": node["captures"].get("semantics.variable.name", {}).get("text", "") or
                           node["captures"].get("semantics.variable.reference", {}).get("text", ""),
                    "type": "assignment" if "semantics.variable.assignment" in node["captures"] else "usage"
                }
            )
        }
    },

    PatternCategory.STRUCTURE: {
        PatternPurpose.UNDERSTANDING: {
            "namespace": QueryPattern(
                pattern="""
                (command
                    name: (_) @structure.namespace.cmd {
                        match: "^namespace$"
                    }
                    argument: (word) @structure.namespace.op {
                        match: "^eval$"
                    }
                    argument: (_) @structure.namespace.name
                    argument: (braced_word) @structure.namespace.body) @structure.namespace
                """,
                extract=lambda node: {
                    "name": node["captures"].get("structure.namespace.name", {}).get("text", "")
                }
            )
        }
    },

    PatternCategory.DOCUMENTATION: {
        PatternPurpose.UNDERSTANDING: {
            "comment": QueryPattern(
                pattern="""
                [
                    (comment) @documentation.comment
                ]
                """,
                extract=lambda node: {
                    "text": node["captures"].get("documentation.comment", {}).get("text", "")
                }
            )
        }
    },

    PatternCategory.LEARNING: {
        PatternPurpose.SCRIPTING: {
            "procedural_patterns": QueryPattern(
                pattern="""
                [
                    (command
                        name: (_) @proc.def.name {
                            match: "^proc$"
                        }
                        argument: [(braced_word) (quoted_word)] @proc.def.name_arg
                        argument: (braced_word
                            (word)* @proc.def.param) @proc.def.params
                        argument: (braced_word) @proc.def.body) @proc.def,
                        
                    (command
                        name: (_) @proc.call.name
                        argument: (_)* @proc.call.arg) @proc.call {
                        filter: { @proc.call.name is not null && @proc.call.name !~ "^(proc|if|while|for|foreach|switch|set)$" }
                    },
                        
                    (command
                        name: (_) @proc.return.name {
                            match: "^return$"
                        }
                        argument: (_)? @proc.return.value) @proc.return,
                        
                    (command
                        name: (_) @proc.uplevel.name {
                            match: "^uplevel$"
                        }
                        argument: (_)+ @proc.uplevel.arg) @proc.uplevel
                ]
                """,
                extract=lambda node: {
                    "pattern_type": "procedural_patterns",
                    "is_proc_def": "proc.def" in node["captures"],
                    "is_proc_call": "proc.call" in node["captures"],
                    "is_return": "proc.return" in node["captures"],
                    "is_uplevel": "proc.uplevel" in node["captures"],
                    "proc_name": node["captures"].get("proc.def.name_arg", {}).get("text", "") if "proc.def" in node["captures"] else node["captures"].get("proc.call.name", {}).get("text", ""),
                    "num_params": len([param for param in node["captures"].get("proc.def.param", [])]) if "proc.def.params" in node["captures"] else 0,
                    "num_args": len([arg for arg in node["captures"].get("proc.call.arg", [])]) if "proc.call" in node["captures"] else 0,
                    "has_return_value": "proc.return.value" in node["captures"] and node["captures"].get("proc.return.value", {}).get("text", "") != "",
                    "proc_type": (
                        "definition" if "proc.def" in node["captures"] else
                        "call" if "proc.call" in node["captures"] else
                        "return" if "proc.return" in node["captures"] else
                        "uplevel" if "proc.uplevel" in node["captures"] else
                        "unknown"
                    )
                }
            )
        }
    },

    "REPOSITORY_LEARNING": TCL_PATTERNS_FOR_LEARNING
} 