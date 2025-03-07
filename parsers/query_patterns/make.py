"""Query patterns for Makefile files."""

from parsers.types import (
    FileType, PatternCategory, PatternPurpose,
    QueryPattern, PatternDefinition
)
from .common import COMMON_PATTERNS

MAKE_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "rule": QueryPattern(
                pattern="""
                [
                    (rule
                        targets: (targets) @syntax.rule.targets
                        prerequisites: (prerequisites)? @syntax.rule.prereqs
                        recipe: (recipe)? @syntax.rule.recipe) @syntax.rule.def,
                    (pattern_rule
                        targets: (targets) @syntax.pattern.targets
                        prerequisites: (prerequisites)? @syntax.pattern.prereqs
                        recipe: (recipe)? @syntax.pattern.recipe) @syntax.pattern.def
                ]
                """,
                extract=lambda node: {
                    "type": "pattern_rule" if "syntax.pattern.def" in node["captures"] else "rule",
                    "targets": (
                        node["captures"].get("syntax.pattern.targets", {}).get("text", "") or
                        node["captures"].get("syntax.rule.targets", {}).get("text", "")
                    ),
                    "has_prerequisites": any(
                        key in node["captures"] for key in 
                        ["syntax.pattern.prereqs", "syntax.rule.prereqs"]
                    ),
                    "has_recipe": any(
                        key in node["captures"] for key in 
                        ["syntax.pattern.recipe", "syntax.rule.recipe"]
                    )
                }
            ),
            "variable": QueryPattern(
                pattern="""
                [
                    (variable_assignment
                        name: (_) @syntax.var.name
                        value: (_) @syntax.var.value) @syntax.var.def,
                    (conditional_variable_assignment
                        name: (_) @syntax.var.cond.name
                        value: (_) @syntax.var.cond.value) @syntax.var.cond.def
                ]
                """,
                extract=lambda node: {
                    "type": "variable",
                    "name": (
                        node["captures"].get("syntax.var.name", {}).get("text", "") or
                        node["captures"].get("syntax.var.cond.name", {}).get("text", "")
                    ),
                    "is_conditional": "syntax.var.cond.def" in node["captures"],
                    "has_value": any(
                        key in node["captures"] for key in 
                        ["syntax.var.value", "syntax.var.cond.value"]
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
                    (comment) @documentation.comment.line
                ]
                """,
                extract=lambda node: {
                    "text": node["captures"].get("documentation.comment.line", {}).get("text", ""),
                    "type": "comment"
                }
            )
        }
    },

    PatternCategory.STRUCTURE: {
        PatternPurpose.UNDERSTANDING: {
            "include": QueryPattern(
                pattern="""
                [
                    (include_statement
                        path: (_) @structure.include.path) @structure.include,
                    (conditional_include
                        path: (_) @structure.include.cond.path) @structure.include.cond
                ]
                """,
                extract=lambda node: {
                    "type": "include",
                    "path": (
                        node["captures"].get("structure.include.path", {}).get("text", "") or
                        node["captures"].get("structure.include.cond.path", {}).get("text", "")
                    ),
                    "is_conditional": "structure.include.cond" in node["captures"]
                }
            )
        }
    },

    PatternCategory.LEARNING: {
        PatternPurpose.BEST_PRACTICES: {
            "phony_targets": QueryPattern(
                pattern="""
                [
                    (rule
                        targets: (targets) @learning.phony.targets
                        prerequisites: (prerequisites)? @learning.phony.prereqs) @learning.phony.def
                        (#match? @learning.phony.targets "^\\.PHONY:"),
                    (rule
                        targets: (targets) @learning.phony.target.name
                        (#match-any? @learning.phony.target.name "^(all|clean|install|test|build|dist)$")) @learning.phony.target
                ]
                """,
                extract=lambda node: {
                    "pattern_type": "phony_target",
                    "is_phony_declaration": "learning.phony.def" in node["captures"],
                    "is_common_target": "learning.phony.target" in node["captures"],
                    "target_name": node["captures"].get("learning.phony.target.name", {}).get("text", ""),
                    "has_prerequisites": "learning.phony.prereqs" in node["captures"]
                }
            )
        },
        PatternPurpose.VARIABLES: {
            "variable_usage": QueryPattern(
                pattern="""
                [
                    (variable_reference
                        name: (_) @learning.var.ref.name) @learning.var.ref,
                    (shell_function
                        arguments: (_) @learning.var.shell.args) @learning.var.shell,
                    (wildcard_function
                        arguments: (_) @learning.var.wildcard.args) @learning.var.wildcard
                ]
                """,
                extract=lambda node: {
                    "pattern_type": "variable_usage",
                    "is_reference": "learning.var.ref" in node["captures"],
                    "uses_shell": "learning.var.shell" in node["captures"],
                    "uses_wildcard": "learning.var.wildcard" in node["captures"],
                    "variable_name": node["captures"].get("learning.var.ref.name", {}).get("text", ""),
                    "function_args": (
                        node["captures"].get("learning.var.shell.args", {}).get("text", "") or
                        node["captures"].get("learning.var.wildcard.args", {}).get("text", "")
                    )
                }
            )
        },
        PatternPurpose.DEPENDENCIES: {
            "dependency_patterns": QueryPattern(
                pattern="""
                [
                    (pattern_rule
                        targets: (targets) @learning.dep.pattern.targets
                        prerequisites: (prerequisites) @learning.dep.pattern.prereqs) @learning.dep.pattern,
                    (rule
                        targets: (targets) @learning.dep.auto.targets
                        prerequisites: (prerequisites) @learning.dep.auto.prereqs) @learning.dep.auto
                        (#match? @learning.dep.auto.targets "%.o: %.c")
                ]
                """,
                extract=lambda node: {
                    "pattern_type": "dependency_pattern",
                    "is_pattern_rule": "learning.dep.pattern" in node["captures"],
                    "is_auto_dependency": "learning.dep.auto" in node["captures"],
                    "target_pattern": (
                        node["captures"].get("learning.dep.pattern.targets", {}).get("text", "") or
                        node["captures"].get("learning.dep.auto.targets", {}).get("text", "")
                    ),
                    "prerequisite_pattern": (
                        node["captures"].get("learning.dep.pattern.prereqs", {}).get("text", "") or
                        node["captures"].get("learning.dep.auto.prereqs", {}).get("text", "")
                    )
                }
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
    
    "REPOSITORY_LEARNING": MAKE_PATTERNS
}