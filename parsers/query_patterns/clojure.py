"""Tree-sitter patterns for Clojure programming language."""

from parsers.types import (
    FileType, PatternCategory, PatternPurpose,
    QueryPattern, PatternDefinition
)
from .common import COMMON_PATTERNS

CLOJURE_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "function": QueryPattern(
                pattern="""
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
                extract=lambda node: {
                    "name": node["captures"].get("syntax.function.name", {}).get("text", "") or
                           node["captures"].get("syntax.macro.name", {}).get("text", ""),
                    "type": "macro" if "syntax.macro.def" in node["captures"] else "function"
                }
            ),
            
            "class": QueryPattern(
                pattern="""
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
                extract=lambda node: {
                    "name": node["captures"].get("syntax.class.name", {}).get("text", ""),
                    "type": node["captures"].get("syntax.class.type", {}).get("text", "")
                }
            )
        }
    },
    
    PatternCategory.SEMANTICS: {
        PatternPurpose.UNDERSTANDING: {
            "variable": QueryPattern(
                pattern="""
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
                extract=lambda node: {
                    "name": node["captures"].get("semantics.var.name", {}).get("text", ""),
                    "type": "defonce" if "defonce" in node["captures"].get("semantics.var.type", {}).get("text", "") else "def"
                }
            )
        }
    },
    
    PatternCategory.STRUCTURE: {
        PatternPurpose.UNDERSTANDING: {
            "namespace": QueryPattern(
                pattern="""
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
                extract=lambda node: {
                    "name": node["captures"].get("structure.ns.name", {}).get("text", ""),
                    "type": node["captures"].get("structure.ns.type", {}).get("text", "")
                }
            )
        }
    },
    
    PatternCategory.DOCUMENTATION: {
        PatternPurpose.UNDERSTANDING: {
            "comments": QueryPattern(
                pattern="""
                [
                    (comment) @documentation.comment,
                    (dis_expr) @documentation.disabled
                ]
                """,
                extract=lambda node: {
                    "text": node["captures"].get("documentation.comment", {}).get("text", "") or
                           node["captures"].get("documentation.disabled", {}).get("text", ""),
                    "type": "comment" if "documentation.comment" in node["captures"] else "disabled"
                }
            )
        }
    },
    
    PatternCategory.LEARNING: {
        PatternPurpose.BEST_PRACTICES: {
            "naming_conventions": QueryPattern(
                pattern="""
                [
                    (sym_lit) @naming.symbol
                ]
                """,
                extract=lambda node: {
                    "type": "naming_convention_pattern",
                    "name": node["node"].text.decode('utf8'),
                    "is_kebab_case": "-" in node["node"].text.decode('utf8') and not "_" in node["node"].text.decode('utf8'),
                    "is_snake_case": "_" in node["node"].text.decode('utf8') and not "-" in node["node"].text.decode('utf8'),
                    "is_camel_case": not ("-" in node["node"].text.decode('utf8') or "_" in node["node"].text.decode('utf8')) and 
                                   any(c.isupper() for c in node["node"].text.decode('utf8'))
                }
            ),
            "function_style": QueryPattern(
                pattern="""
                [
                    (list_lit
                        .
                        (sym_lit) @function.type
                        (#match? @function.type "^(defn|defn-|fn)$")
                        .
                        (sym_lit)? @function.name
                        .
                        (vec_lit) @function.params
                        .
                        (str_lit)? @function.docstring
                        .
                        (_)* @function.body) @function.def
                ]
                """,
                extract=lambda node: {
                    "type": "function_style_pattern",
                    "has_docstring": "function.docstring" in node["captures"],
                    "param_count": len(node["captures"].get("function.params", {}).get("text", "").split()),
                    "is_anonymous": "fn" in node["captures"].get("function.type", {}).get("text", "") and 
                                  not node["captures"].get("function.name", {}).get("text", "")
                }
            )
        },
        PatternPurpose.CODE_ORGANIZATION: {
            "code_structure": QueryPattern(
                pattern="""
                [
                    (list_lit
                        .
                        (sym_lit) @structure.ns.keyword
                        (#eq? @structure.ns.keyword "ns")
                        .
                        (sym_lit) @structure.ns.name
                        .
                        [(list_lit
                            .
                            (kwd_lit) @structure.ns.require.keyword
                            (#eq? @structure.ns.require.keyword ":require")
                            .
                            (_)* @structure.ns.require.specs) @structure.ns.require
                         (list_lit
                            .
                            (kwd_lit) @structure.ns.import.keyword
                            (#eq? @structure.ns.import.keyword ":import")
                            .
                            (_)* @structure.ns.import.specs) @structure.ns.import]*) @structure.ns.def
                ]
                """,
                extract=lambda node: {
                    "type": "code_structure_pattern",
                    "has_requires": "structure.ns.require" in node["captures"],
                    "has_imports": "structure.ns.import" in node["captures"],
                    "namespace": node["captures"].get("structure.ns.name", {}).get("text", "")
                }
            )
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

# Repository learning patterns for Clojure
CLOJURE_PATTERNS_FOR_LEARNING = {
    "naming_conventions": {
        "pattern": """
        [
            (sym_lit) @naming.symbol
        ]
        """,
        "extract": lambda node: {
            "type": "naming_convention_pattern",
            "name": node["node"].text.decode('utf8'),
            "is_kebab_case": "-" in node["node"].text.decode('utf8') and not "_" in node["node"].text.decode('utf8'),
            "is_snake_case": "_" in node["node"].text.decode('utf8') and not "-" in node["node"].text.decode('utf8'),
            "is_camel_case": not ("-" in node["node"].text.decode('utf8') or "_" in node["node"].text.decode('utf8')) and 
                           any(c.isupper() for c in node["node"].text.decode('utf8'))
        }
    },
    
    "function_style": {
        "pattern": """
        [
            (list_lit
                .
                (sym_lit) @function.type
                (#match? @function.type "^(defn|defn-|fn)$")
                .
                (sym_lit)? @function.name
                .
                (vec_lit) @function.params
                .
                (str_lit)? @function.docstring
                .
                (_)* @function.body) @function.def
        ]
        """,
        "extract": lambda node: {
            "type": "function_style_pattern",
            "has_docstring": "function.docstring" in node["captures"],
            "param_count": len(node["captures"].get("function.params", {}).get("text", "").split()),
            "is_anonymous": "fn" in node["captures"].get("function.type", {}).get("text", "") and 
                          not node["captures"].get("function.name", {}).get("text", "")
        }
    },
    
    "code_structure": {
        "pattern": """
        [
            (list_lit
                .
                (sym_lit) @structure.ns.keyword
                (#eq? @structure.ns.keyword "ns")
                .
                (sym_lit) @structure.ns.name
                .
                [(list_lit
                    .
                    (kwd_lit) @structure.ns.require.keyword
                    (#eq? @structure.ns.require.keyword ":require")
                    .
                    (_)* @structure.ns.require.specs) @structure.ns.require
                 (list_lit
                    .
                    (kwd_lit) @structure.ns.import.keyword
                    (#eq? @structure.ns.import.keyword ":import")
                    .
                    (_)* @structure.ns.import.specs) @structure.ns.import]*) @structure.ns.def
        ]
        """,
        "extract": lambda node: {
            "type": "code_structure_pattern",
            "has_requires": "structure.ns.require" in node["captures"],
            "has_imports": "structure.ns.import" in node["captures"],
            "namespace": node["captures"].get("structure.ns.name", {}).get("text", "")
        }
    }
}

# Add the repository learning patterns to the main patterns
CLOJURE_PATTERNS['REPOSITORY_LEARNING'] = CLOJURE_PATTERNS_FOR_LEARNING 