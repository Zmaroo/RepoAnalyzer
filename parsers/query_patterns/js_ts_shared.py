"""Shared patterns between JavaScript and TypeScript."""

from .common import COMMON_PATTERNS

JS_TS_SHARED_PATTERNS = {
    **COMMON_PATTERNS,  # Inherit common patterns
    
    # Syntax category
    "syntax": {
        "function": {
            "pattern": """
            [
                (function_declaration
                    modifiers: [(async) (export) (default)]* @syntax.function.modifier
                    name: (identifier) @syntax.function.name
                    parameters: (formal_parameters) @syntax.function.params
                    body: (statement_block) @syntax.function.body) @syntax.function.def,
                
                (arrow_function
                    modifiers: (async)? @syntax.function.arrow.modifier
                    parameters: (formal_parameters) @syntax.function.arrow.params
                    body: [(statement_block) (expression)] @syntax.function.arrow.body) @syntax.function.arrow,
                
                (method_definition
                    modifiers: [(static) (async) (get) (set)]* @syntax.function.method.modifier
                    name: [(property_identifier) (computed_property_name)] @syntax.function.method.name
                    parameters: (formal_parameters) @syntax.function.method.params
                    body: (statement_block) @syntax.function.method.body) @syntax.function.method,
                
                (function_expression
                    modifiers: (async)? @syntax.function.expr.modifier
                    name: (identifier)? @syntax.function.expr.name
                    parameters: (formal_parameters) @syntax.function.expr.params
                    body: (statement_block) @syntax.function.expr.body) @syntax.function.expr
            ]
            """,
            "extract": lambda node: {
                "name": node["captures"].get("syntax.function.name", {}).get("text", ""),
                "parameters": node["captures"].get("syntax.function.params", {}).get("text", ""),
                "modifiers": [m.text.decode('utf8') for m in node["captures"].get("syntax.function.modifier", [])]
            }
        },
        "variable": {
            "pattern": """
            [
                (variable_declaration
                    kind: (_) @syntax.variable.kind
                    (variable_declarator
                        name: [(identifier) @syntax.variable.name
                              (array_pattern) @syntax.variable.array_pattern
                              (object_pattern) @syntax.variable.object_pattern]
                        type: (type_annotation)? @syntax.variable.type
                        value: (_)? @syntax.variable.value)) @syntax.variable.def,
                
                (object_pattern
                    [(shorthand_property_identifier_pattern) @syntax.variable.destructure.shorthand
                     (pair_pattern
                        key: (_) @syntax.variable.destructure.key
                        value: (_) @syntax.variable.destructure.value)]) @syntax.variable.destructure
            ]
            """,
            "extract": lambda node: {
                "name": node["captures"].get("syntax.variable.name", {}).get("text", ""),
                "kind": node["captures"].get("syntax.variable.kind", {}).get("text", ""),
                "value": node["captures"].get("syntax.variable.value", {}).get("text", "")
            }
        },
        "expression": {
            "pattern": """
            [
                (object
                    [(pair
                        key: (_) @syntax.object.key
                        value: (_) @syntax.object.value)
                     (method_definition) @syntax.object.method
                     (shorthand_property_identifier) @syntax.object.shorthand]) @syntax.object,
                
                (array
                    (_)* @syntax.array.element) @syntax.array,
                
                (template_string
                    (template_substitution
                        (_) @syntax.template.expression)) @syntax.template
            ]
            """,
            "extract": lambda node: {
                "type": "object" if "syntax.object" in node["captures"] else "array" if "syntax.array" in node["captures"] else "template"
            }
        }
    },
    
    # Semantics category
    "variable": """
        [
          ; Variable declarations
          (variable_declaration
            kind: (_) @semantics.variable.kind
            (variable_declarator
              name: (identifier) @semantics.variable.name
              value: (_)? @semantics.variable.value)) @semantics.variable.def,
              
          ; Destructuring patterns
          (object_pattern
            (shorthand_property_identifier_pattern) @semantics.variable.destructure.shorthand
            (pair_pattern
              key: (_) @semantics.variable.destructure.key
              value: (_) @semantics.variable.destructure.value)) @semantics.variable.destructure
        ]
    """,
    
    "expression": """
        [
          ; Object expressions
          (object
            (pair
              key: (_) @semantics.object.key
              value: (_) @semantics.object.value)) @semantics.object,
              
          ; Array expressions
          (array
            (_)* @semantics.array.element) @semantics.array,
              
          ; Template literals
          (template_string
            (template_substitution
              (_) @semantics.template.expression)) @semantics.template
        ]
    """,
    
    # Documentation category
    "documentation": {
        "pattern": """
        [
            (comment
                text: (_) @documentation.jsdoc.text
                (#match? @documentation.jsdoc.text "^/\\*\\*")) @documentation.jsdoc,
            
            (comment) @documentation.comment,
            
            (comment
                text: (_) @documentation.inline.text
                (#match? @documentation.inline.text "^//")) @documentation.inline
        ]
        """,
        "extract": lambda node: {
            "text": node["captures"].get("documentation.jsdoc.text", {}).get("text", "") or
                   node["captures"].get("documentation.inline.text", {}).get("text", "") or
                   node["captures"].get("documentation.comment", {}).get("text", "")
        }
    },
    
    # Structure category
    "import_export": {
        "pattern": """
        [
            (import_statement
                source: (string) @structure.import.source
                clause: [
                    (import_clause
                        (identifier) @structure.import.default)
                    (named_imports
                        (import_specifier
                            name: (identifier) @structure.import.name
                            alias: (identifier)? @structure.import.alias))]) @structure.import,
            
            (export_statement
                declaration: (_)? @structure.export.declaration
                source: (string)? @structure.export.source
                clause: (export_clause
                    (export_specifier
                        name: (identifier) @structure.export.name
                        alias: (identifier)? @structure.export.alias))?) @structure.export
        ]
        """,
        "extract": lambda node: {
            "source": node["captures"].get("structure.import.source", {}).get("text", "") or
                     node["captures"].get("structure.export.source", {}).get("text", ""),
            "type": "import" if "structure.import" in node["captures"] else "export"
        }
    }
}
