"""Query patterns for Makefile files."""

from parsers.types import FileType
from .common import COMMON_PATTERNS

MAKEFILE_PATTERNS_FOR_LEARNING = {
    "rule_patterns": {
        "pattern": """
        [
            (rule
                targets: (targets) @rule.targets
                prerequisites: (prerequisites)? @rule.prereqs
                recipe: (recipe)? @rule.recipe) @rule.def,
                
            (special_target
                name: (_) @rule.special.name
                recipe: (recipe)? @rule.special.recipe) @rule.special,
                
            (pattern_rule
                targets: (targets) @rule.pattern.targets
                prerequisites: (prerequisites)? @rule.pattern.prereqs
                recipe: (recipe)? @rule.pattern.recipe) @rule.pattern
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "rule_organization",
            "is_standard_rule": "rule.def" in node["captures"] and "rule.special" not in node["captures"] and "rule.pattern" not in node["captures"],
            "is_special_target": "rule.special" in node["captures"],
            "is_pattern_rule": "rule.pattern" in node["captures"],
            "target_name": (
                node["captures"].get("rule.targets", {}).get("text", "") or
                node["captures"].get("rule.special.name", {}).get("text", "") or
                node["captures"].get("rule.pattern.targets", {}).get("text", "")
            ),
            "has_prerequisites": (
                "rule.prereqs" in node["captures"] and node["captures"].get("rule.prereqs", {}).get("text", "") or
                "rule.pattern.prereqs" in node["captures"] and node["captures"].get("rule.pattern.prereqs", {}).get("text", "")
            ),
            "is_phony_target": ".PHONY" in (node["captures"].get("rule.special.name", {}).get("text", "") or ""),
            "uses_pattern_matching": "%" in (node["captures"].get("rule.pattern.targets", {}).get("text", "") or "")
        }
    },
    
    "variable_usage": {
        "pattern": """
        [
            (variable_definition
                name: (_) @var.def.name
                value: (_) @var.def.value) @var.def,
                
            (shell_variable
                name: (_) @var.shell.name
                value: (_) @var.shell.value) @var.shell,
                
            (conditional_variable
                name: (_) @var.cond.name
                value: (_) @var.cond.value) @var.cond,
                
            (variable_reference) @var.ref
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "variable_usage",
            "is_variable_definition": "var.def" in node["captures"],
            "is_shell_variable": "var.shell" in node["captures"],
            "is_conditional_variable": "var.cond" in node["captures"],
            "is_variable_reference": "var.ref" in node["captures"],
            "variable_name": (
                node["captures"].get("var.def.name", {}).get("text", "") or
                node["captures"].get("var.shell.name", {}).get("text", "") or
                node["captures"].get("var.cond.name", {}).get("text", "")
            ),
            "assignment_type": (
                "simple" if "var.def" in node["captures"] and "=" in node["captures"].get("var.def", {}).get("text", "") else
                "recursive" if "var.def" in node["captures"] and ":=" in node["captures"].get("var.def", {}).get("text", "") else
                "conditional" if "var.def" in node["captures"] and "?=" in node["captures"].get("var.def", {}).get("text", "") else
                "append" if "var.def" in node["captures"] and "+=" in node["captures"].get("var.def", {}).get("text", "") else
                "shell" if "var.shell" in node["captures"] else
                "other"
            ),
            "uses_automatic_variable": any(
                autovar in (node["captures"].get("var.ref", {}).get("text", "") or "")
                for autovar in ["$@", "$<", "$^", "$*", "$+", "$|", "$?"]
            )
        }
    },
    
    "conditional_logic": {
        "pattern": """
        [
            (ifeq
                condition: (_) @cond.ifeq.condition
                consequence: (_) @cond.ifeq.body) @cond.ifeq,
                
            (ifneq
                condition: (_) @cond.ifneq.condition
                consequence: (_) @cond.ifneq.body) @cond.ifneq,
                
            (ifdef
                condition: (_) @cond.ifdef.condition
                consequence: (_) @cond.ifdef.body) @cond.ifdef,
                
            (ifndef
                condition: (_) @cond.ifndef.condition
                consequence: (_) @cond.ifndef.body) @cond.ifndef,
                
            (else) @cond.else,
            
            (endif) @cond.endif
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "conditional_logic",
            "condition_type": (
                "equal" if "cond.ifeq" in node["captures"] else
                "not_equal" if "cond.ifneq" in node["captures"] else
                "defined" if "cond.ifdef" in node["captures"] else
                "not_defined" if "cond.ifndef" in node["captures"] else
                "else" if "cond.else" in node["captures"] else
                "endif" if "cond.endif" in node["captures"] else
                "other"
            ),
            "condition_expression": (
                node["captures"].get("cond.ifeq.condition", {}).get("text", "") or
                node["captures"].get("cond.ifneq.condition", {}).get("text", "") or
                node["captures"].get("cond.ifdef.condition", {}).get("text", "") or
                node["captures"].get("cond.ifndef.condition", {}).get("text", "")
            ),
            "checks_variable": any(
                key in node["captures"] for key in ["cond.ifdef", "cond.ifndef"]
            ),
            "compares_values": any(
                key in node["captures"] for key in ["cond.ifeq", "cond.ifneq"]
            ),
            "conditional_complexity": (
                "simple" if len([k for k in node["captures"].keys() if k.startswith("cond.")]) <= 2 else
                "moderate" if len([k for k in node["captures"].keys() if k.startswith("cond.")]) <= 4 else
                "complex"
            )
        }
    },
    
    "build_optimization": {
        "pattern": """
        [
            (special_target
                name: (_) @opt.special.name
                (#match? @opt.special.name "^\\.PHONY|\\.PRECIOUS|\\.INTERMEDIATE|\\.SECONDARY|\\.DELETE_ON_ERROR|\\.SILENT|\\.IGNORE|\\.ONESHELL|\\.NOTPARALLEL|\\.EXPORT_ALL_VARIABLES$")
                prerequisites: (_)? @opt.special.prereqs) @opt.special,
                
            (variable_definition
                name: (_) @opt.var.name
                (#match? @opt.var.name "^MAKEFLAGS|SHELL|PATH|VPATH|\\.SHELLFLAGS$")
                value: (_) @opt.var.value) @opt.var,
                
            (recipe_line
                text: (_) @opt.recipe.text) @opt.recipe
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "build_optimization",
            "uses_special_target": "opt.special" in node["captures"],
            "uses_optimization_variable": "opt.var" in node["captures"],
            "special_target_name": node["captures"].get("opt.special.name", {}).get("text", ""),
            "optimization_variable": node["captures"].get("opt.var.name", {}).get("text", ""),
            "uses_parallel_flag": "-j" in (node["captures"].get("opt.var.value", {}).get("text", "") or ""),
            "uses_silent_flag": "@" in (node["captures"].get("opt.recipe.text", {}).get("text", "") or ""),
            "optimization_type": (
                "explicit_dependencies" if "opt.special" in node["captures"] and ".PHONY" in node["captures"].get("opt.special.name", {}).get("text", "") else
                "parallelism" if "opt.var" in node["captures"] and "MAKEFLAGS" in node["captures"].get("opt.var.name", {}).get("text", "") and "-j" in (node["captures"].get("opt.var.value", {}).get("text", "") or "") else
                "intermediate_files" if "opt.special" in node["captures"] and any(
                    target in node["captures"].get("opt.special.name", {}).get("text", "")
                    for target in [".INTERMEDIATE", ".SECONDARY", ".PRECIOUS"]
                ) else
                "other"
            )
        }
    }
}

MAKEFILE_PATTERNS = {
    **COMMON_PATTERNS,
    
    "syntax": {
        "function": {
            "pattern": """
            (rule
                targets: (targets) @syntax.function.name
                prerequisites: (prerequisites)? @syntax.function.params
                recipe: (recipe)? @syntax.function.body) @syntax.function.def
            """
        },
        "conditional": {
            "pattern": """
            [
                (ifeq
                    condition: (_) @syntax.conditional.if.condition
                    consequence: (_) @syntax.conditional.if.body) @syntax.conditional.if,
                (ifneq
                    condition: (_) @syntax.conditional.ifnot.condition
                    consequence: (_) @syntax.conditional.ifnot.body) @syntax.conditional.ifnot,
                (ifdef
                    condition: (_) @syntax.conditional.ifdef.condition
                    consequence: (_) @syntax.conditional.ifdef.body) @syntax.conditional.ifdef
            ]
            """
        }
    },

    "semantics": {
        "variable": {
            "pattern": """
            [
                (variable_definition
                    name: (_) @semantics.variable.name
                    value: (_) @semantics.variable.value) @semantics.variable.def,
                (shell_variable
                    name: (_) @semantics.variable.shell.name
                    value: (_) @semantics.variable.shell.value) @semantics.variable.shell
            ]
            """
        }
    },

    "documentation": {
        "comment": {
            "pattern": """
            (comment) @documentation.comment
            """
        }
    },

    "structure": {
        "include": {
            "pattern": """
            (include_statement
                path: (_) @structure.include.path) @structure.include.def
            """
        }
    },
    
    "REPOSITORY_LEARNING": MAKEFILE_PATTERNS_FOR_LEARNING
}