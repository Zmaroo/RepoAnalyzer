"""Common Tree-sitter patterns shared between languages."""

from parsers.types import (
    FileType, PatternCategory, PatternPurpose,
    QueryPattern, PatternDefinition
)

# Create shared patterns for common constructs
COMMON_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "function": QueryPattern(
                pattern="""
                [
                    (function_definition) @syntax.function,
                    (method_definition) @syntax.method
                ]
                """,
                extract=lambda node: {
                    "type": "method" if "syntax.method" in node["captures"] else "function",
                    "name": node["node"].text.decode('utf8')
                }
            ),
            
            "class": QueryPattern(
                pattern="""
                [
                    (class_definition) @syntax.class,
                    (class_declaration) @syntax.class
                ]
                """,
                extract=lambda node: {
                    "type": "class",
                    "name": node["node"].text.decode('utf8')
                }
            ),
            
            "module": QueryPattern(
                pattern="""
                [
                    (module) @syntax.module,
                    (program) @syntax.module
                ]
                """,
                extract=lambda node: {
                    "type": "module",
                    "name": node["node"].text.decode('utf8')
                }
            )
        }
    },

    PatternCategory.SEMANTICS: {
        PatternPurpose.UNDERSTANDING: {
            "variable": QueryPattern(
                pattern="""
                [
                    (identifier) @semantics.variable.ref,
                    (variable_declaration) @semantics.variable.def
                ]
                """,
                extract=lambda node: {
                    "type": "variable_def" if "semantics.variable.def" in node["captures"] else "variable_ref",
                    "name": node["node"].text.decode('utf8')
                }
            ),
            
            "literal": QueryPattern(
                pattern="""
                [
                    (string_literal) @semantics.literal.string,
                    (number_literal) @semantics.literal.number,
                    (boolean_literal) @semantics.literal.boolean,
                    (null_literal) @semantics.literal.null
                ]
                """,
                extract=lambda node: {
                    "type": ("string" if "semantics.literal.string" in node["captures"] else
                            "number" if "semantics.literal.number" in node["captures"] else
                            "boolean" if "semantics.literal.boolean" in node["captures"] else
                            "null"),
                    "value": node["node"].text.decode('utf8')
                }
            ),
            
            "expression": QueryPattern(
                pattern="""
                [
                    (binary_expression) @semantics.expression.binary,
                    (unary_expression) @semantics.expression.unary
                ]
                """,
                extract=lambda node: {
                    "type": "binary" if "semantics.expression.binary" in node["captures"] else "unary",
                    "expression": node["node"].text.decode('utf8')
                }
            )
        }
    },

    PatternCategory.DOCUMENTATION: {
        PatternPurpose.UNDERSTANDING: {
            "documentation": QueryPattern(
                pattern="""
                [
                    (comment) @documentation.comment,
                    (block_comment) @documentation.block,
                    (line_comment) @documentation.line,
                    (documentation_comment) @documentation.doc
                ]
                """,
                extract=lambda node: {
                    "type": ("doc" if "documentation.doc" in node["captures"] else
                            "block" if "documentation.block" in node["captures"] else
                            "line" if "documentation.line" in node["captures"] else
                            "comment"),
                    "text": node["node"].text.decode('utf8')
                }
            )
        }
    },

    PatternCategory.STRUCTURE: {
        PatternPurpose.UNDERSTANDING: {
            "import": QueryPattern(
                pattern="""
                [
                    (import_statement) @structure.import,
                    (import_declaration) @structure.import
                ]
                """,
                extract=lambda node: {
                    "type": "import",
                    "statement": node["node"].text.decode('utf8')
                }
            ),
            
            "export": QueryPattern(
                pattern="""
                [
                    (export_statement) @structure.export,
                    (export_declaration) @structure.export
                ]
                """,
                extract=lambda node: {
                    "type": "export",
                    "statement": node["node"].text.decode('utf8')
                }
            ),
            
            "namespace": QueryPattern(
                pattern="""
                [
                    (namespace_definition) @structure.namespace,
                    (package_declaration) @structure.namespace
                ]
                """,
                extract=lambda node: {
                    "type": "namespace",
                    "name": node["node"].text.decode('utf8')
                }
            )
        }
    }
}

# Note: Languages should now use PatternCategory and PatternPurpose directly
# instead of merging with COMMON_PATTERNS. Example:
#
# from parsers.types import PatternCategory, PatternPurpose, QueryPattern
# from .common import COMMON_PATTERNS
#
# LANGUAGE_PATTERNS = {
#     PatternCategory.SYNTAX: {
#         PatternPurpose.UNDERSTANDING: {
#             **COMMON_PATTERNS[PatternCategory.SYNTAX][PatternPurpose.UNDERSTANDING],
#             # Language-specific patterns...
#         }
#     }
# } 