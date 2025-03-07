"""
Query patterns for Racket files.
"""

from parsers.types import (
    FileType, PatternCategory, PatternPurpose,
    QueryPattern, PatternDefinition
)
from .common import COMMON_PATTERNS

RACKET_PATTERNS_FOR_LEARNING = {
    "functional_patterns": {
        "pattern": """
        [
            (list_lit
                .
                (sym_lit) @func.def.type
                (#match? @func.def.type "^(define|lambda)$")
                .
                [(sym_lit) (list_lit)] @func.def.name
                .
                (list_lit)? @func.def.params
                .
                (_)* @func.def.body) @func.def,
                
            (list_lit
                .
                (sym_lit) @func.app.type
                (#match? @func.app.type "^(map|filter|foldl|foldr|andmap|ormap|apply)$")
                .
                (_)* @func.app.args) @func.app
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "functional_patterns",
            "is_function_definition": "func.def" in node["captures"],
            "is_function_application": "func.app" in node["captures"],
            "function_name": node["captures"].get("func.def.name", {}).get("text", "") if "func.def.name" in node["captures"] else 
                           node["captures"].get("func.app.type", {}).get("text", ""),
            "definition_type": node["captures"].get("func.def.type", {}).get("text", ""),
            "param_count": len((node["captures"].get("func.def.params", {}).get("text", "") or "").split(" ")) 
                          if node["captures"].get("func.def.params", {}).get("text", "") else 0,
            "higher_order_function": node["captures"].get("func.app.type", {}).get("text", "")
        }
    },
    
    "macro_patterns": {
        "pattern": """
        [
            (list_lit
                .
                (sym_lit) @macro.def.type
                (#match? @macro.def.type "^(define-syntax|define-syntax-rule|syntax-rules|define-macro)$")
                .
                (sym_lit) @macro.def.name
                .
                (_)* @macro.def.body) @macro.def,
                
            (list_lit
                .
                (sym_lit) @macro.pattern.type
                (#match? @macro.pattern.type "^(syntax-case|syntax|quasisyntax)$")
                .
                (_)* @macro.pattern.body) @macro.pattern
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "macro_patterns",
            "is_macro_definition": "macro.def" in node["captures"],
            "is_pattern_matching": "macro.pattern" in node["captures"],
            "macro_name": node["captures"].get("macro.def.name", {}).get("text", ""),
            "macro_definition_type": node["captures"].get("macro.def.type", {}).get("text", ""),
            "pattern_matching_type": node["captures"].get("macro.pattern.type", {}).get("text", ""),
            "macro_style": (
                "syntax_rules" if "macro.def.type" in node["captures"] and 
                                node["captures"].get("macro.def.type", {}).get("text", "") == "syntax-rules" else
                "syntax_case" if "macro.pattern.type" in node["captures"] and 
                                node["captures"].get("macro.pattern.type", {}).get("text", "") == "syntax-case" else
                "procedural_macro" if "macro.def.type" in node["captures"] and 
                                    node["captures"].get("macro.def.type", {}).get("text", "") == "define-macro" else
                "syntax_rule_based" if "macro.def.type" in node["captures"] else
                "unknown"
            )
        }
    },
    
    "module_patterns": {
        "pattern": """
        [
            (list_lit
                .
                (sym_lit) @module.def.type
                (#match? @module.def.type "^(module|module\\*)$")
                .
                (sym_lit) @module.def.name
                .
                (sym_lit) @module.def.lang
                .
                (_)* @module.def.body) @module.def,
                
            (list_lit
                .
                (sym_lit) @module.require.type
                (#match? @module.require.type "^(require)$")
                .
                (_)* @module.require.specs) @module.require,
                
            (list_lit
                .
                (sym_lit) @module.provide.type
                (#match? @module.provide.type "^(provide)$")
                .
                (_)* @module.provide.specs) @module.provide
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "module_patterns",
            "is_module_definition": "module.def" in node["captures"],
            "is_require": "module.require" in node["captures"],
            "is_provide": "module.provide" in node["captures"],
            "module_name": node["captures"].get("module.def.name", {}).get("text", ""),
            "module_lang": node["captures"].get("module.def.lang", {}).get("text", ""),
            "require_specs": node["captures"].get("module.require.specs", {}).get("text", ""),
            "provide_specs": node["captures"].get("module.provide.specs", {}).get("text", ""),
            "module_system_type": (
                "module_definition" if "module.def" in node["captures"] else
                "module_import" if "module.require" in node["captures"] else
                "module_export" if "module.provide" in node["captures"] else
                "unknown"
            )
        }
    },
    
    "data_structures": {
        "pattern": """
        [
            (list_lit
                .
                (sym_lit) @struct.def.type
                (#match? @struct.def.type "^(struct|define-struct)$")
                .
                (sym_lit) @struct.def.name
                .
                (_)* @struct.def.fields) @struct.def,
                
            (quote
                value: (list_lit) @list.quoted) @list.quote,
                
            (list_lit
                .
                (sym_lit) @hash.def.type
                (#match? @hash.def.type "^(hash|hasheq|hasheqv)$")
                .
                (_)* @hash.def.entries) @hash.def,
                
            (list_lit
                .
                (sym_lit) @vector.def.type
                (#match? @vector.def.type "^(vector)$")
                .
                (_)* @vector.def.elements) @vector.def
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "data_structures",
            "is_struct_definition": "struct.def" in node["captures"],
            "is_quoted_list": "list.quote" in node["captures"],
            "is_hash_table": "hash.def" in node["captures"],
            "is_vector": "vector.def" in node["captures"],
            "struct_name": node["captures"].get("struct.def.name", {}).get("text", ""),
            "struct_definition_type": node["captures"].get("struct.def.type", {}).get("text", ""),
            "hash_type": node["captures"].get("hash.def.type", {}).get("text", ""),
            "data_structure_type": (
                "struct" if "struct.def" in node["captures"] else
                "quoted_list" if "list.quote" in node["captures"] else
                "hash_table" if "hash.def" in node["captures"] else
                "vector" if "vector.def" in node["captures"] else
                "unknown"
            )
        }
    }
}

RACKET_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "function": QueryPattern(
                pattern="""
                [
                    (list_lit
                        .
                        (sym_lit) @def_type
                        (#match? @def_type "^(define|lambda)$")
                        .
                        [(sym_lit) (list_lit)] @syntax.function.name
                        .
                        (list_lit)? @syntax.function.params
                        .
                        (_)* @syntax.function.body) @syntax.function.def
                ]
                """,
                extract=lambda node: {
                    "name": node["captures"].get("syntax.function.name", {}).get("text", ""),
                    "type": "function",
                    "has_params": "syntax.function.params" in node["captures"]
                }
            ),
            "macro": QueryPattern(
                pattern="""
                [
                    (list_lit
                        .
                        (sym_lit) @def_type
                        (#match? @def_type "^(define-syntax|define-syntax-rule)$")
                        .
                        (sym_lit) @syntax.macro.name
                        .
                        (_)* @syntax.macro.body) @syntax.macro.def
                ]
                """,
                extract=lambda node: {
                    "name": node["captures"].get("syntax.macro.name", {}).get("text", ""),
                    "type": "macro"
                }
            )
        }
    },

    PatternCategory.STRUCTURE: {
        PatternPurpose.UNDERSTANDING: {
            "module": QueryPattern(
                pattern="""
                [
                    (list_lit
                        .
                        (sym_lit) @def_type
                        (#match? @def_type "^(module|module\\*)$")
                        .
                        (sym_lit) @structure.module.name
                        .
                        (sym_lit) @structure.module.lang
                        .
                        (_)* @structure.module.body) @structure.module.def
                ]
                """,
                extract=lambda node: {
                    "name": node["captures"].get("structure.module.name", {}).get("text", ""),
                    "language": node["captures"].get("structure.module.lang", {}).get("text", "")
                }
            ),
            "require": QueryPattern(
                pattern="""
                (list_lit
                    .
                    (sym_lit) @def_type
                    (#match? @def_type "^(require)$")
                    .
                    (_)* @structure.require.specs) @structure.require.def
                """,
                extract=lambda node: {
                    "type": "require",
                    "specs": node["captures"].get("structure.require.specs", {}).get("text", "")
                }
            )
        }
    },

    PatternCategory.DOCUMENTATION: {
        PatternPurpose.UNDERSTANDING: {
            "comment": QueryPattern(
                pattern="""
                [
                    (comment) @documentation.comment,
                    (block_comment) @documentation.block_comment,
                    (sexp_comment) @documentation.sexp_comment
                ]
                """,
                extract=lambda node: {
                    "text": (
                        node["captures"].get("documentation.comment", {}).get("text", "") or
                        node["captures"].get("documentation.block_comment", {}).get("text", "") or
                        node["captures"].get("documentation.sexp_comment", {}).get("text", "")
                    ),
                    "type": "comment",
                    "is_block": "documentation.block_comment" in node["captures"],
                    "is_sexp": "documentation.sexp_comment" in node["captures"]
                }
            )
        }
    },

    PatternCategory.LEARNING: {
        PatternPurpose.FUNCTIONAL: {
            "functional_patterns": QueryPattern(
                pattern="""
                [
                    (list_lit
                        .
                        (sym_lit) @func.name
                        (#match? @func.name "^(map|filter|fold|reduce|andmap|ormap|apply)$")
                        .
                        (_)* @func.args) @func.app
                ]
                """,
                extract=lambda node: {
                    "pattern_type": "functional",
                    "function_name": node["captures"].get("func.name", {}).get("text", ""),
                    "has_args": "func.args" in node["captures"]
                }
            )
        }
    },

    "REPOSITORY_LEARNING": RACKET_PATTERNS_FOR_LEARNING
} 