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