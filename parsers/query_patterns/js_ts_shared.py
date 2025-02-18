"""Shared patterns between JavaScript and TypeScript."""

from .common import COMMON_PATTERNS

JS_TS_SHARED_PATTERNS = {
    **COMMON_PATTERNS,  # Inherit common patterns
    
    # Syntax category
    "function": """
        [
          ; Regular function declaration
          (function_declaration
            name: (identifier) @syntax.function.name
            parameters: (formal_parameters) @syntax.function.params
            body: (statement_block) @syntax.function.body) @syntax.function.def,
            
          ; Arrow function
          (arrow_function
            parameters: (formal_parameters) @syntax.function.params
            body: [
              (statement_block) @syntax.function.body
              (expression) @syntax.function.body
            ]) @syntax.function.arrow,
            
          ; Method definition
          (method_definition
            name: (property_identifier) @syntax.function.name
            parameters: (formal_parameters) @syntax.function.params
            body: (statement_block) @syntax.function.body) @syntax.function.method,
            
          ; Function expression
          (function_expression
            name: (identifier)? @syntax.function.name
            parameters: (formal_parameters) @syntax.function.params
            body: (statement_block) @syntax.function.body) @syntax.function.expr
        ]
    """,
    
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
    "documentation": """
        [
          ; JSDoc comments
          (comment
            (comment_block) @documentation.jsdoc.block
            (#match? @documentation.jsdoc.block "^/\\*\\*")) @documentation.jsdoc,
            
          ; Regular comments
          (comment) @documentation.comment,
          
          ; Inline documentation
          (comment
            (#match? @documentation.comment "//")) @documentation.inline
        ]
    """,
    
    # Structure category
    "import": """
        [
          ; ES6 imports
          (import_statement
            source: (string) @structure.import.source
            clause: [
              (import_clause
                (identifier) @structure.import.default)
              (named_imports
                (import_specifier
                  name: (identifier) @structure.import.name
                  alias: (identifier)? @structure.import.alias))
            ]) @structure.import,
            
          ; Dynamic imports
          (call_expression
            function: (import) @structure.import.dynamic
            arguments: (arguments (string) @structure.import.source)) @structure.import.dynamic
        ]
    """,
    
    "export": """
        [
          ; Named exports
          (export_statement
            declaration: (_) @structure.export.declaration) @structure.export,
            
          ; Default exports
          (export_statement
            value: (_) @structure.export.default
            (#match? @structure.export.default "default")) @structure.export.default,
            
          ; Re-exports
          (export_statement
            source: (string) @structure.export.source) @structure.export.from
        ]
    """
}
