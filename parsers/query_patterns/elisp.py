"""Query patterns for Emacs Lisp files."""

from .common import COMMON_PATTERNS

ELISP_PATTERNS = {
    **COMMON_PATTERNS,  # Keep as fallback for basic patterns
    
    "syntax": {
        "function": {
            "pattern": """
            [
                (function_definition
                    name: (symbol) @syntax.function.name
                    parameters: (_)? @syntax.function.params
                    docstring: (string)? @syntax.function.doc
                    [
                        (bytecode) @syntax.function.bytecode
                        (list) @syntax.function.body
                        (special_form) @syntax.function.special
                    ]*) @syntax.function.def,
                    
                (special_form
                    name: (symbol) @syntax.special.name
                    (#match? @syntax.special.name "^(defun|cl-defun|defsubst)$")
                    parameters: (_)? @syntax.special.params
                    body: (_)* @syntax.special.body) @syntax.special.def
            ]
            """,
            "extract": lambda node: {
                "name": node["captures"].get("syntax.function.name", {}).get("text", ""),
                "type": "function"
            }
        },
        "class": [
            """
            (macro_definition
                name: (symbol) @macro.name
                parameters: (_)? @macro.params
                docstring: (string)? @macro.doc
                [
                    (list) @macro.body
                    (special_form) @macro.special
                ]*) @class
            """
        ]
    },
    "structure": {
        "namespace": [
            """
            (source_file
                [
                    (function_definition) @source.function
                    (macro_definition) @source.macro
                    (special_form) @source.special
                    (list) @source.list
                    (comment) @source.comment
                ]*) @namespace
            """
        ]
    },
    "semantics": {
        "variable": {
            "pattern": """
            [
                (list
                    (symbol) @semantics.var.keyword
                    (#match? @semantics.var.keyword "^(defvar|defconst|defcustom)$")
                    (symbol) @semantics.var.name
                    value: (_)? @semantics.var.value
                    docstring: (string)? @semantics.var.doc) @semantics.var.def
            ]
            """,
            "extract": lambda node: {
                "name": node["captures"].get("semantics.var.name", {}).get("text", ""),
                "type": node["captures"].get("semantics.var.keyword", {}).get("text", "")
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