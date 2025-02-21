"""Query patterns for Elixir files."""

from .common import COMMON_PATTERNS

ELIXIR_PATTERNS = {
    **COMMON_PATTERNS,  # Keep as fallback for basic patterns
    
    "syntax": {
        "function": {
            "pattern": """
            [
                (stab_clause
                    left: (arguments
                        [
                            (identifier) @syntax.function.name
                            (binary_operator) @syntax.function.operator
                        ]) @syntax.function.params
                    right: (body) @syntax.function.body) @syntax.function.def,
                    
                (call
                    target: (identifier) @syntax.macro.name
                    (#match? @syntax.macro.name "^(def|defp|defmacro|defmacrop)$")
                    arguments: (arguments
                        (identifier) @syntax.function.name
                        parameters: (_)? @syntax.function.params
                        body: (do_block)? @syntax.function.body)) @syntax.macro.def
            ]
            """,
            "extract": lambda node: {
                "name": node["captures"].get("syntax.function.name", {}).get("text", ""),
                "type": "function"
            }
        },
        "class": [
            """
            (do_block
                (stab_clause)* @block.clauses) @class
            """
        ]
    },
    "structure": {
        "namespace": [
            """
            (block
                (_)* @block.content) @namespace
            """
        ]
    },
    "semantics": {
        "variable": [
            """
            (string
                quoted_content: (_)? @string.content
                interpolation: (_)* @string.interpolation) @variable
            """
        ],
        "module": {
            "pattern": """
            [
                (call
                    target: (identifier) @semantics.module.keyword
                    (#match? @semantics.module.keyword "^(defmodule)$")
                    arguments: (arguments
                        (alias) @semantics.module.name
                        (do_block)? @semantics.module.body)) @semantics.module.def
            ]
            """,
            "extract": lambda node: {
                "name": node["captures"].get("semantics.module.name", {}).get("text", ""),
                "type": "module"
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