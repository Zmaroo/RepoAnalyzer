"""Base patterns shared between JavaScript and TypeScript."""

from .js_ts_shared import JS_TS_SHARED_PATTERNS

JS_BASE_PATTERNS = {
    **JS_TS_SHARED_PATTERNS,
    # Syntax category
    "class": """
        [
          (class_declaration
            [
              (comment)* @class.jsdoc
            ]?
            name: (identifier) @class.name
            body: (class_body) @class.body) @class.def,
          (class_expression
            name: (identifier)? @class.name
            body: (class_body) @class.body) @class.expr
        ]
    """,
    
    "module": """
        [
          (program
            [
              (import_statement)* @module.imports
              (export_statement)* @module.exports
              (_)* @module.body
            ]) @module.def
        ]
    """,

    # Semantics category
    "variable": """
        [
          (variable_declaration
            kind: (_) @variable.kind
            declarator: (variable_declarator
              name: (identifier) @variable.name
              value: (_)? @variable.value)) @variable.def,
          (identifier) @variable.ref
        ]
    """,

    "type": """
        [
          (type_annotation
            (_) @type.annotation) @type,
          (type_identifier) @type.name
        ]
    """,

    "expression": """
        [
          (binary_expression
            left: (_) @expr.left
            operator: (_) @expr.operator 
            right: (_) @expr.right) @expr.binary,
          (unary_expression
            operator: (_) @expr.operator
            argument: (_) @expr.argument) @expr.unary
        ]
    """,

    # Structure category
    "namespace": """
        [
          (namespace_import
            name: (identifier) @namespace.name) @namespace,
          (namespace_export
            name: (identifier) @namespace.name) @namespace.export
        ]
    """
} 