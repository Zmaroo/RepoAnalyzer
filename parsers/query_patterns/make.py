"""Query patterns for Makefile files."""

from parsers.file_classification import FileType
from .common import COMMON_PATTERNS

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
    }
}