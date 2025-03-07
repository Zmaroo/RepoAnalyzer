"""
Query patterns for Scheme files.
"""

from parsers.types import (
    FileType, PatternCategory, PatternPurpose,
    QueryPattern, PatternDefinition
)
from .common import COMMON_PATTERNS

SCHEME_PATTERNS_FOR_LEARNING = {
    "functional_patterns": {
        "pattern": """
        [
            (list
                "(" @func.list.open
                (symbol) @func.name
                (_)* @func.args
                ")" @func.list.close
                (#match? @func.name "^(lambda|define)$")) @func.def,
                
            (list
                "(" @func.hof.open
                (symbol) @func.hof.name
                (_)* @func.hof.args
                ")" @func.hof.close
                (#match? @func.hof.name "^(map|filter|fold|reduce|apply)$")) @func.hof,
                
            (list
                "(" @func.rec.open
                (symbol) @func.rec.name
                (_)* @func.rec.args
                ")" @func.rec.close
                (#any-of? @func.rec.name "letrec" "let" "named-lambda")) @func.recursion,
                
            (list
                "(" @func.comp.open
                (symbol) @func.comp.name
                (_)* @func.comp.args
                ")" @func.comp.close
                (#match? @func.comp.name "^(compose|pipe|andmap|ormap)$")) @func.composition
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "functional_patterns",
            "is_function_def": "func.def" in node["captures"],
            "is_higher_order": "func.hof" in node["captures"],
            "is_recursion": "func.recursion" in node["captures"],
            "is_composition": "func.composition" in node["captures"],
            "function_name": (
                node["captures"].get("func.name", {}).get("text", "") or
                node["captures"].get("func.hof.name", {}).get("text", "") or
                node["captures"].get("func.rec.name", {}).get("text", "") or
                node["captures"].get("func.comp.name", {}).get("text", "")
            ),
            "functional_pattern": (
                "lambda_definition" if "func.def" in node["captures"] and node["captures"].get("func.name", {}).get("text", "") == "lambda" else
                "function_definition" if "func.def" in node["captures"] and node["captures"].get("func.name", {}).get("text", "") == "define" else
                "higher_order_function" if "func.hof" in node["captures"] else
                "recursion" if "func.recursion" in node["captures"] else
                "function_composition" if "func.composition" in node["captures"] else
                "unknown"
            )
        }
    },
    
    "data_structures": {
        "pattern": """
        [
            (list
                "(" @data.list.open
                (symbol) @data.list.name
                (_)* @data.list.elements
                ")" @data.list.close
                (#match? @data.list.name "^(list|vector|make-vector|cons)$")) @data.list.expr,
                
            (list
                "(" @data.assoc.open
                (symbol) @data.assoc.name
                (_)* @data.assoc.elements
                ")" @data.assoc.close
                (#match? @data.assoc.name "^(hash-table|make-hash-table|alist->hash-table)$")) @data.assoc.expr,
                
            (pair "(" @data.pair.open "_" "." "_" ")" @data.pair.close) @data.pair.expr,
                
            (list
                "(" @data.struct.open
                (symbol) @data.struct.name
                (_)* @data.struct.elements
                ")" @data.struct.close
                (#match? @data.struct.name "^(define-struct|define-record-type)$")) @data.struct.expr
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "data_structures",
            "is_list": "data.list.expr" in node["captures"],
            "is_associative": "data.assoc.expr" in node["captures"],
            "is_pair": "data.pair.expr" in node["captures"],
            "is_struct": "data.struct.expr" in node["captures"],
            "structure_name": (
                node["captures"].get("data.list.name", {}).get("text", "") or
                node["captures"].get("data.assoc.name", {}).get("text", "") or 
                node["captures"].get("data.struct.name", {}).get("text", "")
            ),
            "data_structure_pattern": (
                "list" if "data.list.expr" in node["captures"] and node["captures"].get("data.list.name", {}).get("text", "") == "list" else
                "vector" if "data.list.expr" in node["captures"] and node["captures"].get("data.list.name", {}).get("text", "") in ["vector", "make-vector"] else
                "cons_cell" if "data.list.expr" in node["captures"] and node["captures"].get("data.list.name", {}).get("text", "") == "cons" else
                "hashtable" if "data.assoc.expr" in node["captures"] else
                "pair" if "data.pair.expr" in node["captures"] else
                "struct" if "data.struct.expr" in node["captures"] else
                "unknown"
            )
        }
    },
    
    "macros": {
        "pattern": """
        [
            (list
                "(" @macro.def.open
                (symbol) @macro.def.name
                (_)* @macro.def.args
                ")" @macro.def.close
                (#match? @macro.def.name "^(define-syntax|syntax-rules|define-macro)$")) @macro.def.expr,
                
            (list
                "(" @macro.use.open
                (symbol) @macro.use.name
                (_)* @macro.use.args
                ")" @macro.use.close
                (#match? @macro.use.name "^(syntax|quasisyntax|unsyntax|syntax-case)$")) @macro.use.expr,
                
            (list
                "(" @macro.expand.open
                (symbol) @macro.expand.name
                (_)* @macro.expand.args
                ")" @macro.expand.close
                (#match? @macro.expand.name "^(expand|syntax->datum|datum->syntax)$")) @macro.expand.expr
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "macros",
            "is_macro_definition": "macro.def.expr" in node["captures"],
            "is_macro_use": "macro.use.expr" in node["captures"],
            "is_macro_expand": "macro.expand.expr" in node["captures"],
            "macro_name": (
                node["captures"].get("macro.def.name", {}).get("text", "") or
                node["captures"].get("macro.use.name", {}).get("text", "") or
                node["captures"].get("macro.expand.name", {}).get("text", "")
            ),
            "macro_pattern": (
                "macro_definition" if "macro.def.expr" in node["captures"] else
                "macro_use" if "macro.use.expr" in node["captures"] else
                "macro_expansion" if "macro.expand.expr" in node["captures"] else
                "unknown"
            )
        }
    },
    
    "module_system": {
        "pattern": """
        [
            (list
                "(" @module.def.open
                (symbol) @module.def.name
                (_)* @module.def.args
                ")" @module.def.close
                (#match? @module.def.name "^(define-module|module|library)$")) @module.def.expr,
                
            (list
                "(" @module.import.open
                (symbol) @module.import.name
                (_)* @module.import.args
                ")" @module.import.close
                (#match? @module.import.name "^(import|use|require)$")) @module.import.expr,
                
            (list
                "(" @module.export.open
                (symbol) @module.export.name
                (_)* @module.export.args
                ")" @module.export.close
                (#match? @module.export.name "^(export|provide)$")) @module.export.expr,
                
            (list
                "(" @module.include.open
                (symbol) @module.include.name
                (_)* @module.include.args
                ")" @module.include.close
                (#match? @module.include.name "^(include|include-ci|include-lib)$")) @module.include.expr
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "module_system",
            "is_module_def": "module.def.expr" in node["captures"],
            "is_import": "module.import.expr" in node["captures"],
            "is_export": "module.export.expr" in node["captures"],
            "is_include": "module.include.expr" in node["captures"],
            "module_directive": (
                node["captures"].get("module.def.name", {}).get("text", "") or
                node["captures"].get("module.import.name", {}).get("text", "") or
                node["captures"].get("module.export.name", {}).get("text", "") or
                node["captures"].get("module.include.name", {}).get("text", "")
            ),
            "module_pattern": (
                "module_definition" if "module.def.expr" in node["captures"] else
                "import" if "module.import.expr" in node["captures"] else
                "export" if "module.export.expr" in node["captures"] else
                "include" if "module.include.expr" in node["captures"] else
                "unknown"
            )
        }
    }
}

SCHEME_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "function": QueryPattern(
                pattern="""
                [
                    (list_lit
                        "(" @syntax.function.open
                        (sym_lit) @syntax.function.name
                        (list_lit
                            "(" @syntax.function.params.open
                            [(sym_lit) @syntax.function.param
                            (list_lit
                                "(" @syntax.function.param.nested.open
                                [(sym_lit) (list_lit)]+ @syntax.function.param.nested
                                ")" @syntax.function.param.nested.close)]* @syntax.function.params.all
                            ")" @syntax.function.params.close) @syntax.function.params
                        (_)+ @syntax.function.body
                        ")" @syntax.function.close
                        (#match? @syntax.function.name "^define$")) @syntax.function.def
                ]
                """,
                extract=lambda node: {
                    "name": node["captures"].get("syntax.function.name", {}).get("text", ""),
                    "params": [p.text.decode('utf8') for p in node["captures"].get("syntax.function.param", [])]
                }
            ),
            "variable": QueryPattern(
                pattern="""
                [
                    (list_lit
                        "(" @syntax.variable.open
                        (sym_lit) @syntax.variable.name
                        (sym_lit) @syntax.variable.binding
                        (_) @syntax.variable.value
                        ")" @syntax.variable.close
                        (#match? @syntax.variable.name "^define$")) @syntax.variable.def
                ]
                """,
                extract=lambda node: {
                    "name": node["captures"].get("syntax.variable.binding", {}).get("text", "")
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
                        "(" @structure.module.open
                        (sym_lit) @structure.module.name
                        (sym_lit)? @structure.module.module_name
                        (_)* @structure.module.body
                        ")" @structure.module.close
                        (#match? @structure.module.name "^(module|define-module|library)$")) @structure.module.def,
                    
                    (list_lit
                        "(" @structure.import.open
                        (sym_lit) @structure.import.name
                        (_)* @structure.import.modules
                        ")" @structure.import.close
                        (#match? @structure.import.name "^(import|use|require)$")) @structure.import.statement,
                    
                    (list_lit
                        "(" @structure.export.open
                        (sym_lit) @structure.export.name
                        (_)* @structure.export.bindings
                        ")" @structure.export.close
                        (#match? @structure.export.name "^(export|provide)$")) @structure.export.statement
                ]
                """,
                extract=lambda node: {
                    "type": (
                        "module_def" if "structure.module.def" in node["captures"] else
                        "import" if "structure.import.statement" in node["captures"] else
                        "export" if "structure.export.statement" in node["captures"] else "unknown"
                    ),
                    "module_name": node["captures"].get("structure.module.module_name", {}).get("text", "")
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
                    (block_comment) @documentation.block
                ]
                """,
                extract=lambda node: {
                    "text": (
                        node["captures"].get("documentation.comment", {}).get("text", "") or
                        node["captures"].get("documentation.block", {}).get("text", "")
                    ),
                    "type": "block" if "documentation.block" in node["captures"] else "line"
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
                        "(" @learning.func.open
                        (sym_lit) @learning.func.name
                        (#match? @learning.func.name "^(map|filter|fold|reduce|andmap|ormap|apply)$")
                        (_)* @learning.func.args
                        ")" @learning.func.close) @learning.func.call
                ]
                """,
                extract=lambda node: {
                    "pattern_type": "functional",
                    "function_name": node["captures"].get("learning.func.name", {}).get("text", ""),
                    "is_higher_order": True,
                    "has_args": "learning.func.args" in node["captures"]
                }
            )
        }
    },

    "REPOSITORY_LEARNING": SCHEME_PATTERNS_FOR_LEARNING
} 