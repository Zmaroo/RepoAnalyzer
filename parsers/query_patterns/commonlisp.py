"""Query patterns for Common Lisp files."""

from .common import COMMON_PATTERNS

COMMONLISP_PATTERNS = {
    **COMMON_PATTERNS,  # Keep as fallback for basic patterns
    
    "syntax": {
        "function": {
            "pattern": """
            [
                (list
                    (symbol) @syntax.function.keyword
                    (symbol) @syntax.function.name
                    (list) @syntax.function.params
                    (_)* @syntax.function.body) @syntax.function.def
                (#eq? @syntax.function.keyword "defun"),
                
                (list
                    (symbol) @syntax.lambda.keyword
                    (list) @syntax.lambda.params
                    (_)* @syntax.lambda.body) @syntax.lambda.def
                (#eq? @syntax.lambda.keyword "lambda")
            ]
            """,
            "extract": lambda node: {
                "name": node["captures"].get("syntax.function.name", {}).get("text", ""),
                "type": "function" if "syntax.function.def" in node["captures"] else "lambda"
            }
        },
        
        "macro": {
            "pattern": """
            [
                (list
                    (symbol) @syntax.macro.keyword
                    (symbol) @syntax.macro.name
                    (list) @syntax.macro.params
                    (_)* @syntax.macro.body) @syntax.macro.def
                (#eq? @syntax.macro.keyword "defmacro")
            ]
            """,
            "extract": lambda node: {
                "name": node["captures"].get("syntax.macro.name", {}).get("text", "")
            }
        }
    },
    
    "semantics": {
        "expression": {
            "pattern": """
            [
                (list
                    (symbol) @semantics.expr.keyword
                    (_)* @semantics.expr.body) @semantics.expr.def
                (#match? @semantics.expr.keyword "^(defun|lambda|defmacro)$")
            ]
            """,
            "extract": lambda node: {
                "type": node["captures"].get("semantics.expr.keyword", {}).get("text", "")
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

# Repository learning patterns for Common Lisp
COMMONLISP_PATTERNS_FOR_LEARNING = {
    "naming_conventions": {
        "pattern": """
        [
            (symbol) @naming.symbol
        ]
        """,
        "extract": lambda node: {
            "type": "naming_convention_pattern",
            "name": node["node"].text.decode('utf8'),
            "is_kebab_case": "-" in node["node"].text.decode('utf8'),
            "is_uppercase": all(c.isupper() or not c.isalpha() for c in node["node"].text.decode('utf8')),
            "has_asterisk_wrapping": (node["node"].text.decode('utf8').startswith("*") and 
                                     node["node"].text.decode('utf8').endswith("*")),
            "is_predicate": node["node"].text.decode('utf8').endswith("-P") or node["node"].text.decode('utf8').endswith("P")
        }
    },
    
    "code_organization": {
        "pattern": """
        [
            (list
                (symbol) @organization.keyword
                (#match? @organization.keyword "^(defpackage|in-package)$")
                (_)* @organization.args) @organization.def
        ]
        """,
        "extract": lambda node: {
            "type": "code_organization_pattern",
            "keyword": node["captures"].get("organization.keyword", {}).get("text", ""),
            "is_package_def": node["captures"].get("organization.keyword", {}).get("text", "") == "defpackage",
            "is_package_use": node["captures"].get("organization.keyword", {}).get("text", "") == "in-package"
        }
    },
    
    "error_handling": {
        "pattern": """
        [
            (list
                (symbol) @error.keyword
                (#match? @error.keyword "^(handler-case|handler-bind|ignore-errors|unwind-protect)$")
                (_)* @error.body) @error.def
        ]
        """,
        "extract": lambda node: {
            "type": "error_handling_pattern",
            "method": node["captures"].get("error.keyword", {}).get("text", ""),
            "is_handler_case": node["captures"].get("error.keyword", {}).get("text", "") == "handler-case",
            "is_ignore_errors": node["captures"].get("error.keyword", {}).get("text", "") == "ignore-errors",
            "is_unwind_protect": node["captures"].get("error.keyword", {}).get("text", "") == "unwind-protect"
        }
    }
}

# Add the repository learning patterns to the main patterns
COMMONLISP_PATTERNS['REPOSITORY_LEARNING'] = COMMONLISP_PATTERNS_FOR_LEARNING 