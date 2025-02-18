"""Common Tree-sitter patterns shared between languages."""

# Create shared patterns for common constructs
COMMON_PATTERNS = {
    # Syntax category
    "function": """
        [
          (function_definition) @syntax.function,
          (method_definition) @syntax.method
        ]
    """,
    
    "class": """
        [
          (class_definition) @syntax.class,
          (class_declaration) @syntax.class
        ]
    """,
    
    "module": """
        [
          (module) @syntax.module,
          (program) @syntax.module
        ]
    """,

    # Semantics category
    "variable": """
        [
          (identifier) @semantics.variable.ref,
          (variable_declaration) @semantics.variable.def
        ]
    """,
    
    "literal": """
        [
          (string_literal) @semantics.literal.string,
          (number_literal) @semantics.literal.number,
          (boolean_literal) @semantics.literal.boolean,
          (null_literal) @semantics.literal.null
        ]
    """,
    
    "expression": """
        [
          (binary_expression) @semantics.expression.binary,
          (unary_expression) @semantics.expression.unary
        ]
    """,

    # Documentation category
    "documentation": """
        [
          (comment) @documentation.comment,
          (block_comment) @documentation.block,
          (line_comment) @documentation.line,
          (documentation_comment) @documentation.doc
        ]
    """,

    # Structure category
    "import": """
        [
          (import_statement) @structure.import,
          (import_declaration) @structure.import
        ]
    """,
    
    "export": """
        [
          (export_statement) @structure.export,
          (export_declaration) @structure.export
        ]
    """,
    
    "namespace": """
        [
          (namespace_definition) @structure.namespace,
          (package_declaration) @structure.namespace
        ]
    """
}

# Languages can import and extend these patterns:
from .common import COMMON_PATTERNS
LANGUAGE_PATTERNS = {
    **COMMON_PATTERNS,
    # Language-specific patterns...
} 