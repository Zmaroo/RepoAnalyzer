"""Query patterns for Emacs Lisp files."""

from .common import COMMON_PATTERNS

ELISP_PATTERNS_FOR_LEARNING = {
    "naming_conventions": {
        "pattern": """
        [
            (function_definition name: (symbol) @naming.function.name) @naming.function
            (special_form 
                name: (symbol) @naming.special.keyword 
                (#match? @naming.special.keyword "^(defun|cl-defun|defsubst)$") 
                (_) @naming.special.name) @naming.special
            (macro_definition name: (symbol) @naming.macro.name) @naming.macro
            (list 
                (symbol) @naming.var.keyword
                (#match? @naming.var.keyword "^(defvar|defconst|defcustom)$")
                (symbol) @naming.var.name) @naming.var
        ]
        """,
        "extract": lambda node: {
            "function_name": node["captures"].get("naming.function.name", {}).get("text", ""),
            "macro_name": node["captures"].get("naming.macro.name", {}).get("text", ""),
            "var_name": node["captures"].get("naming.var.name", {}).get("text", ""),
            "uses_lisp_case": any(
                "-" in name for name in [
                    node["captures"].get("naming.function.name", {}).get("text", ""),
                    node["captures"].get("naming.macro.name", {}).get("text", ""),
                    node["captures"].get("naming.var.name", {}).get("text", "")
                ] if name
            ),
            "uses_prefix": any(
                name and name.startswith(("my-", "company-", "project-")) 
                for name in [
                    node["captures"].get("naming.function.name", {}).get("text", ""),
                    node["captures"].get("naming.macro.name", {}).get("text", ""),
                    node["captures"].get("naming.var.name", {}).get("text", "")
                ]
            )
        }
    },
    "code_organization": {
        "pattern": """
        [
            (list 
                (symbol) @org.provide.keyword 
                (#match? @org.provide.keyword "^provide$") 
                (_) @org.provide.name) @org.provide
            (list 
                (symbol) @org.require.keyword 
                (#match? @org.require.keyword "^require$") 
                (_) @org.require.name) @org.require
            (list 
                (symbol) @org.feature.keyword 
                (#match? @org.feature.keyword "^(feature|featurep)$") 
                (_) @org.feature.name) @org.feature
            (list 
                (symbol) @org.package.keyword 
                (#match? @org.package.keyword "^(package-initialize|use-package)$") 
                [(_) (_)+]? @org.package.args) @org.package
        ]
        """,
        "extract": lambda node: {
            "uses_provide": bool(node["captures"].get("org.provide.name", {}).get("text", "")),
            "requires_feature": bool(node["captures"].get("org.require.name", {}).get("text", "")),
            "uses_package_system": bool(node["captures"].get("org.package.keyword", {}).get("text", "")),
            "feature_name": node["captures"].get("org.feature.name", {}).get("text", ""),
            "package_system": node["captures"].get("org.package.keyword", {}).get("text", "")
        }
    },
    "elisp_idioms": {
        "pattern": """
        [
            (list 
                (symbol) @idiom.interactive.keyword 
                (#match? @idiom.interactive.keyword "^interactive$")
                (_)* @idiom.interactive.args) @idiom.interactive
            (list 
                (symbol) @idiom.let.keyword 
                (#match? @idiom.let.keyword "^(let|let\\*|lexical-let)$")
                (_) @idiom.let.bindings
                (_)+ @idiom.let.body) @idiom.let
            (list 
                (symbol) @idiom.hook.keyword 
                (#match? @idiom.hook.keyword "^(add-hook|remove-hook)$")
                (_)+ @idiom.hook.args) @idiom.hook
            (list 
                (symbol) @idiom.advice.keyword 
                (#match? @idiom.advice.keyword "^(advice-add|define-advice)$")
                (_)+ @idiom.advice.args) @idiom.advice
            (list 
                (symbol) @idiom.mode.keyword 
                (#match? @idiom.mode.keyword ".*-mode$")
                (_)* @idiom.mode.args) @idiom.mode
        ]
        """,
        "extract": lambda node: {
            "uses_interactive": bool(node["captures"].get("idiom.interactive.keyword", {}).get("text", "")),
            "uses_let_binding": bool(node["captures"].get("idiom.let.keyword", {}).get("text", "")),
            "manages_hooks": bool(node["captures"].get("idiom.hook.keyword", {}).get("text", "")),
            "uses_advice": bool(node["captures"].get("idiom.advice.keyword", {}).get("text", "")),
            "defines_mode": bool(node["captures"].get("idiom.mode.keyword", {}).get("text", ""))
        }
    }
}

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
    },
    "REPOSITORY_LEARNING": ELISP_PATTERNS_FOR_LEARNING
} 