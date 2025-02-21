"""Tree-sitter patterns for Clojure programming language."""

from .common import COMMON_PATTERNS

CLOJURE_PATTERNS = {
    **COMMON_PATTERNS,  # Keep as fallback for basic patterns
    
    "syntax": {
        "function": {
            "pattern": """
            [
                (list_lit
                    .
                    (sym_lit) @syntax.function.type
                    (#match? @syntax.function.type "^(defn|defn-|fn)$")
                    .
                    (sym_lit) @syntax.function.name
                    .
                    (vec_lit)? @syntax.function.params
                    .
                    (_)* @syntax.function.body) @syntax.function.def,
                
                (list_lit
                    .
                    (sym_lit) @syntax.macro.type
                    (#match? @syntax.macro.type "^defmacro$")
                    .
                    (sym_lit) @syntax.macro.name
                    .
                    (vec_lit)? @syntax.macro.params
                    .
                    (_)* @syntax.macro.body) @syntax.macro.def
            ]
            """,
            "extract": lambda node: {
                "name": node["captures"].get("syntax.function.name", {}).get("text", "") or
                       node["captures"].get("syntax.macro.name", {}).get("text", ""),
                "type": "macro" if "syntax.macro.def" in node["captures"] else "function"
            }
        },
        
        "class": {
            "pattern": """
            [
                (list_lit
                    .
                    (sym_lit) @syntax.class.type
                    (#match? @syntax.class.type "^(defrecord|defprotocol|deftype)$")
                    .
                    (sym_lit) @syntax.class.name
                    .
                    [(vec_lit) @syntax.class.fields
                     (_)* @syntax.class.body]) @syntax.class.def
            ]
            """,
            "extract": lambda node: {
                "name": node["captures"].get("syntax.class.name", {}).get("text", ""),
                "type": node["captures"].get("syntax.class.type", {}).get("text", "")
            }
        }
    },
    
    "semantics": {
        "variable": {
            "pattern": """
            [
                (list_lit
                    .
                    (sym_lit) @semantics.var.type
                    (#match? @semantics.var.type "^(def|defonce)$")
                    .
                    (sym_lit) @semantics.var.name
                    .
                    (_)? @semantics.var.value) @semantics.var.def
            ]
            """,
            "extract": lambda node: {
                "name": node["captures"].get("semantics.var.name", {}).get("text", ""),
                "type": "defonce" if "defonce" in node["captures"].get("semantics.var.type", {}).get("text", "") else "def"
            }
        }
    },
    
    "structure": {
        "namespace": {
            "pattern": """
            [
                (list_lit
                    .
                    (sym_lit) @structure.ns.type
                    (#match? @structure.ns.type "^(ns|in-ns)$")
                    .
                    [(sym_lit) @structure.ns.name
                     (quote) @structure.ns.quoted]
                    .
                    (_)* @structure.ns.body) @structure.ns.def
            ]
            """,
            "extract": lambda node: {
                "name": node["captures"].get("structure.ns.name", {}).get("text", ""),
                "type": node["captures"].get("structure.ns.type", {}).get("text", "")
            }
        }
    },
    
    "documentation": {
        "comments": {
            "pattern": """
            [
                (comment) @documentation.comment,
                (dis_expr) @documentation.disabled
            ]
            """,
            "extract": lambda node: {
                "text": node["captures"].get("documentation.comment", {}).get("text", "") or
                       node["captures"].get("documentation.disabled", {}).get("text", ""),
                "type": "comment" if "documentation.comment" in node["captures"] else "disabled"
            }
        }
    }
}

# Additional metadata for pattern categories
PATTERN_METADATA = {
    "syntax": {
        "function": {
            "contains": ["params", "body", "docstring"],
            "contained_by": ["namespace"]
        },
        "class": {
            "contains": ["fields", "methods", "protocols", "implementations", "docstring"],
            "contained_by": ["namespace"]
        }
    },
    "structure": {
        "namespace": {
            "contains": ["import", "function", "class", "variable"],
            "contained_by": []
        },
        "import": {
            "contains": [],
            "contained_by": ["namespace"]
        }
    },
    "semantics": {
        "variable": {
            "contains": ["value"],
            "contained_by": ["namespace", "function"]
        },
        "expression": {
            "contains": ["forms", "branches"],
            "contained_by": ["function", "variable"]
        }
    },
    "documentation": {
        "docstring": {
            "contains": [],
            "contained_by": ["function", "class", "namespace"]
        },
        "comment": {
            "contains": [],
            "contained_by": ["function", "class", "namespace", "expression"]
        }
    }
} 